import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import pytest

from app.models.billing import CreditPackage, Payment
from app.services.payment.base import PaymentProvider
from app.services.payment.cinetpay_provider import NOTIFICATION_SIGNATURE_FIELDS, CinetPayProvider
from app.tasks.payment_tasks import reconcile_pending_payments


@pytest.fixture()
def package(db):
    pkg = CreditPackage(name="Starter", credits=500, price_xof=9000, sort_order=1)
    db.session.add(pkg)
    db.session.commit()
    return pkg


@pytest.fixture()
def pending_payment(db, business, package):
    payment = Payment(
        business_id=business.id,
        package_id=package.id,
        amount_xof=package.price_xof,
        credits=package.credits,
        provider="cinetpay",
        provider_reference="pmesms-1-1",
        status=Payment.STATUS_PENDING,
    )
    db.session.add(payment)
    db.session.commit()
    return payment


class FakeCinetPayProvider(PaymentProvider):
    name = "cinetpay"

    def __init__(self, status="success", signature_valid=True):
        self.status = status
        self.signature_valid = signature_valid
        self.verify_status_calls = 0

    def initiate(self, payment, notify_url, return_url):
        raise NotImplementedError

    def verify_status(self, provider_reference):
        self.verify_status_calls += 1
        return self.status

    def verify_notification_signature(self, payload, received_token):
        return self.signature_valid


def _patch_provider(monkeypatch, provider):
    monkeypatch.setattr("app.blueprints.webhooks.routes.get_payment_provider", lambda: provider)


# --- CinetPayProvider.verify_notification_signature -------------------


def test_verify_notification_signature_accepts_valid_token():
    provider = CinetPayProvider(api_key="k", site_id="s", secret_key="topsecret")
    payload = {"cpm_site_id": "s", "cpm_trans_id": "t1", "cpm_amount": "9000"}
    data_to_sign = "".join(str(payload.get(f, "")) for f in NOTIFICATION_SIGNATURE_FIELDS)
    token = hmac.new(b"topsecret", data_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    assert provider.verify_notification_signature(payload, token) is True


def test_verify_notification_signature_rejects_wrong_token():
    provider = CinetPayProvider(api_key="k", site_id="s", secret_key="topsecret")
    payload = {"cpm_site_id": "s", "cpm_trans_id": "t1"}
    assert provider.verify_notification_signature(payload, "wrong-token") is False


def test_verify_notification_signature_rejects_missing_token():
    provider = CinetPayProvider(api_key="k", site_id="s", secret_key="topsecret")
    assert provider.verify_notification_signature({"cpm_site_id": "s"}, "") is False


# --- /webhooks/payment/callback ----------------------------------------


def test_webhook_credits_business_on_success(client, db, business, pending_payment, monkeypatch):
    provider = FakeCinetPayProvider(status="success", signature_valid=True)
    _patch_provider(monkeypatch, provider)
    starting_balance = business.credit_balance

    resp = client.post(
        "/webhooks/payment/callback",
        data={"cpm_trans_id": pending_payment.provider_reference},
        headers={"X-TOKEN": "whatever"},
    )

    assert resp.status_code == 200
    db.session.refresh(pending_payment)
    db.session.refresh(business)
    assert pending_payment.status == Payment.STATUS_SUCCESS
    assert business.credit_balance == starting_balance + pending_payment.credits


def test_webhook_duplicate_notification_does_not_double_credit(
    client, db, business, pending_payment, monkeypatch
):
    provider = FakeCinetPayProvider(status="success", signature_valid=True)
    _patch_provider(monkeypatch, provider)
    starting_balance = business.credit_balance

    for _ in range(2):
        resp = client.post(
            "/webhooks/payment/callback",
            data={"cpm_trans_id": pending_payment.provider_reference},
            headers={"X-TOKEN": "whatever"},
        )
        assert resp.status_code == 200

    db.session.refresh(business)
    assert business.credit_balance == starting_balance + pending_payment.credits
    assert provider.verify_status_calls == 1  # 2e appel court-circuité (déjà traité)


def test_webhook_rejects_invalid_signature(client, db, business, pending_payment, monkeypatch):
    provider = FakeCinetPayProvider(status="success", signature_valid=False)
    _patch_provider(monkeypatch, provider)
    starting_balance = business.credit_balance

    resp = client.post(
        "/webhooks/payment/callback",
        data={"cpm_trans_id": pending_payment.provider_reference},
        headers={"X-TOKEN": "bad-token"},
    )

    assert resp.status_code == 400
    db.session.refresh(pending_payment)
    db.session.refresh(business)
    assert pending_payment.status == Payment.STATUS_PENDING
    assert business.credit_balance == starting_balance
    assert provider.verify_status_calls == 0


# --- reconcile_pending_payments (tâche Celery) --------------------------


def test_reconcile_credits_stale_pending_payment(db, business, pending_payment, monkeypatch):
    pending_payment.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    db.session.commit()
    starting_balance = business.credit_balance

    provider = FakeCinetPayProvider(status="success", signature_valid=True)
    monkeypatch.setattr("app.tasks.payment_tasks.get_payment_provider", lambda: provider)

    reconciled = reconcile_pending_payments()

    assert reconciled == 1
    db.session.refresh(pending_payment)
    db.session.refresh(business)
    assert pending_payment.status == Payment.STATUS_SUCCESS
    assert business.credit_balance == starting_balance + pending_payment.credits


def test_reconcile_ignores_recent_pending_payment(db, business, pending_payment, monkeypatch):
    provider = FakeCinetPayProvider(status="success", signature_valid=True)
    monkeypatch.setattr("app.tasks.payment_tasks.get_payment_provider", lambda: provider)

    reconciled = reconcile_pending_payments()

    assert reconciled == 0
    assert provider.verify_status_calls == 0
