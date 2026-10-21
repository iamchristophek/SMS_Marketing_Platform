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


class _FlakyProvider:
    """Fournisseur qui lève une exception (panne réseau) sur certains appels."""

    name = "flaky"

    def __init__(self, fail_calls):
        self.fail_calls = set(fail_calls)
        self.calls = []

    def send(self, to, body, sender_id):
        from app.services.sms.base import SmsSendResult

        self.calls.append(to)
        if len(self.calls) in self.fail_calls:
            raise ConnectionError("réseau indisponible")
        return SmsSendResult(success=True, provider="flaky", provider_message_id=f"id-{len(self.calls)}")


def _scheduled_campaign(db, business, user):
    campaign = Campaign(
        business_id=business.id, created_by_id=user.id, name="Promo", message_body="Bonjour !"
    )
    db.session.add(campaign)
    db.session.commit()
    campaign_service.reserve_credits(campaign, sms_cost_credits=1)
    campaign.status = Campaign.STATUS_SCHEDULED
    db.session.commit()
    return campaign


def test_send_campaign_retry_resumes_without_resending(app, db, business, user, monkeypatch):
    from app.tasks.sms_tasks import send_campaign

    _make_contact(db, business, "+2250712345678")
    _make_contact(db, business, "+2250712345679")
    campaign = _scheduled_campaign(db, business, user)
    provider = _FlakyProvider(fail_calls={2})  # le 2e envoi échoue une fois
    monkeypatch.setattr(campaign_service, "get_sms_provider", lambda: provider)

    send_campaign.delay(campaign.id)

    db.session.refresh(campaign)
    assert campaign.status == Campaign.STATUS_SENT
    assert campaign.total_sent == 2
    assert Message.query.filter_by(campaign_id=campaign.id).count() == 2
    # 1er contact envoyé une seule fois, 2e contact : échec puis succès.
    assert provider.calls.count("+2250712345678") == 1
    assert len(provider.calls) == 3


def test_send_campaign_final_failure_refunds_credits(app, db, business, user, monkeypatch):
    from app.tasks.sms_tasks import send_campaign

    _make_contact(db, business, "+2250712345678")
    balance_before = business.credit_balance
    campaign = _scheduled_campaign(db, business, user)
    assert business.credit_balance == balance_before - 1
    provider = _FlakyProvider(fail_calls=range(1, 100))  # panne permanente
    monkeypatch.setattr(campaign_service, "get_sms_provider", lambda: provider)

    try:
        send_campaign.delay(campaign.id)
    except ConnectionError:
        pass  # en mode eager, l'exception finale remonte à l'appelant

    db.session.refresh(campaign)
    db.session.refresh(business)
    assert campaign.status == Campaign.STATUS_FAILED
    assert business.credit_balance == balance_before
    assert len(provider.calls) == 1 + send_campaign.max_retries


def test_execute_campaign_is_not_run_twice(app, db, business, user):
    _make_contact(db, business, "+2250712345678")
    campaign = _scheduled_campaign(db, business, user)

    campaign_service.execute_campaign(campaign.id, sender_id="PMEPMI", sms_cost_credits=1)
    assert campaign_service.execute_campaign(campaign.id, sender_id="PMEPMI", sms_cost_credits=1) is None
    assert Message.query.filter_by(campaign_id=campaign.id).count() == 1


def test_accented_message_is_billed_as_ucs2():
    from app.services.sms.encoding import analyze_message

    info = analyze_message("Réduction ça vaut le coup")
    assert info.encoding == "UCS-2"
    assert info.non_gsm_chars == ("ç",)
    # 71 caractères avec un « ç » : 2 SMS en UCS-2 (1 seul en GSM-7).
    assert compute_sms_segments("ç" + "a" * 70) == 2
    assert compute_sms_segments("ç" + "a" * 69) == 1
    assert compute_sms_segments("ç" + "a" * 134) == 3


def test_gsm7_extension_characters_count_double():
    assert compute_sms_segments("€" * 80) == 1
    assert compute_sms_segments("€" * 81) == 2


def test_common_french_accents_stay_gsm7():
    from app.services.sms.encoding import analyze_message

    # é, è, à, ù sont dans l'alphabet GSM : pas de surcoût.
    assert analyze_message("Été à Abidjan : -20% où vous voulez").encoding == "GSM-7"


def test_emoji_counts_as_two_ucs2_units():
    from app.services.sms.encoding import analyze_message

    assert analyze_message("🙏").length == 2


def test_campaign_reservation_uses_ucs2_segments(app, db, business, user):
    _make_contact(db, business, "+2250712345678")
    campaign = Campaign(
        business_id=business.id, created_by_id=user.id, name="Promo", message_body="ç" + "a" * 70
    )
    db.session.add(campaign)
    db.session.commit()
    _, cost = campaign_service.reserve_credits(campaign, sms_cost_credits=1)
    assert cost == 2
