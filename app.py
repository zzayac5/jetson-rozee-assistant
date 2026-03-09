from flask import Flask, request, Response
import requests
import json

app = Flask(__name__)

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:0.5b"

SYSTEM_PROMPT = """
You are a friendly local assistant for a young child.
Keep replies short, warm, simple, and age-appropriate.
Ask only one question at a time.
Do not use scary, intense, or inappropriate content.
"""

@app.route("/")
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    messages = data.get("messages", [])
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    def generate():
        try:
            with requests.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "messages": full_messages,
                    "stream": True,
                    "keep_alive": -1
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
