from app.models.campaign import Campaign, Message, compute_sms_segments
from app.models.contact import Contact, ContactGroup
from app.services import campaign_service


def _make_contact(db, business, phone, opted_out=False, group=None):
    contact = Contact(business_id=business.id, phone_e164=phone, opted_out=opted_out)
    if group:
        contact.groups.append(group)
    db.session.add(contact)
    db.session.commit()
    return contact


def test_compute_sms_segments():
    assert compute_sms_segments("") == 0
    assert compute_sms_segments("a" * 160) == 1
    assert compute_sms_segments("a" * 161) == 2
    assert compute_sms_segments("a" * 306) == 2
    assert compute_sms_segments("a" * 307) == 3


def test_get_recipients_excludes_opted_out(app, db, business, user):
    _make_contact(db, business, "+2250712345678")
    _make_contact(db, business, "+2250712345679", opted_out=True)

    campaign = Campaign(
        business_id=business.id, created_by_id=user.id, name="Promo", message_body="Bonjour !"
    )
    db.session.add(campaign)
    db.session.commit()

    recipients = campaign_service.get_recipients(campaign)
    assert len(recipients) == 1
    assert recipients[0].phone_e164 == "+2250712345678"


def test_get_recipients_filters_by_group(app, db, business, user):
    group = ContactGroup(business_id=business.id, name="VIP")
    db.session.add(group)
    db.session.commit()

    _make_contact(db, business, "+2250712345678", group=group)
    _make_contact(db, business, "+2250712345680")  # hors groupe

    campaign = Campaign(
        business_id=business.id,
        created_by_id=user.id,
        name="Promo VIP",
        message_body="Bonjour !",
        group_id=group.id,
    )
    db.session.add(campaign)
    db.session.commit()

    recipients = campaign_service.get_recipients(campaign)
    assert len(recipients) == 1


def test_reserve_credits_debits_business(app, db, business, user):
    _make_contact(db, business, "+2250712345678")
    _make_contact(db, business, "+2250712345679")

    campaign = Campaign(
        business_id=business.id, created_by_id=user.id, name="Promo", message_body="a" * 160
    )
    db.session.add(campaign)
    db.session.commit()

    recipients, cost = campaign_service.reserve_credits(campaign, sms_cost_credits=1)
    db.session.commit()

    assert cost == 2  # 1 segment * 1 crédit * 2 destinataires
    assert business.credit_balance == 48  # 50 - 2


def test_execute_campaign_sends_via_console_provider(app, db, business, user):
    _make_contact(db, business, "+2250712345678")

    campaign = Campaign(
        business_id=business.id, created_by_id=user.id, name="Promo", message_body="Bonjour !"
    )
    db.session.add(campaign)
    db.session.commit()

    campaign_service.reserve_credits(campaign, sms_cost_credits=1)
    campaign.status = Campaign.STATUS_SCHEDULED
    db.session.commit()

    result = campaign_service.execute_campaign(campaign.id, sender_id="PMEPMI", sms_cost_credits=1)

    assert result.status == Campaign.STATUS_SENT
    assert result.total_sent == 1
    assert result.total_failed == 0
    messages = Message.query.filter_by(campaign_id=campaign.id).all()
    assert len(messages) == 1
    assert messages[0].status == Message.STATUS_SENT
    assert messages[0].provider == "console"
