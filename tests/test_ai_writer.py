import json
from types import SimpleNamespace

import pytest

from app.services import ai_writer


def _fake_response(payload, stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=json.dumps(payload))])


@pytest.fixture()
def fake_claude(app, monkeypatch):
    app.config["ANTHROPIC_API_KEY"] = "test"
    calls = {}

    class Messages:
        def create(self, **kwargs):
            calls.update(kwargs)
            return calls.pop("_response", None) or _fake_response(
                {"suggestions": ["Promo -20% ce week-end ! STOP au 1234", "Bonjour {prenom}, -20% chez nous. Rep STOP pour arreter", "Prix cassés 😀"]}
            )

    monkeypatch.setattr(ai_writer, "_client", lambda: SimpleNamespace(messages=Messages()))
    return calls


def test_suggest_returns_three_with_segments(auth_client, fake_claude):
    resp = auth_client.post("/campaigns/ai-suggest", data={"brief": "Promo pagnes ce week-end"})
    data = resp.get_json()
    assert resp.status_code == 200 and len(data["suggestions"]) == 3
    assert data["suggestions"][0]["segments"] == 1
    assert data["suggestions"][2]["encoding"] != data["suggestions"][0]["encoding"]
    assert fake_claude["output_config"]["format"]["type"] == "json_schema"


def test_suggest_rejects_empty_brief(auth_client, fake_claude):
    resp = auth_client.post("/campaigns/ai-suggest", data={"brief": " "})
    assert resp.status_code == 400


def test_suggest_without_key_is_disabled(app, auth_client):
    app.config["ANTHROPIC_API_KEY"] = None
    resp = auth_client.post("/campaigns/ai-suggest", data={"brief": "Promo pagnes"})
    assert resp.status_code == 400
    assert 'id="ai-btn"' not in auth_client.get("/campaigns/new").data.decode()


def test_form_shows_assistant_when_configured(app, auth_client, fake_claude):
    assert 'id="ai-btn"' in auth_client.get("/campaigns/new").data.decode()


def test_refusal_is_reported(auth_client, fake_claude):
    fake_claude["_response"] = _fake_response({}, stop="refusal")
    resp = auth_client.post("/campaigns/ai-suggest", data={"brief": "Promo pagnes"})
    assert resp.status_code == 400
