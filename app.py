import os
import tempfile
from flask import Flask, request, jsonify, render_template, send_file
from groq import Groq
from gtts import gTTS
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """
You are Alex — a friendly, warm English conversation partner.
Your job:
- Reply like a REAL human friend
- Use casual English, emojis sometimes
- Keep it short (2–3 sentences)

Then provide:
[CONVERSATION]
<Your response>

[ANALYSIS]
- What the user said
- Corrections
- Better way to say it
"""


# ---------------------------
# HOME PAGE
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------
# TEXT CHAT
# ---------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "")

    if not user_message:
        return jsonify({"error": "No message"}), 400

    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.9,
            max_tokens=400
        )

        ai_text = response.choices[0].message.content

        audio_path = text_to_speech(ai_text)

        return jsonify({
            "response": ai_text,
            "audio_url": f"/audio/{os.path.basename(audio_path)}"
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "AI error"}), 500


# ---------------------------
# VOICE INPUT
# ---------------------------
@app.route("/api/voice", methods=["POST"])
def voice():
    if "audio" not in request.files:
        return jsonify({"error": "Missing audio"}), 400

    file = request.files["audio"]

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp:
        file.save(temp.name)
        audio_path = temp.name

    # Transcribe via Groq Whisper
    try:
        transcribe_url = "https://api.groq.com/openai/v1/audio/transcriptions"

        with open(audio_path, "rb") as audio_file:
            result = requests.post(
                transcribe_url,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files={"file": ("audio.wav", audio_file, "audio/wav")},
                data={"model": "whisper-large-v3-turbo"}
            )

        text = result.json().get("text", "").strip()

        if not text:
            return jsonify({"error": "Failed transcription"}), 500

        # Get AI response
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

        ai_response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )

        reply = ai_response.choices[0].message.content

        # Convert reply to speech
        audio_reply = text_to_speech(reply)

        return jsonify({
            "user_text": text,
            "response": reply,
            "audio_url": f"/audio/{os.path.basename(audio_reply)}"
        })

    except Exception as e:
        print("Voice error:", e)
        return jsonify({"error": "Voice process error"}), 500


# ---------------------------
# TTS (gTTS)
# ---------------------------
def text_to_speech(text):
    tts = gTTS(text=text, lang="en")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        tts.save(fp.name)
        return fp.name


@app.route("/audio/<filename>")
def serve_audio(filename):
    return send_file(f"/tmp/{filename}", mimetype="audio/mpeg")


# ---------------------------
# START SERVER
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
