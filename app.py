from flask import Flask, request, Response, jsonify
import requests
import json
import subprocess
from pathlib import Path
import threading
import time

from db import (
    list_tasks,
    get_task,
    create_task,
    update_task,
    add_task_inference,
    add_task_person,
    add_subtask,
    add_dependency,
)

app = Flask(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "smollm2:360m"

MIC_DEVICE = "plughw:3,0"
SPEAKER_DEVICE = "plughw:2,0"

WHISPER_BIN = str(Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli")
WHISPER_MODEL = str(Path.home() / "whisper.cpp" / "models" / "ggml-base.en.bin")

PIPER_BIN = str(Path.home() / ".local" / "bin" / "piper")
PIPER_MODEL = str(Path.home() / "jetson-ui" / "en_US-lessac-medium.onnx")

INPUT_WAV = str(Path.home() / "rozee_input.wav")
WHISPER_OUT_BASE = str(Path.home() / "rozee_whisper")
OUTPUT_WAV = str(Path.home() / "rozee_output.wav")

CHAT_SYSTEM_PROMPT = (
    "You are Rozee, a local offline task capture and prioritization assistant. "
    "Keep replies short and practical."
)

TASK_EXTRACTION_SYSTEM = (
    "You extract structured task records from a user's spoken task dump. "
    "Do not write generic assistant prose. "
    "Return only structured task data that can be stored in a task database. "
    "Split combined statements into separate tasks when needed. "
    "Use short concrete task titles that start with an action verb. "
    "Capture people involved in each task when named. "
    "Capture deadline phrases like tomorrow, Friday, next week, by 3 PM when stated. "
    "Capture dependency relationships when one task must happen before another. "
    "If something is directly stated, store it as task data. "
    "If something is only inferred, place it in ai_inference_candidates instead. "
    "Prefer null over guessing."
)

TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "project": {"type": ["string", "null"]},
                    "category": {"type": ["string", "null"]},
                    "subcategory": {"type": ["string", "null"]},
                    "context": {"type": ["string", "null"]},
                    "priority_user": {"type": ["integer", "null"]},
                    "importance_user": {"type": ["integer", "null"]},
                    "impact_user": {"type": ["integer", "null"]},
                    "urgency_user": {"type": ["integer", "null"]},
                    "deadline_text": {"type": ["string", "null"]},
                    "hard_deadline": {"type": ["string", "null"]},
                    "soft_deadline": {"type": ["string", "null"]},
                    "estimated_minutes_min": {"type": ["integer", "null"]},
                    "estimated_minutes_max": {"type": ["integer", "null"]},
                    "can_delegate": {"type": ["integer", "null"]},
                    "can_outsource": {"type": ["integer", "null"]},
                    "can_automate": {"type": ["integer", "null"]},
                    "line_of_effort": {"type": ["string", "null"]},
                    "line_of_operation": {"type": ["string", "null"]},
                    "function": {"type": ["string", "null"]},
                    "depends_on_summary": {"type": ["string", "null"]},
                    "depends_on_task_titles": {
                        "type": ["array", "null"],
                        "items": {"type": "string"}
                    },
                    "notes_for_review": {"type": ["string", "null"]},
                    "people": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "properties": {
                                "person_name": {"type": "string"},
                                "role": {"type": ["string", "null"]},
                                "involvement_type": {"type": ["string", "null"]},
                                "required": {"type": ["integer", "null"]}
                            },
                            "required": ["person_name"]
                        }
                    },
                    "subtasks": {
                        "type": ["array", "null"],
                        "items": {"type": "string"}
                    },
                    "ai_inference_candidates": {
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "properties": {
                                "field_name": {"type": "string"},
                                "inferred_value": {"type": ["string", "null"]},
                                "rationale": {"type": ["string", "null"]},
                                "confidence": {"type": ["number", "null"]}
                            },
                            "required": ["field_name"]
                        }
                    }
                },
                "required": ["title"]
            }
        }
    },
    "required": ["tasks"]
}

messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
recording_proc = None
recording_lock = threading.Lock()


@app.route("/")
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    incoming_messages = data.get("messages", [])
    full_messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + incoming_messages

    def generate():
        try:
            with requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": full_messages,
                    "stream": True,
                    "keep_alive": -1,
                    "options": {
                        "num_ctx": 1024,
                        "temperature": 0.2
                    }
                },
                stream=True,
                timeout=300
            ) as r:
                r.raise_for_status()

                for line in r.iter_lines():
                    if not line:
                        continue
                    obj = json.loads(line.decode("utf-8"))

                    if "message" in obj and "content" in obj["message"]:
                        yield f"data: {json.dumps({'token': obj['message']['content']})}\n\n"

                    if obj.get("done", False):
                        yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/start_recording", methods=["POST"])
