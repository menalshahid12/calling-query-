"""
Text-to-Speech via Edge TTS. Generates MP3 files with unique names per session.
"""

import os, uuid, asyncio

AUDIO_DIR = os.path.join(os.path.dirname(__file__), "static", "audio")
os.makedirs(AUDIO_DIR, exist_ok=True)

VOICE = "en-US-JennyNeural"


async def _synthesize(text: str, output_path: str):
    import edge_tts

    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    await communicate.save(output_path)


def synthesize(text: str, session_id: str = "") -> str:
    filename = f"{session_id}_{uuid.uuid4().hex[:8]}.mp3"
    output_path = os.path.join(AUDIO_DIR, filename)

    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _synthesize(text, output_path))
            future.result(timeout=30)
    else:
        asyncio.run(_synthesize(text, output_path))

    return f"/static/audio/{filename}"


GREETING_TEXT = "Hello, this is the Institute of Space Technology. How can I help you today?"


def get_greeting(session_id: str = "") -> str:
    return synthesize(GREETING_TEXT, session_id)
