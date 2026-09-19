"""SQLite persistence for conversations and messages."""
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    category     TEXT NOT NULL DEFAULT 'otro',
    confidence   REAL NOT NULL DEFAULT 0.0,
    summary      TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'text',
    language        TEXT,
    audio_seconds   REAL,
    latency_ms      INTEGER,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def start_conversation(session_id: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (session_id, started_at, updated_at) VALUES (?, ?, ?)",
            (session_id, _now(), _now()),
        )
        return int(cur.lastrowid)


def add_message(
    conversation_id: int,
    role: str,
    content: str,
    source: str = "text",
    language: str | None = None,
    audio_seconds: float | None = None,
    latency_ms: int | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO messages
               (conversation_id, role, content, source, language, audio_seconds, latency_ms, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (conversation_id, role, content, source, language, audio_seconds, latency_ms, _now()),
        )
        conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), conversation_id))


def set_classification(conversation_id: int, category: str, confidence: float, summary: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE conversations SET category = ?, confidence = ?, summary = ?, updated_at = ? WHERE id = ?",
            (category, confidence, summary, _now(), conversation_id),
        )


def history(conversation_id: int) -> list[dict]:
    """Messages of one conversation, ready to feed back into the model."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, source FROM messages WHERE conversation_id = ? ORDER BY id",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def recent_conversations(limit: int = 50) -> list[dict]:
    """Non-empty conversations, newest first, with a label for the history list."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.category, c.summary, c.updated_at,
                      (SELECT m.content FROM messages m
                        WHERE m.conversation_id = c.id AND m.role = 'user'
                        ORDER BY m.id LIMIT 1) AS first_message
               FROM conversations c
               WHERE EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)
               ORDER BY c.updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def prune_empty() -> None:
    """Drop conversations that never received a message."""
    with connect() as conn:
        conn.execute(
            "DELETE FROM conversations WHERE NOT EXISTS "
            "(SELECT 1 FROM messages m WHERE m.conversation_id = conversations.id)"
        )


def delete_conversation(conversation_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


NON_EMPTY = "EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id)"


def report(days: int = 30) -> list[dict]:
    """One row per conversation for the external report: volume, audio, latency and last message."""
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT c.id,
                       c.started_at,
                       c.category,
                       (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id)       AS messages,
                       (SELECT COUNT(*) FROM messages m
                         WHERE m.conversation_id = c.id AND m.source = 'audio')                AS audio_messages,
                       (SELECT AVG(m.latency_ms) FROM messages m
                         WHERE m.conversation_id = c.id AND m.latency_ms > 0)                  AS avg_latency_ms,
                       (SELECT m.content FROM messages m
                         WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1)            AS last_message,
                       (SELECT m.created_at FROM messages m
                         WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1)            AS last_message_at
                FROM conversations c
                WHERE {NON_EMPTY} AND date(c.started_at) >= date('now', ?)
                ORDER BY c.started_at""",
            (f"-{max(days - 1, 0)} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def stats(days: int = 14) -> dict:
    """Aggregates for the dashboard: totals, categories, activity and history."""
    with connect() as conn:
        totals = dict(
            conn.execute(
                f"""SELECT
                      (SELECT COUNT(*) FROM conversations c WHERE {NON_EMPTY})        AS conversations,
                      (SELECT COUNT(*) FROM messages)                                 AS messages,
                      (SELECT COUNT(*) FROM messages WHERE role = 'user')             AS user_messages,
                      (SELECT COUNT(*) FROM messages WHERE source = 'audio')          AS audio_messages,
                      (SELECT COALESCE(SUM(audio_seconds), 0) FROM messages)          AS audio_seconds,
                      (SELECT AVG(latency_ms) FROM messages WHERE latency_ms > 0)      AS avg_latency_ms,
                      (SELECT AVG(confidence) FROM conversations WHERE confidence > 0) AS avg_confidence"""
            ).fetchone()
        )

        categories = [
            dict(r)
            for r in conn.execute(
                f"""SELECT c.category, COUNT(*) AS total, AVG(c.confidence) AS confidence
                    FROM conversations c WHERE {NON_EMPTY}
                    GROUP BY c.category ORDER BY total DESC, c.category"""
            ).fetchall()
        ]

        daily = [
            dict(r)
            for r in conn.execute(
                """SELECT date(created_at) AS day,
                          COUNT(*) AS messages,
                          COUNT(DISTINCT conversation_id) AS conversations
                   FROM messages
                   WHERE date(created_at) >= date('now', ?)
                   GROUP BY day ORDER BY day""",
                (f"-{max(days - 1, 0)} days",),
            ).fetchall()
        ]

        hourly = {
            int(r["hour"]): r["total"]
            for r in conn.execute(
                "SELECT strftime('%H', created_at) AS hour, COUNT(*) AS total "
                "FROM messages GROUP BY hour"
            ).fetchall()
        }

        sources = {
            r["source"]: r["total"]
            for r in conn.execute(
                "SELECT source, COUNT(*) AS total FROM messages WHERE role = 'user' GROUP BY source"
            ).fetchall()
        }

        recent = [
            dict(r)
            for r in conn.execute(
                f"""SELECT c.id, c.category, c.confidence, c.summary, c.started_at, c.updated_at,
                           (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS messages,
                           (SELECT COUNT(*) FROM messages m
                             WHERE m.conversation_id = c.id AND m.source = 'audio')         AS audio_messages,
                           (SELECT m.content FROM messages m
                             WHERE m.conversation_id = c.id AND m.role = 'user'
                             ORDER BY m.id LIMIT 1)                                         AS first_message
                    FROM conversations c WHERE {NON_EMPTY}
                    ORDER BY c.updated_at DESC LIMIT 12"""
            ).fetchall()
        ]

        user_texts = [
            r["content"]
            for r in conn.execute(
                "SELECT content FROM messages WHERE role = 'user' ORDER BY id DESC LIMIT 5000"
            ).fetchall()
        ]

    return {
        "totals": totals,
        "categories": categories,
        "daily": daily,
        "hourly": [{"hour": h, "total": hourly.get(h, 0)} for h in range(24)],
        "sources": sources,
        "recent": recent,
        "user_texts": user_texts,
    }
