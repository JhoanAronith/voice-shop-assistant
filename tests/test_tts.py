"""Unit: text cleanup before synthesis and the in-memory clip cache."""
import pytest

import tts


def test_clean_strips_markdown_and_reads_units():
    text = '- **Monitor Vista 27"** a S/ 999\n* stock: 8'
    assert tts._clean(text) == "Monitor Vista 27 pulgadas a soles 999 stock: 8"


def test_speak_rejects_empty_text():
    with pytest.raises(ValueError):
        tts.speak("   \n  ")


def test_speak_caches_identical_requests(monkeypatch):
    calls = []

    class FakeVoice:
        def synthesize(self, text, handle):
            calls.append(text)
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\x00\x00" * 10)

    monkeypatch.setattr(tts, "_load", lambda: FakeVoice())
    monkeypatch.setattr(tts, "_cache", {})

    first = tts.speak("Hola cliente")
    second = tts.speak("Hola cliente")
    assert first == second and first[:4] == b"RIFF"
    assert calls == ["Hola cliente"]
