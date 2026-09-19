"""Shared fixtures: isolated SQLite per test and no calls to Ollama, Whisper or Piper."""
import os
import sys
import types
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))
os.environ.setdefault("DB_PATH", str(Path(__file__).with_name(".test.db")))

# Whisper is heavy and loads a model on first use; a stub is enough to import stt.
try:
    import faster_whisper  # noqa: F401
except ImportError:
    sys.modules["faster_whisper"] = types.SimpleNamespace(WhisperModel=object)

import db  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "assistant.db"))
    db.init()
    return db


@pytest.fixture
def client(temp_db):
    from fastapi.testclient import TestClient

    import api

    with TestClient(api.app) as test_client:
        yield test_client
