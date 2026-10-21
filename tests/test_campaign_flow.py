"""Parcours campagne : brouillon → aperçu → confirmation, liste figée,
personnalisation, consentement, lignes fixes, annulation."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.campaign import Campaign, Message
from app.models.contact import Contact, ContactGroup
from app.models.template import MessageTemplate
from app.services import campaign_service
from app.services.campaign_service import render_message


def _contact(db, business, phone, **kwargs):
    contact = Contact(business_id=business.id, phone_e164=phone, **kwargs)
    db.session.add(contact)
    db.session.commit()
    return contact


def _draft(auth_client, **data):
    payload = {"name": "Promo", "message": "Bonjour", "group_id": "0", "scheduled_at": ""}
    payload.update(data)
    auth_client.post("/campaigns/new", data=payload)
    return Campaign.query.order_by(Campaign.id.desc()).first()


def test_draft_costs_nothing_until_confirmed(auth_client, db, business):
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client)
    assert campaign.status == Campaign.STATUS_DRAFT
    db.session.refresh(business)
    assert business.credit_balance == 50
    assert Message.query.count() == 0


def test_preview_shows_recipients_cost_and_balance_after(auth_client, db, business):
    _contact(db, business, "+2250712345678", first_name="Koffi")
    _contact(db, business, "+2250512345678", first_name="Aya")
    _contact(db, business, "+2252722334455", first_name="Bureau")  # ligne fixe
    _contact(db, business, "+2250112345678", first_name="Yao", opted_out=True)
    campaign = _draft(auth_client, message="Bonjour {prenom} !")
    html = auth_client.get(f"/campaigns/{campaign.id}/confirm").data.decode()
    assert "Bonjour Koffi !" in html
    assert "1 ligne(s) fixe(s)" in html
    assert "1 désabonné(s)" in html
    estimate = campaign_service.estimate(campaign, 1)
    assert estimate.recipients == 2 and estimate.credits == 2


def test_confirmation_freezes_recipients(auth_client, db, business):
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client, scheduled_at="2099-01-01T10:00")
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    # Contact ajouté APRÈS la confirmation : ni envoyé, ni facturé.
    _contact(db, business, "+2250512345678")

    campaign_service.execute_campaign(campaign.id, "BAORYX", 1)
    db.session.refresh(campaign)
    assert campaign.total_recipients == 1
    assert Message.query.filter_by(campaign_id=campaign.id).count() == 1
    db.session.refresh(business)
    assert business.credit_balance == 49


def test_contact_opting_out_after_confirmation_is_refunded(auth_client, db, business):
    koffi = _contact(db, business, "+2250712345678")
    _contact(db, business, "+2250512345678")
    campaign = _draft(auth_client, scheduled_at="2099-01-01T10:00")
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    koffi.opted_out = True
    db.session.commit()

    campaign_service.execute_campaign(campaign.id, "BAORYX", 1)
    db.session.refresh(campaign)
    assert campaign.total_sent == 1 and campaign.total_failed == 1
    db.session.refresh(business)
    assert business.credit_balance == 49


def test_campaign_without_recipients_cannot_be_confirmed(auth_client, db, business):
    campaign = _draft(auth_client)
    resp = auth_client.post(f"/campaigns/{campaign.id}/confirm", follow_redirects=True)
    assert "Aucun destinataire".encode() in resp.data
    db.session.refresh(campaign)
    assert campaign.status == Campaign.STATUS_DRAFT


def test_insufficient_credits_keeps_draft(auth_client, db, business):
    business.credit_balance = 0
    db.session.commit()
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client)
    resp = auth_client.post(f"/campaigns/{campaign.id}/confirm", follow_redirects=True)
    assert "Solde insuffisant".encode() in resp.data
    db.session.refresh(campaign)
    assert campaign.status == Campaign.STATUS_DRAFT
    assert Message.query.count() == 0


def test_draft_is_never_sent_by_the_worker(app, db, business, user):
    """Un brouillon n'a pas de crédits réservés : l'envoyer serait gratuit."""
    _contact(db, business, "+2250712345678")
    draft = Campaign(business_id=business.id, created_by_id=user.id, name="B", message_body="Bonjour")
    db.session.add(draft)
    db.session.commit()
    assert campaign_service.execute_campaign(draft.id, "BAORYX", 1) is None
    assert Message.query.count() == 0


def test_consent_only_campaign(auth_client, db, business):
    _contact(db, business, "+2250712345678", consent_given=True)
    _contact(db, business, "+2250512345678")
    campaign = _draft(auth_client, consent_only="y")
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    db.session.refresh(campaign)
    assert campaign.total_recipients == 1


def test_group_targeting(auth_client, db, business):
    vip = ContactGroup(business_id=business.id, name="VIP")
    db.session.add(vip)
    member = _contact(db, business, "+2250712345678")
    member.groups.append(vip)
    _contact(db, business, "+2250512345678")
    db.session.commit()
    campaign = _draft(auth_client, group_id=str(vip.id))
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    db.session.refresh(campaign)
    assert campaign.total_recipients == 1


def test_personalised_message_billed_per_recipient(auth_client, db, business):
    _contact(db, business, "+2250712345678", first_name="A")
    _contact(db, business, "+2250512345678", first_name="B" * 80)
    body = "Bonjour {prenom}, " + "x" * 80  # 91 caractères avec « A », 170 avec 80 « B »
    campaign = _draft(auth_client, message=body)
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    db.session.refresh(campaign)
    # 1 SMS pour « A », 2 SMS pour le prénom de 80 caractères.
    assert campaign.credits_reserved == 3
    bodies = {m.body for m in Message.query.all()}
    assert any(b.startswith("Bonjour A,") for b in bodies)


@pytest.mark.parametrize(
    "body,expected",
    [
        ("Bonjour {prenom} !", "Bonjour Koffi !"),
        ("Bonjour {prenom} {nom}", "Bonjour Koffi"),
        ("{Prenom}", "Koffi"),
        ("Code {inconnu}", "Code {inconnu}"),
    ],
)
def test_render_message(body, expected):
    assert render_message(body, Contact(first_name="Koffi", phone_e164="+2250712345678")) == expected


def test_edit_draft_then_confirm(auth_client, db, business):
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client)
    auth_client.post(
        f"/campaigns/{campaign.id}/edit",
        data={"name": "Promo modifiée", "message": "Nouveau texte", "group_id": "0", "scheduled_at": ""},
    )
    db.session.refresh(campaign)
    assert campaign.name == "Promo modifiée" and campaign.status == Campaign.STATUS_DRAFT


def test_cannot_edit_confirmed_campaign(auth_client, db, business):
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client, scheduled_at="2099-01-01T10:00")
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    auth_client.post(
        f"/campaigns/{campaign.id}/edit",
        data={"name": "Piratée", "message": "x", "group_id": "0", "scheduled_at": ""},
    )
    db.session.refresh(campaign)
    assert campaign.name == "Promo"


def test_cancel_twice_refunds_once(auth_client, db, business):
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client, scheduled_at="2099-01-01T10:00")
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    auth_client.post(f"/campaigns/{campaign.id}/cancel")
    auth_client.post(f"/campaigns/{campaign.id}/cancel")
    db.session.refresh(business)
    assert business.credit_balance == 50


def test_duplicate_creates_draft(auth_client, db, business):
    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client)
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    auth_client.post(f"/campaigns/{campaign.id}/duplicate")
    copy = Campaign.query.order_by(Campaign.id.desc()).first()
    assert copy.id != campaign.id and copy.status == Campaign.STATUS_DRAFT
    assert copy.message_body == campaign.message_body


def test_detail_lists_messages_with_french_status(auth_client, db, business):
    _contact(db, business, "+2250712345678", first_name="Koffi")
    campaign = _draft(auth_client)
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    html = auth_client.get(f"/campaigns/{campaign.id}").data.decode()
    assert "Koffi" in html and "Envoyé" in html and "Envoyée" in html


def test_new_campaign_from_template(auth_client, db, business):
    template = MessageTemplate(
        business_id=business.id, name="Promo", category="promotional", body="Promo du jour {prenom}"
    )
    db.session.add(template)
    db.session.commit()
    html = auth_client.get(f"/campaigns/new?template={template.id}").data.decode()
    assert "Promo du jour {prenom}" in html


def test_scheduled_campaign_sent_when_due(app, auth_client, db, business):
    from app.tasks.sms_tasks import dispatch_scheduled_campaigns

    _contact(db, business, "+2250712345678")
    campaign = _draft(auth_client, scheduled_at="2099-01-01T10:00")
    auth_client.post(f"/campaigns/{campaign.id}/confirm")
    campaign.scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    dispatch_scheduled_campaigns()
    db.session.refresh(campaign)
    assert campaign.status == Campaign.STATUS_SENT
