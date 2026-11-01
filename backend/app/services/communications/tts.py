"""Hindi speech for WhatsApp voice notes and the call greeting: OpenAI TTS, cached on disk by text.

Same prompt text -> same file, so a rehearsed demo plays from cache with no API call."""
import hashlib
import logging
from pathlib import Path

from backend.app.core.config import settings

log = logging.getLogger(__name__)
MODEL = "gpt-4o-mini-tts"
VOICE = "coral"
STYLE = ("Speak natural, warm Hindi like a helpful village extension worker talking to a farmer. "
         "Slow, clear pace; pause briefly before each option number.")


def tts_dir() -> Path:
    d = settings.upload_dir.parent / "tts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def speech(text: str, fmt: str = "opus") -> Path | None:
    """Audio file for text (fmt "opus" = ogg voice note, "mp3" for the call greeting); None when TTS is off."""
    from backend.app.services.vision import openai_llm

    path = tts_dir() / f"{hashlib.sha256(f'{VOICE}|{text}'.encode()).hexdigest()[:20]}.{'ogg' if fmt == 'opus' else fmt}"
    if path.exists():
        return path
    if not openai_llm.api_key():
        return None
    import openai

    try:
        resp = openai.OpenAI(api_key=openai_llm.api_key(), timeout=30).audio.speech.create(
            model=MODEL, voice=VOICE, input=text, instructions=STYLE, response_format=fmt)
        path.write_bytes(resp.content)
    except openai.OpenAIError as exc:   # the text message still goes out
        log.warning("TTS failed: %s", exc)
        return None
    return path
