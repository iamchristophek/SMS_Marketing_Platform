from datetime import datetime, timedelta, timezone

from app.models.campaign import Message
from app.models.contact import Contact
from app.services import billing_service, stats_service


def _sent(db, business, days_ago=0, status=Message.STATUS_SENT):
    message = Message(
        business_id=business.id, phone_e164="+2250712345678", body="x", status=status,
        sent_at=datetime.now(timezone.utc) - timedelta(days=days_ago), credits_used=1,
    )
    db.session.add(message)
    db.session.commit()
    return message


def test_month_figures_and_credits_net_of_refunds(db, business):
    _sent(db, business)
    _sent(db, business)
    billing_service.debit_for_campaign(business, 10, None, "Réservation")
    billing_service.refund_for_campaign(business, 4, None, "Remboursement")
    db.session.commit()

    stats = stats_service.dashboard_stats(business.id)
    assert stats.sms_sent_month == 2
    assert stats.credits_used_month == 6


def test_daily_activity_covers_30_days(db, business):
    _sent(db, business, days_ago=0)
    _sent(db, business, days_ago=0)
    _sent(db, business, days_ago=3)
    _sent(db, business, days_ago=45)  # hors fenêtre

    daily = stats_service.daily_sent(business.id)
    assert len(daily) == 30
    assert daily[-1][1] == 2
    assert daily[-4][1] == 1
    assert sum(n for _, n in daily) == 3


def test_operator_breakdown(db, business):
    for phone in ["+2250712345678", "+2250712345679", "+2250512345678", "+2252722334455"]:
        db.session.add(Contact(business_id=business.id, phone_e164=phone))
    db.session.add(Contact(business_id=business.id, phone_e164="+2250112345678", opted_out=True))
    db.session.commit()
    breakdown = {label: (n, pct) for label, n, pct in stats_service.operator_breakdown(business.id)}
    assert breakdown == {"Orange": (2, 50), "MTN": (1, 25), "Ligne fixe": (1, 25)}


def test_delivery_rate_hidden_without_reports(db, business):
    _sent(db, business)
    assert stats_service.dashboard_stats(business.id).delivery_rate is None
    _sent(db, business, status=Message.STATUS_DELIVERED)
    _sent(db, business, status=Message.STATUS_UNDELIVERED)
    assert stats_service.dashboard_stats(business.id).delivery_rate == 50.0


def test_nice_ticks():
    assert stats_service.nice_ticks(0) == [0, 1]
    assert stats_service.nice_ticks(3) == [0, 1, 2, 3]
    assert stats_service.nice_ticks(7) == [0, 2, 4, 6, 8]
    assert stats_service.nice_ticks(1234)[-1] >= 1234


def test_dashboard_renders_chart_and_onboarding(auth_client, db, business):
    html = auth_client.get("/dashboard").data.decode()
    assert "Bien démarrer" in html
    assert "Aucun SMS envoyé ces 30 derniers jours" in html

    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()
    _sent(db, business)
    html = auth_client.get("/dashboard").data.decode()
    assert 'class="bar"' in html and "Voir les données sous forme de tableau" in html
    assert "Orange" in html


def test_low_balance_threshold_is_configurable(app, auth_client, business):
    app.config["LOW_BALANCE_THRESHOLD"] = 10  # solde de test : 50
    assert "Votre solde est faible".encode() not in auth_client.get("/dashboard").data
    app.config["LOW_BALANCE_THRESHOLD"] = 100
    assert "Votre solde est faible".encode() in auth_client.get("/dashboard").data
