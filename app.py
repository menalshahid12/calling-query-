"""
IST AI Calling Agent — Flask backend.
Handles STT → RAG → LLM → TTS pipeline with session management.
"""

import os, time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

import knowledge_base as kb
import stt
import llm
import tts
import session_manager as sm

app = Flask(__name__, static_folder="static")
CORS(app)

ESCALATION_KEYWORDS = [
    "forward your query",
    "provide your phone number",
    "call you back",
    "admissions office",
]

GOODBYE_TEXT = "Thank you for calling the Institute of Space Technology. Goodbye and have a great day!"


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/start", methods=["POST"])
def start_call():
    session_id = sm.create_session()
    audio_url = tts.get_greeting(session_id)
    return jsonify({
        "session_id": session_id,
        "audio_url": audio_url,
        "message": "Call started",
    })


@app.route("/api/query", methods=["POST"])
def handle_query():
    start_time = time.time()

    session_id = request.form.get("session_id", "")
    if not session_id or not sm.get_session(session_id):
        return jsonify({"error": "Invalid session"}), 400

    audio_file = request.files.get("audio")
    if not audio_file:
        return jsonify({"error": "No audio provided"}), 400

    content_type = audio_file.content_type or "audio/webm"
    audio_bytes = audio_file.read()

    user_text = stt.transcribe(audio_bytes, content_type)
    if not user_text or len(user_text.strip()) < 2:
        return jsonify({"error": "Could not understand audio", "retry": True}), 200

    if sm.is_end_call(user_text):
        goodbye_url = tts.synthesize(GOODBYE_TEXT, session_id)
        sm.add_turn(session_id, user_text, GOODBYE_TEXT)
        sm.end_session(session_id)
        metrics = sm.get_metrics(session_id)
        return jsonify({
            "text": GOODBYE_TEXT,
            "audio_url": goodbye_url,
            "end_call": True,
            "metrics": metrics,
            "latency_ms": round((time.time() - start_time) * 1000),
        })

    if sm.is_awaiting_phone(session_id):
        phone = sm.extract_phone(user_text)
        if phone:
            sm.save_phone(session_id, phone)
            reply = f"Thank you! I've noted your number {phone}. The admissions office will call you back soon. Is there anything else I can help you with?"
            reply_url = tts.synthesize(reply, session_id)
            sm.add_turn(session_id, user_text, reply)
            return jsonify({
                "text": reply,
                "audio_url": reply_url,
                "user_text": user_text,
                "end_call": False,
                "latency_ms": round((time.time() - start_time) * 1000),
            })
        else:
            sm.set_awaiting_phone(session_id, False)

    history = sm.get_conversation_history(session_id)

    search_query = user_text
    if len(user_text.split()) <= 3 and history:
        prev_user = history[-1].get("user", "")
        search_query = f"{prev_user} {user_text}"

    context = kb.search(search_query)
    answer = llm.generate_answer(user_text, context, history)

    is_escalation = any(kw in answer.lower() for kw in ESCALATION_KEYWORDS)
    if is_escalation:
        sm.mark_escalated(session_id)

    audio_url = tts.synthesize(answer, session_id)
    sm.add_turn(session_id, user_text, answer)

    return jsonify({
        "text": answer,
        "audio_url": audio_url,
        "user_text": user_text,
        "end_call": False,
        "escalated": is_escalation,
        "latency_ms": round((time.time() - start_time) * 1000),
    })


with app.app_context():
    print("[APP] Initializing knowledge base...")
    kb.init_kb()
    print("[APP] Ready.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
