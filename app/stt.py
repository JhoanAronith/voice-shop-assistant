"""Speech-to-text with faster-whisper (CPU, int8)."""
import tempfile
from pathlib import Path

from faster_whisper import WhisperModel

from config import WHISPER_LANG, WHISPER_MODEL

_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            download_root="/models",
        )
    return _model


def transcribe(audio_bytes: bytes, suffix: str = ".wav") -> dict:
    """Return {'text', 'language', 'duration'} for a recorded/uploaded clip."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        segments, info = get_model().transcribe(
            path,
            language=WHISPER_LANG or None,
            vad_filter=True,
            beam_size=1,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        return {
            "text": text,
            "language": info.language,
            "duration": round(float(info.duration), 2),
        }
    finally:
        Path(path).unlink(missing_ok=True)