def start_recording():
    global recording_proc
    with recording_lock:
        if recording_proc is not None:
            return jsonify({"error": "Already recording"}), 400

        try:
            for p in [INPUT_WAV, WHISPER_OUT_BASE + ".txt"]:
                try:
                    Path(p).unlink()
                except FileNotFoundError:
                    pass

            recording_proc = subprocess.Popen(
                [
                    "arecord",
                    "-D", MIC_DEVICE,
                    "-f", "S16_LE",
                    "-r", "16000",
                    "-c", "1",
                    INPUT_WAV
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            recording_proc = None
            return jsonify({"error": f"Failed to start recording: {e}"}), 500

    return jsonify({"status": "recording"})


@app.route("/stop_recording", methods=["POST"])
def stop_recording():
    global recording_proc
    with recording_lock:
        if recording_proc is None:
            return jsonify({"error": "Not recording"}), 400

        try:
            recording_proc.terminate()
            recording_proc.wait(timeout=3)
        except Exception:
            try:
                recording_proc.kill()
            except Exception:
                pass
        finally:
            recording_proc = None

    time.sleep(0.4)

    wav_path = Path(INPUT_WAV)
    if not wav_path.exists() or wav_path.stat().st_size < 2000:
        return jsonify({"error": "Recorded audio was too short or empty"}), 400

    return jsonify({"status": "stopped"})


@app.route("/reset", methods=["POST"])
def reset():
    global recording_proc
    with recording_lock:
        if recording_proc is not None:
            try:
                recording_proc.terminate()
                recording_proc.wait(timeout=2)
            except Exception:
                try:
                    recording_proc.kill()
                except Exception:
                    pass
            finally:
                recording_proc = None

    for pattern in ["arecord", "whisper", "piper"]:
        try:
            subprocess.run(["pkill", "-f", pattern], check=False)
        except Exception:
            pass

    return jsonify({"status": "reset"})


def transcribe_audio():
    wav_path = Path(INPUT_WAV)
    if not wav_path.exists():
        return {"error": "No audio file found"}

    if wav_path.stat().st_size < 2000:
        return {"error": "Audio file is empty or too short"}

    txt_path = Path(WHISPER_OUT_BASE + ".txt")
    try:
        txt_path.unlink()
    except FileNotFoundError:
        pass

    try:
        result = subprocess.run(
            [
                WHISPER_BIN,
                "-m", WHISPER_MODEL,
                "-f", INPUT_WAV,
                "-otxt",
                "-of", WHISPER_OUT_BASE,
                "-nt"
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120
        )
    except subprocess.TimeoutExpired:
        return {"error": "Whisper timed out"}
    except subprocess.CalledProcessError as e:
        return {"error": f"Whisper failed: {e.stderr or e.stdout or str(e)}"}
    except Exception as e:
        return {"error": f"Transcription error: {e}"}

    if not txt_path.exists():
        return {"error": "Whisper did not produce transcript output"}

    transcript = txt_path.read_text(encoding="utf-8").strip()
    if not transcript:
        return {"error": "No speech detected"}

    return {"transcript": transcript}


def speak_text(text: str):
    try:
        p = subprocess.Popen(
            [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", OUTPUT_WAV],
            stdin=subprocess.PIPE,
            text=True
        )
        p.communicate(text)
        subprocess.run(["aplay", "-D", SPEAKER_DEVICE, OUTPUT_WAV], check=True)
    except Exception as e:
        print(f"TTS ERROR: {e}")


@app.route("/voice_turn", methods=["POST"])
def voice_turn():
    global messages

    tx = transcribe_audio()
    if "error" in tx:
        return jsonify({"error": tx["error"]}), 400

    transcript = tx["transcript"]
    messages.append({"role": "user", "content": transcript})

    def generate():
        assistant_text = ""
        try:
            yield f"data: {json.dumps({'transcript': transcript})}\n\n"

            with requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": messages,
                    "stream": True,
                    "keep_alive": -1,
                    "options": {
                        "num_ctx": 1024,
                        "temperature": 0.2
                    }
                },
                stream=True,
                timeout=300
            ) as r:
                r.raise_for_status()

                for line in r.iter_lines():
                    if not line:
                        continue
                    obj = json.loads(line.decode("utf-8"))

                    if "message" in obj and "content" in obj["message"]:
                        token = obj["message"]["content"]
                        assistant_text += token
                        yield f"data: {json.dumps({'token': token})}\n\n"

                    if obj.get("done", False):
                        messages.append({"role": "assistant", "content": assistant_text})
                        if assistant_text.strip():
                            speak_text(assistant_text)
                        yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/tasks", methods=["GET"])
def api_list_tasks():
    return jsonify(list_tasks())


@app.route("/api/tasks/<int:task_id>", methods=["GET"])
def api_get_task(task_id: int):
    task = get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    data = request.get_json(force=True)
    try:
        task_id = create_task(data)
        return jsonify({"status": "ok", "task_id": task_id, "task": get_task(task_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
def api_update_task(task_id: int):
    data = request.get_json(force=True)
    changed = update_task(task_id, data)
    if not changed:
        return jsonify({"error": "No valid fields updated or task not found"}), 400
    return jsonify({"status": "ok", "task": get_task(task_id)})


@app.route("/api/extract_tasks", methods=["POST"])
def api_extract_tasks():
    data = request.get_json(force=True)
    transcript = data.get("transcript", "").strip()
    if not transcript:
        return jsonify({"error": "transcript is required"}), 400

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "stream": False,
                "format": TASK_SCHEMA,
                "messages": [
                    {"role": "system", "content": TASK_EXTRACTION_SYSTEM},
                    {"role": "user", "content": transcript}
                ],
                "options": {
                    "num_ctx": 1024,
                    "temperature": 0.1
                }
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        return jsonify(json.loads(data["message"]["content"]))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/extract_and_store", methods=["POST"])
def api_extract_and_store():
    data = request.get_json(force=True)
    transcript = data.get("transcript", "").strip()
    if not transcript:
        return jsonify({"error": "transcript is required"}), 400

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "stream": False,
                "format": TASK_SCHEMA,
                "messages": [
                    {"role": "system", "content": TASK_EXTRACTION_SYSTEM},
                    {"role": "user", "content": transcript}
                ],
                "options": {
                    "num_ctx": 1024,
                    "temperature": 0.1
                }
            },
            timeout=120
        )
        response.raise_for_status()
        extracted = json.loads(response.json()["message"]["content"])

        created_items = []
        title_to_task_number = {}

        for task in extracted.get("tasks", []):
            deadline_text = task.pop("deadline_text", None)
            notes_for_review = task.pop("notes_for_review", None)
            depends_on_task_titles = task.pop("depends_on_task_titles", None) or []
            people = task.pop("people", None) or []
            subtasks = task.pop("subtasks", None) or []
            ai_inference_candidates = task.pop("ai_inference_candidates", None) or []

            if deadline_text and not task.get("soft_deadline") and not task.get("hard_deadline"):
                task["soft_deadline"] = deadline_text

            task["raw_capture_text"] = transcript
            task["task_source"] = "voice_extraction"
            task["created_by"] = "user"

            task_id = create_task(task)
            full_task = get_task(task_id)
            title_to_task_number[full_task["title"]] = full_task["task_number"]

            for person in people:
                if person.get("person_name"):
                    add_task_person(
                        task_id=task_id,
                        person_name=person["person_name"],
                        role=person.get("role"),
                        involvement_type=person.get("involvement_type"),
                        required=person.get("required", 0) or 0,
                        source_type="user_explicit"
                    )

            for subtask_title in subtasks:
                if subtask_title:
                    add_subtask(task_id=task_id, title=subtask_title, source_type="user_explicit")

            for inf in ai_inference_candidates:
                if inf.get("field_name"):
                    add_task_inference(
                        task_id=task_id,
                        field_name=inf["field_name"],
                        inferred_value=str(inf.get("inferred_value", "")),
                        rationale=inf.get("rationale"),
                        confidence=inf.get("confidence"),
                        needs_confirmation=1
                    )

            if notes_for_review:
                add_task_inference(
                    task_id=task_id,
                    field_name="notes_for_review",
                    inferred_value=notes_for_review,
                    rationale="Model flagged this for human review",
                    confidence=0.5,
                    needs_confirmation=1
                )

            created_items.append({
                "task_id": task_id,
                "title": full_task["title"],
                "depends_on_task_titles": depends_on_task_titles
            })

        for item in created_items:
            for dep_title in item["depends_on_task_titles"]:
                dep_task_number = title_to_task_number.get(dep_title)
                if dep_task_number:
                    add_dependency(
                        task_id=item["task_id"],
                        depends_on_task_number=dep_task_number,
                        dependency_type="predecessor",
                        dependency_strength="hard",
                        source_type="user_explicit",
                        notes=f"Derived from transcript reference to: {dep_title}"
                    )

        stored = [get_task(item["task_id"]) for item in created_items]
        return jsonify({"status": "ok", "tasks": stored})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
