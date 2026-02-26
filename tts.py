"""
Text-to-Speech via Edge TTS. Generates MP3 files with unique names per session.
Falls back to silent audio if Edge TTS fails (e.g. on Render).
"""

import os
import uuid
import asyncio

AUDIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE = "en-US-JennyNeural"
SILENT_FILE = "_silent.mp3"
GREETING_FILE = "greeting.mp3"

# Minimal silent MP3 (base64), ~1.5s, no ffmpeg needed
_SILENT_MP3_B64 = (
    "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA/+M4wAAAAAAAAAAAAEluZm8AAAAPAAAAAwAAAbAAqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV////////////////////////////////////////////AAAAAExhdmM1OC4xMwAAAAAAAAAAAAAAACQDkAAAAAAAAAGw9wrNaQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+MYxAAAAANIAAAAAExBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV/+MYxDsAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV/+MYxHYAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
)


def _ensure_silent_audio():
    path = os.path.join(AUDIO_DIR, SILENT_FILE)
    if os.path.isfile(path):
        return "/static/audio/" + SILENT_FILE
    try:
        import base64
        data = base64.b64decode(_SILENT_MP3_B64)
        with open(path, "wb") as f:
            f.write(data)
        return "/static/audio/" + SILENT_FILE
    except Exception as e:
        print("[TTS] Could not create silent audio:", e)
        return None


async def _synthesize_async(text, output_path):
    import edge_tts
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    await communicate.save(output_path)


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    return asyncio.run(coro)


def synthesize(text, session_id=""):
    filename = "{}_{}.mp3".format(session_id, uuid.uuid4().hex[:8])
    output_path = os.path.join(AUDIO_DIR, filename)
    try:
        _run_async(_synthesize_async(text, output_path))
        return "/static/audio/" + filename
    except Exception as e:
        print("[TTS] synthesize failed:", e)
        return _ensure_silent_audio() or "/static/audio/" + GREETING_FILE


def _generate_greeting_mp3():
    path = os.path.join(AUDIO_DIR, GREETING_FILE)
    try:
        _run_async(_synthesize_async(GREETING_TEXT, path))
        return True
    except Exception as e:
        print("[TTS] greeting generation failed:", e)
        try:
            silent_url = _ensure_silent_audio()
            if silent_url:
                import shutil
                silent_path = os.path.join(AUDIO_DIR, SILENT_FILE)
                if os.path.isfile(silent_path):
                    shutil.copy(silent_path, path)
                    return True
        except Exception as e2:
            print("[TTS] silent greeting fallback failed:", e2)
        return False


def ensure_greeting_audio():
    path = os.path.join(AUDIO_DIR, GREETING_FILE)
    if os.path.isfile(path):
        return
    _generate_greeting_mp3()


GREETING_TEXT = "Hello, this is the Institute of Space Technology. How can I help you today?"


def get_greeting(session_id=""):
    path = os.path.join(AUDIO_DIR, GREETING_FILE)
    if os.path.isfile(path):
        return "/static/audio/" + GREETING_FILE
    url = _ensure_silent_audio()
    if url:
        return url
    return "/static/audio/" + GREETING_FILE
