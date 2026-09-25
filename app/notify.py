"""Webhook for automations (n8n): fires once, when a conversation turns into a complaint."""
import logging

import httpx

from config import NOTIFY_CATEGORIES, NOTIFY_URL

log = logging.getLogger("uvicorn.error")


def enabled() -> bool:
    return bool(NOTIFY_URL)


def should_alert(previous: str | None, current: str) -> bool:
    return bool(NOTIFY_URL) and current in NOTIFY_CATEGORIES and previous != current


def alert(payload: dict) -> bool:
    """Post the alert; a failure is logged and never breaks the conversation."""
    try:
        httpx.post(NOTIFY_URL, json=payload, timeout=5).raise_for_status()
        return True
    except Exception as exc:
        log.warning("No se pudo avisar de la conversación %s: %s", payload.get("conversation_id"), exc)
        return False
