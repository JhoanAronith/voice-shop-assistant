"""Unit: when the webhook fires and why a failure must stay silent."""
import httpx
import pytest

import notify


@pytest.fixture
def webhook(monkeypatch):
    monkeypatch.setattr(notify, "NOTIFY_URL", "http://n8n:5678/webhook/reclamo")
    monkeypatch.setattr(notify, "NOTIFY_CATEGORIES", ("reclamo",))


def test_alerts_when_the_category_becomes_a_complaint(webhook):
    assert notify.should_alert("otro", "reclamo") is True
    assert notify.should_alert(None, "reclamo") is True


def test_does_not_repeat_the_alert_on_later_turns(webhook):
    assert notify.should_alert("reclamo", "reclamo") is False


def test_ignores_other_categories(webhook):
    assert notify.should_alert("otro", "precio") is False


def test_stays_off_without_a_url(monkeypatch):
    monkeypatch.setattr(notify, "NOTIFY_URL", "")
    assert notify.enabled() is False
    assert notify.should_alert("otro", "reclamo") is False


def test_alert_posts_the_payload(webhook, monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

    def fake_post(url, json, timeout):
        sent.update(url=url, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(notify.httpx, "post", fake_post)
    assert notify.alert({"conversation_id": 7}) is True
    assert sent == {
        "url": "http://n8n:5678/webhook/reclamo",
        "json": {"conversation_id": 7},
        "timeout": 5,
    }


def test_alert_survives_an_unreachable_webhook(webhook, monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("n8n caído")

    monkeypatch.setattr(notify.httpx, "post", boom)
    assert notify.alert({"conversation_id": 7}) is False
