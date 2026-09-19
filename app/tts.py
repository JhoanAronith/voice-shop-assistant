"""Offline text to speech with Piper (ONNX, CPU). The voice is downloaded once."""
import hashlib
import io
import re
import threading
import wave
from pathlib import Path

import httpx

from config import PIPER_VOICE, PIPER_VOICE_URL, TTS_ENABLED

VOICE_DIR = Path("/models/piper")
CACHE_LIMIT = 24

_voice = None
_lock = threading.Lock()
_cache: dict[str, bytes] = {}


def available() -> bool:
    return TTS_ENABLED


def _download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=600) as response:
        response.raise_for_status()
        with open(partial, "wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    partial.rename(target)


def _load():
    global _voice
    if _voice is not None:
        return _voice

    from piper import PiperVoice

    model = VOICE_DIR / f"{PIPER_VOICE}.onnx"
    config = VOICE_DIR / f"{PIPER_VOICE}.onnx.json"
    if not model.exists():
        _download(PIPER_VOICE_URL, model)
    if not config.exists():
        _download(PIPER_VOICE_URL + ".json", config)

    _voice = PiperVoice.load(str(model), config_path=str(config))
    return _voice


def _clean(text: str) -> str:
    """Strip markdown so the voice does not read asterisks and bullets."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = text.replace("S/", "soles ").replace('"', " pulgadas ")
    return re.sub(r"\s+", " ", text).strip()


def speak(text: str) -> bytes:
    """Synthesize a WAV clip; identical requests are served from memory."""
    cleaned = _clean(text)[:1200]
    if not cleaned:
        raise ValueError("Texto vacío")

    key = hashlib.sha1(f"{PIPER_VOICE}:{cleaned}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]

    with _lock:
        voice = _load()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            voice.synthesize(cleaned, handle)
        audio = buffer.getvalue()

    if len(_cache) >= CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = audio
    return audio
