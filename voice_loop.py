import subprocess
import requests
from pathlib import Path

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
    "Keep replies short, clear, and conversational."
    "if the user asks a question focus on answering the question as best you can"
    "You are a local voice assistant. Answer in 1 to 2 short sentences. Use simple, direct wording."
    "If the user’s request is unclear, ask one short clarifying question."
    "Do not ramble."
    "If the user does anything other than ask a question reply telling the user you can only answer questions right now"
    "If the speaker sounds like a child, be warm and age-appropriate."
)

messages = [{"role": "system", "content": SYSTEM_PROMPT}]

def start_recording():
    print("Listening... press Enter to stop.")
    return subprocess.Popen(
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

def stop_recording(proc):
    try:
        proc.terminate()
        proc.wait(timeout=2)
    except Exception:
        proc.kill()

def transcribe_audio():
    print("Transcribing...")
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

def ask_ollama(user_text):
    print("Thinking...")
    messages.append({"role": "user", "content": user_text})

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": messages,
            "stream": True,
            "keep_alive": -1
        },
        timeout=120
    )
    response.raise_for_status()

    data = response.json()
    reply = data["message"]["content"].strip()
    messages.append({"role": "assistant", "content": reply})
    return reply

def speak_text(text):
    print("Speaking...")
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

def main():
    print("Press Enter to start recording. Type q and press Enter to quit.")

    while True:
        cmd = input("> ").strip().lower()
        if cmd == "q":
            break

        recorder = start_recording()
        input()
        stop_recording(recorder)

        transcript = transcribe_audio()
        if not transcript:
            print("I did not catch that.")
            continue

        print(f"You said: {transcript}")
        reply = ask_ollama(transcript)
        print(f"Assistant: {reply}")
        speak_text(reply)

if __name__ == "__main__":
    main()
