from app.models.api_key import ApiKey
from app.models.campaign import Campaign, Message
from app.models.contact import Contact


def _token(client):
    resp = client.post("/api/v1/auth/token", json={"username": "testuser", "password": "Password123!"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_token_with_bad_credentials_is_rejected(client, user):
    resp = client.post("/api/v1/auth/token", json={"username": "testuser", "password": "nope"})
    assert resp.status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/api/v1/me").status_code == 401


def test_me_with_jwt(client, user, business):
    resp = client.get("/api/v1/me", headers=_token(client))
    assert resp.status_code == 200
    assert resp.get_json()["credit_balance"] == business.credit_balance


def test_me_with_api_key(client, db, business):
    api_key, raw_key = ApiKey.generate(business.id, "ERP")
    db.session.add(api_key)
    db.session.commit()

    resp = client.get("/api/v1/me", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
    assert resp.get_json()["business_id"] == business.id
    assert db.session.get(ApiKey, api_key.id).last_used_at is not None


def test_send_single_sms_debits_credits(client, db, user, business):
    before = business.credit_balance
    resp = client.post(
        "/api/v1/sms/send",
        headers=_token(client),
        json={"to": "07 12 34 56 78", "message": "Votre commande est prête."},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["status"] == Message.STATUS_SENT
    assert data["credits_used"] == 1

    message = db.session.get(Message, data["id"])
    assert message.phone_e164 == "+2250712345678"
    assert message.provider_message_id
    db.session.refresh(business)
    assert business.credit_balance == before - 1


def test_send_single_sms_validates_input(client, user):
    headers = _token(client)
    assert client.post("/api/v1/sms/send", headers=headers, json={"to": "0712345678"}).status_code == 400
    assert (
        client.post("/api/v1/sms/send", headers=headers, json={"to": "123", "message": "x"}).status_code
        == 400
    )


def test_send_single_sms_insufficient_credits(client, db, user, business):
    business.credit_balance = 0
    db.session.commit()
    resp = client.post(
        "/api/v1/sms/send", headers=_token(client), json={"to": "0712345678", "message": "Bonjour"}
    )
    assert resp.status_code == 402
    assert Message.query.count() == 0


def test_create_campaign_via_api_sends_immediately(client, db, user, business):
    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()

    resp = client.post(
        "/api/v1/campaigns", headers=_token(client), json={"name": "Promo", "message": "Promo -20%"}
    )
    assert resp.status_code == 201
    campaign = db.session.get(Campaign, resp.get_json()["id"])
    assert campaign.status == Campaign.STATUS_SENT
    assert campaign.total_sent == 1


def test_create_campaign_with_api_key_and_no_owner_returns_409(client, db, business):
    api_key, raw_key = ApiKey.generate(business.id, "ERP")
    db.session.add(api_key)
    db.session.commit()

    resp = client.post(
        "/api/v1/campaigns", headers={"X-API-Key": raw_key}, json={"name": "Promo", "message": "Bonjour"}
    )
    assert resp.status_code == 409
    assert "error" in resp.get_json()
    assert Campaign.query.count() == 0


def test_create_campaign_with_api_key_uses_owner_as_author(client, db, user, business):
    api_key, raw_key = ApiKey.generate(business.id, "ERP")
    db.session.add(api_key)
    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()

    resp = client.post(
        "/api/v1/campaigns", headers={"X-API-Key": raw_key}, json={"name": "Promo", "message": "Bonjour"}
    )
    assert resp.status_code == 201
    assert db.session.get(Campaign, resp.get_json()["id"]).created_by_id == user.id


def test_api_key_prefix_fits_column():
    # key_prefix était String(10) alors que le préfixe fait 14 caractères :
    # erreur à l'insertion sur PostgreSQL (SQLite ignore la longueur).
    api_key, raw_key = ApiKey.generate(1, "ERP")
    assert raw_key.startswith(api_key.key_prefix)
    assert len(api_key.key_prefix) <= ApiKey.__table__.c.key_prefix.type.length


def test_api_rejects_values_longer_than_columns(client, user):
    headers = _token(client)
    resp = client.post(
        "/api/v1/contacts", headers=headers, json={"phone": "0712345678", "first_name": "x" * 81}
    )
    assert resp.status_code == 400
    resp = client.post("/api/v1/campaigns", headers=headers, json={"name": "x" * 121, "message": "Bonjour"})
    assert resp.status_code == 400
    assert Campaign.query.count() == 0


def test_create_campaign_without_recipients_is_refused(client, db, user, business):
    resp = client.post(
        "/api/v1/campaigns", headers=_token(client), json={"name": "Promo", "message": "Bonjour"}
    )
    assert resp.status_code == 422
    assert "Aucun destinataire" in resp.get_json()["error"]
    assert Campaign.query.count() == 0
    db.session.refresh(business)
    assert business.credit_balance == 50


def test_create_campaign_invalid_date_reserves_nothing(client, db, user, business):
    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()
    resp = client.post(
        "/api/v1/campaigns", headers=_token(client),
        json={"name": "Promo", "message": "Bonjour", "scheduled_at": "demain"},
    )
    assert resp.status_code == 400
    db.session.refresh(business)
    assert business.credit_balance == 50
