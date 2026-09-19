"""Unit: classification parsing/fallback and token streaming, with Ollama mocked."""
import json

import pytest

import llm

HISTORY = [
    {"role": "user", "content": "¿Cuánto cuesta el monitor Vista 27?"},
    {"role": "assistant", "content": "Cuesta S/ 999.00."},
]


def test_classify_parses_json_from_model(monkeypatch):
    raw = 'Claro: {"category": "precio", "confidence": 0.9, "summary": "Precio del monitor"}'
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: raw)
    assert llm.classify(HISTORY) == {
        "category": "precio",
        "confidence": 0.9,
        "summary": "Precio del monitor",
    }


@pytest.mark.parametrize(
    "raw",
    [
        "no es json",
        '{"category": "inventada", "confidence": 1}',
        '{"confidence": 0.9}',
        '{"category": "precio", roto}',
    ],
)
def test_classify_falls_back_to_keywords(monkeypatch, raw):
    monkeypatch.setattr(llm, "_chat", lambda *a, **k: raw)
    result = llm.classify(HISTORY)
    assert result["category"] == "precio"
    assert result["confidence"] == 0.4
    assert result["summary"].startswith("¿Cuánto cuesta")


def test_classify_falls_back_when_ollama_is_down(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(llm, "_chat", boom)
    result = llm.classify([{"role": "user", "content": "hola"}])
    assert result["category"] == "otro"
    assert result["confidence"] == 0.2


@pytest.mark.parametrize(
    "text, expected",
    [
        ("mi pedido no llega", "envio"),
        ("la laptop no funciona", "soporte_tecnico"),
        ("tengo una queja", "reclamo"),
        ("quiero comprar", "compra"),
        ("buenas", "otro"),
    ],
)
def test_fallback_category(text, expected):
    assert llm._fallback_category(text)[0] == expected


def test_system_prompt_grounds_on_the_question():
    prompt = llm.system_prompt("tienen router?")
    assert "RT-070" in prompt
    assert "No inventes precios" in prompt


class FakeStream:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        return iter(self.lines)


def test_stream_reply_yields_chunks_until_done(monkeypatch):
    lines = [
        json.dumps({"message": {"content": "Hola"}}),
        "",
        json.dumps({"message": {"content": ", ¿en qué ayudo?"}}),
        json.dumps({"message": {"content": ""}, "done": True}),
        json.dumps({"message": {"content": "ignorado"}}),
    ]
    captured = {}

    def fake_stream(method, url, json, timeout):
        captured["messages"] = json["messages"]
        return FakeStream(lines)

    monkeypatch.setattr(llm.httpx, "stream", fake_stream)
    assert list(llm.stream_reply(HISTORY)) == ["Hola", ", ¿en qué ayudo?"]
    assert captured["messages"][0]["role"] == "system"
    assert "MN-030" in captured["messages"][0]["content"]
    assert captured["messages"][1:] == HISTORY
