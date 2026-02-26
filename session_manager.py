"""
Session and logging management for concurrent callers.
"""

import os, json, re, threading, time, uuid
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

_sessions: dict[str, dict] = {}
_lock = threading.Lock()

PHONE_PATTERN = re.compile(r"(?:\+?92|0)?[\s\-]?3\d{2}[\s\-]?\d{7}")
END_PHRASES = [
    "goodbye", "bye", "no more questions", "end call", "that's all",
    "thank you bye", "thanks bye", "no question", "nothing else",
    "i'm done", "that is all", "hang up", "close the call",
]


def create_session() -> str:
    session_id = uuid.uuid4().hex[:12]
    with _lock:
        _sessions[session_id] = {
            "id": session_id,
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "turns": [],
            "escalated": False,
            "awaiting_phone": False,
            "phone_number": None,
        }
    return session_id


def get_session(session_id: str) -> dict | None:
    with _lock:
        return _sessions.get(session_id)


def add_turn(session_id: str, user_msg: str, agent_reply: str):
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return
        sess["turns"].append({
            "user": user_msg,
            "assistant": agent_reply,
            "timestamp": datetime.utcnow().isoformat(),
        })


def mark_escalated(session_id: str):
    with _lock:
        sess = _sessions.get(session_id)
        if sess:
            sess["escalated"] = True
            sess["awaiting_phone"] = True


def set_awaiting_phone(session_id: str, val: bool):
    with _lock:
        sess = _sessions.get(session_id)
        if sess:
            sess["awaiting_phone"] = val


def is_awaiting_phone(session_id: str) -> bool:
    with _lock:
        sess = _sessions.get(session_id)
        return sess.get("awaiting_phone", False) if sess else False


def extract_phone(text: str) -> str | None:
    m = PHONE_PATTERN.search(text.replace("-", "").replace(" ", ""))
    if m:
        return m.group().strip()
    digits = re.sub(r"\D", "", text)
    if 10 <= len(digits) <= 13:
        return digits
    return None


def save_phone(session_id: str, phone: str):
    with _lock:
        sess = _sessions.get(session_id)
        if sess:
            sess["phone_number"] = phone
            sess["awaiting_phone"] = False
    _write_lead_log(session_id, phone)


def is_end_call(text: str) -> bool:
    text_lower = text.lower().strip()
    return any(phrase in text_lower for phrase in END_PHRASES)


def end_session(session_id: str):
    with _lock:
        sess = _sessions.get(session_id)
        if sess:
            sess["end_time"] = datetime.utcnow().isoformat()
    _write_call_record(session_id)


def get_conversation_history(session_id: str) -> list[dict]:
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return []
        return list(sess["turns"])


def get_metrics(session_id: str) -> dict:
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return {}
        start = datetime.fromisoformat(sess["start_time"])
        end = datetime.fromisoformat(sess["end_time"]) if sess["end_time"] else datetime.utcnow()
        duration = (end - start).total_seconds()
        return {
            "call_duration_seconds": round(duration, 1),
            "total_turns": len(sess["turns"]),
            "escalated": sess["escalated"],
            "phone_captured": sess["phone_number"] is not None,
        }


def _write_lead_log(session_id: str, phone: str):
    sess = _sessions.get(session_id)
    last_query = ""
    if sess and sess["turns"]:
        for t in reversed(sess["turns"]):
            if t.get("user"):
                last_query = t["user"]
                break
    line = f"{datetime.utcnow().isoformat()} | phone={phone} | call_id={session_id} | query={last_query}\n"
    lead_path = os.path.join(LOGS_DIR, "lead_logs.txt")
    with open(lead_path, "a", encoding="utf-8") as f:
        f.write(line)


def _write_call_record(session_id: str):
    with _lock:
        sess = _sessions.get(session_id)
        if not sess:
            return
        record = dict(sess)

    records_path = os.path.join(LOGS_DIR, "call_records.json")
    with _lock:
        records = []
        if os.path.exists(records_path):
            try:
                with open(records_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
            except Exception:
                records = []
        records.append(record)
        with open(records_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
