from flask import Flask, request, Response, jsonify
import requests
import json
import subprocess
from pathlib import Path
import threading

app = Flask(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:0.5b"

MIC_DEVICE = "plughw:3,0"
SPEAKER_DEVICE = "plughw:2,0"

WHISPER_BIN = str(Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli")
WHISPER_MODEL = str(Path.home() / "whisper.cpp" / "models" / "ggml-base.en.bin")

PIPER_BIN = str(Path.home() / ".local" / "bin" / "piper")
PIPER_MODEL = str(Path.home() / "jetson-ui" / "en_US-lessac-medium.onnx")

INPUT_WAV = str(Path.home() / "rozee_input.wav")
OUTPUT_WAV = str(Path.home() / "rozee_output.wav")

SYSTEM_PROMPT = (
    "You are a local voice assistant. "
    "Answer in no more than 2 short sentences. "
    "Use simple, direct wording. "
    "If the request is unclear, ask one short clarifying question. "
    "Do not ramble."
)

messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + incoming_messages

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
                        token = obj["message"]["content"]
                        yield f"data: {json.dumps({'token': token})}\n\n"

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

    return jsonify({"status": "recording"})


@app.route("/stop_recording", methods=["POST"])
def stop_recording():
    global recording_proc
    with recording_lock:
        if recording_proc is None:
            return jsonify({"error": "Not recording"}), 400

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

    return jsonify({"status": "stopped"})


def transcribe_audio():
    result = subprocess.run(
        [
            WHISPER_BIN,
            "-m", WHISPER_MODEL,
            "-f", INPUT_WAV,
            "-nt"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def speak_text(text):
    try:
        p = subprocess.Popen(
            [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", OUTPUT_WAV],
            stdin=subprocess.PIPE,
            text=True
        )
        p.communicate(text)

        subprocess.run(
            ["aplay", "-D", SPEAKER_DEVICE, OUTPUT_WAV],
            check=True
        )
    except Exception as e:
        print(f"TTS ERROR: {e}")


@app.route("/voice_turn", methods=["POST"])
def voice_turn():
    global messages

    transcript = transcribe_audio()

    if not transcript:
        return jsonify({"error": "I did not catch that."}), 400

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
                        speak_text(assistant_text)
                        yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
