"""Functional: HTTP endpoints end to end over a temp database, with the AI services mocked."""
import json

import pytest

import api


def parse_sse(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr(api.llm, "stream_reply", lambda history: iter(["El mouse ", "cuesta S/ 149."]))
    monkeypatch.setattr(
        api.llm,
        "classify",
        lambda history: {"category": "precio", "confidence": 0.9, "summary": "Precio del mouse"},
    )


def send(client, message, **extra):
    response = client.post("/api/chat", json={"message": message, **extra})
    assert response.status_code == 200
    return parse_sse(response.text)


def test_pages_and_config_are_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/report").status_code == 200
    assert client.get("/app.js").status_code == 200
    config = client.get("/api/config").json()
    assert "precio" in config["categories"]


def test_health_reports_llm_status(client, monkeypatch):
    monkeypatch.setattr(api.llm, "health", lambda: False)
    assert client.get("/api/health").json() == {"model": False}


def test_chat_streams_persists_and_classifies(client, fake_llm):
    events = send(client, "  ¿cuánto cuesta el mouse?  ", source="audio", audio_seconds=2.5)

    assert [name for name, _ in events] == ["start", "token", "token", "done"]
    cid = events[0][1]["conversation_id"]
    assert events[-1][1] == {
        "conversation_id": cid,
        "category": "precio",
        "category_label": "Precio y ofertas",
        "title": "Precio del mouse",
    }

    messages = client.get(f"/api/conversations/{cid}").json()["messages"]
    assert messages == [
        {"role": "user", "content": "¿cuánto cuesta el mouse?", "source": "audio"},
        {"role": "assistant", "content": "El mouse cuesta S/ 149.", "source": "text"},
    ]
    [item] = client.get("/api/conversations").json()
    assert item["id"] == cid and item["title"] == "Precio del mouse"


def test_chat_continues_an_existing_conversation(client, fake_llm):
    cid = send(client, "hola")[0][1]["conversation_id"]
    events = send(client, "¿y el teclado?", conversation_id=cid)
    assert events[0][1]["conversation_id"] == cid
    assert len(client.get(f"/api/conversations/{cid}").json()["messages"]) == 4


def test_chat_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": "   "}).status_code == 400


def test_chat_reports_llm_failure_as_event(client, monkeypatch):
    def broken(history):
        raise RuntimeError("ollama caído")
        yield  # pragma: no cover

    monkeypatch.setattr(api.llm, "stream_reply", broken)
    events = send(client, "hola")
    assert [name for name, _ in events] == ["start", "error"]
    assert "ollama caído" in events[-1][1]["detail"]


def test_conversation_not_found_and_delete(client, fake_llm):
    assert client.get("/api/conversations/999").status_code == 404
    cid = send(client, "hola")[0][1]["conversation_id"]
    assert client.delete(f"/api/conversations/{cid}").status_code == 204
    assert client.get(f"/api/conversations/{cid}").status_code == 404
    assert client.get("/api/conversations").json() == []


def test_stats_reflect_chat_activity(client, fake_llm):
    send(client, "precio del mouse", source="audio", audio_seconds=30)
    stats = client.get("/api/stats?days=500").json()

    assert stats["days"] == 90  # clamped
    assert stats["totals"]["conversations"] == 1
    assert stats["totals"]["messages"] == 2
    assert stats["totals"]["audio_minutes"] == 0.5
    assert stats["totals"]["messages_per_conversation"] == 2.0
    assert stats["categories"][0]["share"] == 100
    assert stats["products"][0]["sku"] == "MS-041"
    assert stats["inventory"]["out_of_stock"] == 2
    assert "user_texts" not in stats


@pytest.fixture
def complaints(monkeypatch):
    """Classify every turn as a complaint and capture the webhook calls."""
    monkeypatch.setattr(
        api.llm,
        "classify",
        lambda history: {"category": "reclamo", "confidence": 0.87, "summary": "Pedido sin llegar"},
    )
    monkeypatch.setattr(api.notify, "NOTIFY_URL", "http://n8n:5678/webhook/reclamo")
    monkeypatch.setattr(api.notify, "NOTIFY_CATEGORIES", ("reclamo",))
    sent = []
    monkeypatch.setattr(api.notify, "alert", lambda payload: sent.append(payload) or True)
    return sent


def test_complaint_triggers_the_webhook_once(client, fake_llm, complaints):
    cid = send(client, "mi pedido nunca llegó, quiero un reclamo")[0][1]["conversation_id"]

    [payload] = complaints
    assert payload["conversation_id"] == cid
    assert payload["category"] == "reclamo"
    assert payload["category_label"] == "Reclamo"
    assert payload["confidence"] == 0.87
    assert payload["summary"] == "Pedido sin llegar"
    assert payload["store"] == "TecnoStore"
    assert payload["messages"][0] == {
        "role": "user",
        "content": "mi pedido nunca llegó, quiero un reclamo",
    }
    assert payload["messages"][-1]["role"] == "assistant"

    send(client, "sigo esperando", conversation_id=cid)
    assert len(complaints) == 1


def test_other_categories_do_not_trigger_the_webhook(client, fake_llm, monkeypatch):
    monkeypatch.setattr(api.notify, "NOTIFY_URL", "http://n8n:5678/webhook/reclamo")
    sent = []
    monkeypatch.setattr(api.notify, "alert", lambda payload: sent.append(payload) or True)

    send(client, "precio del mouse")
    assert sent == []


def test_chat_works_without_a_webhook_configured(client, fake_llm, monkeypatch):
    monkeypatch.setattr(api.notify, "NOTIFY_URL", "")
    monkeypatch.setattr(
        api.llm,
        "classify",
        lambda history: {"category": "reclamo", "confidence": 0.9, "summary": "Reclamo"},
    )
    events = send(client, "quiero un reclamo")
    assert events[-1][1]["category"] == "reclamo"


def test_report_rows_are_flat_for_spreadsheets(client, fake_llm):
    send(client, "precio del mouse", source="audio", audio_seconds=30)
    [row] = client.get("/api/report").json()

    assert row["messages"] == 2
    assert row["audio_messages"] == 1
    assert row["category"] == "Precio y ofertas"
    assert row["last_message"] == "El mouse cuesta S/ 149."
    assert row["last_message_at"] >= row["started_at"]
    assert isinstance(row["avg_response_seconds"], float)
    assert all(not isinstance(value, dict | list) for value in row.values())


def test_report_days_are_clamped(client, fake_llm):
    send(client, "hola")
    assert len(client.get("/api/report?days=0").json()) == 1
    assert len(client.get("/api/report?days=9999").json()) == 1


def test_transcribe(client, monkeypatch):
    seen = {}

    def fake_transcribe(payload, suffix):
        seen.update(payload=payload, suffix=suffix)
        return {"text": "hola", "language": "es", "duration": 1.2}

    monkeypatch.setattr(api.stt, "transcribe", fake_transcribe)
    response = client.post("/api/transcribe", files={"audio": ("clip.ogg", b"fake-audio", "audio/ogg")})
    assert response.json()["text"] == "hola"
    assert seen == {"payload": b"fake-audio", "suffix": ".ogg"}

    empty = client.post("/api/transcribe", files={"audio": ("clip.webm", b"", "audio/webm")})
    assert empty.status_code == 400


def test_speak(client, monkeypatch):
    monkeypatch.setattr(api.tts, "TTS_ENABLED", True)
    monkeypatch.setattr(api.tts, "speak", lambda text: b"RIFF-fake")
    response = client.post("/api/speak", json={"text": "hola"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF-fake"

    monkeypatch.setattr(api.tts, "TTS_ENABLED", False)
    assert client.post("/api/speak", json={"text": "hola"}).status_code == 503
