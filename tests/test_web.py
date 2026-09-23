import io
from datetime import datetime, timedelta, timezone

import pytest

from app.models.billing import CreditPackage
from app.models.campaign import Campaign
from app.models.contact import Contact, ContactGroup
from app.tasks.sms_tasks import dispatch_scheduled_campaigns


@pytest.mark.parametrize(
    "url",
    [
        "/",
        "/dashboard",
        "/contacts/",
        "/contacts/new",
        "/contacts/groups",
        "/contacts/groups/new",
        "/contacts/import",
        "/campaigns/",
        "/campaigns/new",
        "/billing/",
        "/change-password",
    ],
)
def test_pages_render(auth_client, url):
    assert auth_client.get(url).status_code == 200


def test_unknown_page_returns_404(client):
    assert client.get("/nexiste-pas").status_code == 404


def test_create_contact_normalizes_phone(auth_client, db, business):
    resp = auth_client.post(
        "/contacts/new", data={"first_name": "Awa", "phone": "07 12 34 56 78", "group_id": "0"}
    )
    assert resp.status_code == 302
    contact = Contact.query.filter_by(business_id=business.id).one()
    assert contact.phone_e164 == "+2250712345678"


def test_csv_import_creates_skips_duplicates_and_invalid(auth_client, db, business):
    group = ContactGroup(business_id=business.id, name="VIP")
    db.session.add(group)
    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()

    csv_data = (
        "﻿first_name,last_name,phone,email\n"
        "Koffi,A,0102030405,koffi@example.com\n"
        "Awa,K,07 12 34 56 78,\n"  # doublon
        "Bad,X,123,\n"  # invalide
    ).encode("utf-8")
    resp = auth_client.post(
        "/contacts/import",
        data={"file": (io.BytesIO(csv_data), "contacts.csv"), "group_id": str(group.id)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "1 contact(s) ajouté(s), 1 doublon(s) ignoré(s), 1 numéro(s) invalide(s)" in resp.get_data(
        as_text=True
    )
    koffi = Contact.query.filter_by(phone_e164="+2250102030405").one()
    assert koffi.first_name == "Koffi"
    assert group in koffi.groups


def test_campaign_sent_immediately_from_web(auth_client, db, business):
    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()

    resp = auth_client.post(
        "/campaigns/new",
        data={"name": "Promo", "message": "Promo -20% ce week-end", "group_id": "0", "scheduled_at": ""},
    )
    assert resp.status_code == 302
    campaign = Campaign.query.one()
    assert campaign.status == Campaign.STATUS_SENT
    assert campaign.total_sent == 1
    assert auth_client.get(f"/campaigns/{campaign.id}").status_code == 200
    assert auth_client.get("/dashboard").status_code == 200


def test_dispatch_scheduled_campaigns_sends_due_ones(app, db, business, user):
    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    past = Campaign(
        business_id=business.id, created_by_id=user.id, name="Due", message_body="Bonjour",
        status=Campaign.STATUS_SCHEDULED, scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    future = Campaign(
        business_id=business.id, created_by_id=user.id, name="Later", message_body="Bonjour",
        status=Campaign.STATUS_SCHEDULED, scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db.session.add_all([past, future])
    db.session.commit()

    assert dispatch_scheduled_campaigns() == 1
    db.session.refresh(past)
    db.session.refresh(future)
    assert past.status == Campaign.STATUS_SENT
    assert future.status == Campaign.STATUS_SCHEDULED


def test_buy_package_with_manual_provider(auth_client, db, business):
    package = CreditPackage(name="Starter", credits=500, price_xof=9000, sort_order=1)
    db.session.add(package)
    db.session.commit()
    before = business.credit_balance

    resp = auth_client.post(f"/billing/buy/{package.id}")
    assert resp.status_code == 302
    db.session.refresh(business)
    assert business.credit_balance == before + 500


def test_delete_scheduled_campaign_refunds_and_keeps_ledger(auth_client, db, business, user):
    from app.models.billing import CreditTransaction

    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()
    before = business.credit_balance
    resp = auth_client.post(
        "/campaigns/new",
        data={"name": "Plus tard", "message": "Bonjour", "group_id": "0", "scheduled_at": "2099-01-01T10:00"},
    )
    assert resp.status_code == 302
    campaign = Campaign.query.one()
    assert campaign.status == Campaign.STATUS_SCHEDULED

    # Les clés étrangères sont appliquées (PRAGMA foreign_keys) : sans
    # détachement du journal, la suppression échouerait comme sur PostgreSQL.
    resp = auth_client.post(f"/campaigns/{campaign.id}/delete")
    assert resp.status_code == 302
    assert Campaign.query.count() == 0
    db.session.refresh(business)
    assert business.credit_balance == before
    ledger = CreditTransaction.query.filter_by(business_id=business.id).all()
    assert len(ledger) == 2  # réservation + remboursement conservés
    assert all(t.campaign_id is None for t in ledger)


def test_group_used_by_pending_campaign_cannot_be_deleted(auth_client, db, business, user):
    group = ContactGroup(business_id=business.id, name="VIP")
    db.session.add(group)
    db.session.flush()
    pending = Campaign(
        business_id=business.id, created_by_id=user.id, name="Bientôt", message_body="Bonjour",
        group_id=group.id, status=Campaign.STATUS_SCHEDULED,
    )
    db.session.add(pending)
    db.session.commit()

    auth_client.post(f"/contacts/groups/{group.id}/delete")
    assert db.session.get(ContactGroup, group.id) is not None

    pending.status = Campaign.STATUS_SENT
    db.session.commit()
    resp = auth_client.post(f"/contacts/groups/{group.id}/delete")
    assert resp.status_code == 302
    assert db.session.get(ContactGroup, group.id) is None
    db.session.refresh(pending)
    assert pending.group_id is None


def test_delete_contact_keeps_message_history(auth_client, db, business, user):
    from app.models.campaign import Message

    contact = Contact(business_id=business.id, phone_e164="+2250712345678")
    db.session.add(contact)
    db.session.flush()
    db.session.add(
        Message(business_id=business.id, contact_id=contact.id, phone_e164=contact.phone_e164, body="x")
    )
    db.session.commit()

    assert auth_client.post(f"/contacts/{contact.id}/delete").status_code == 302
    message = Message.query.one()
    assert message.contact_id is None
