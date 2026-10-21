from app.models.feedback import Feedback


def test_feedback_is_saved(auth_client, db, business):
    resp = auth_client.post("/compte/avis", data={"rating": 4, "message": "Très pratique !"})
    assert resp.status_code == 302
    fb = Feedback.query.one()
    assert fb.rating == 4 and fb.business_id == business.id


def test_feedback_requires_message(auth_client, db):
    auth_client.post("/compte/avis", data={"rating": 4, "message": ""})
    assert Feedback.query.count() == 0


def test_public_pages(client, db):
    for page in ("/impact", "/cgu", "/confidentialite"):
        assert client.get(page).status_code == 200


def test_impact_counts(client, db, business, auth_client):
    auth_client.post("/compte/avis", data={"rating": 5, "message": "Super"})
    body = client.get("/impact").data.decode()
    assert "5.0/5" in body and "Commerces et PME inscrits" in body


def test_cli_impact(app, db, business):
    result = app.test_cli_runner().invoke(args=["impact"])
    assert "businesses" in result.output
