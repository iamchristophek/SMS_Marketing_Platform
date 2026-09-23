from app.models.campaign import Campaign, Message
from app.models.contact import Contact


def _sent_message(db, business, user, provider_message_id="prov-1"):
    campaign = Campaign(
        business_id=business.id, created_by_id=user.id, name="Promo", message_body="Bonjour",
        status=Campaign.STATUS_SENT, total_sent=1,
    )
    db.session.add(campaign)
    db.session.flush()
    message = Message(
        campaign_id=campaign.id, business_id=business.id, phone_e164="+2250712345678",
        body="Bonjour", status=Message.STATUS_SENT, provider_message_id=provider_message_id,
    )
    db.session.add(message)
    db.session.commit()
    return campaign, message


def test_delivery_report_marks_message_delivered_once(client, db, business, user):
    campaign, message = _sent_message(db, business, user)

    for _ in range(2):  # accusé rejoué par le fournisseur
        resp = client.post("/webhooks/sms/delivery-report", data={"id": "prov-1", "status": "Success"})
        assert resp.status_code == 200

    db.session.refresh(message)
    db.session.refresh(campaign)
    assert message.status == Message.STATUS_DELIVERED
    assert message.delivered_at is not None
    assert campaign.total_delivered == 1


def test_delivery_report_failure_with_null_reason(client, db, business, user):
    campaign, message = _sent_message(db, business, user)
    resp = client.post(
        "/webhooks/sms/delivery-report",
        json={"id": "prov-1", "status": "Failed", "failureReason": None},
    )
    assert resp.status_code == 200
    db.session.refresh(message)
    assert message.status == Message.STATUS_UNDELIVERED


def test_delivery_report_requires_id(client):
    assert client.post("/webhooks/sms/delivery-report", json={"status": "Success"}).status_code == 400


def test_delivery_report_unknown_message_is_ignored(client):
    resp = client.post("/webhooks/sms/delivery-report", json={"id": "inconnu", "status": "Success"})
    assert resp.status_code == 200


def test_inbound_stop_opts_out_contact_whatever_the_number_format(client, db, business):
    contact = Contact(business_id=business.id, phone_e164="+2250712345678")
    db.session.add(contact)
    db.session.commit()

    resp = client.post("/webhooks/sms/inbound", data={"from": "2250712345678", "text": " stop "})
    assert resp.status_code == 200
    db.session.refresh(contact)
    assert contact.opted_out is True
    assert contact.opted_out_at is not None


def test_payment_callback_unknown_reference(client):
    resp = client.post("/webhooks/payment/callback", data={"transaction_id": "nope"})
    assert resp.status_code == 200
    assert client.post("/webhooks/payment/callback", data={}).status_code == 400
