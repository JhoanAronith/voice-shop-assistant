"""Unit: persistence of conversations, messages and dashboard aggregates."""


def test_conversation_roundtrip(temp_db):
    cid = temp_db.start_conversation("web")
    temp_db.add_message(cid, "user", "hola", source="audio", audio_seconds=3.0)
    temp_db.add_message(cid, "assistant", "¿en qué ayudo?", latency_ms=500)
    temp_db.set_classification(cid, "otro", 0.8, "Saludo")

    assert temp_db.history(cid) == [
        {"role": "user", "content": "hola", "source": "audio"},
        {"role": "assistant", "content": "¿en qué ayudo?", "source": "text"},
    ]
    [row] = temp_db.recent_conversations()
    assert row["summary"] == "Saludo"
    assert row["first_message"] == "hola"


def test_prune_and_delete(temp_db):
    empty = temp_db.start_conversation("web")
    full = temp_db.start_conversation("web")
    temp_db.add_message(full, "user", "hola")

    temp_db.prune_empty()
    with temp_db.connect() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM conversations")]
    assert ids == [full] and empty not in ids

    temp_db.delete_conversation(full)
    assert temp_db.history(full) == []  # messages go with it (ON DELETE CASCADE)


def test_stats_aggregates(temp_db):
    a = temp_db.start_conversation("web")
    temp_db.add_message(a, "user", "precio del mouse", source="audio", audio_seconds=6)
    temp_db.add_message(a, "assistant", "S/ 149", latency_ms=1000)
    temp_db.set_classification(a, "precio", 0.9, "")
    b = temp_db.start_conversation("web")
    temp_db.add_message(b, "user", "hola")
    temp_db.add_message(b, "assistant", "hola", latency_ms=3000)
    temp_db.start_conversation("web")  # empty: must not be counted

    stats = temp_db.stats(days=7)
    totals = stats["totals"]
    assert totals["conversations"] == 2
    assert totals["messages"] == 4
    assert totals["audio_messages"] == 1
    assert totals["audio_seconds"] == 6
    assert totals["avg_latency_ms"] == 2000
    assert stats["sources"] == {"audio": 1, "text": 1}
    assert {c["category"]: c["total"] for c in stats["categories"]} == {"precio": 1, "otro": 1}
    assert len(stats["hourly"]) == 24
    assert sum(d["messages"] for d in stats["daily"]) == 4
    assert set(stats["user_texts"]) == {"precio del mouse", "hola"}
