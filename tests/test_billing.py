import pytest

from app.services import billing_service
from app.services.billing_service import InsufficientCreditsError


def test_credit_purchase_increases_balance(db, business):
    billing_service.credit_purchase(business, 100, "Achat pack Starter", payment_id=None)
    db.session.commit()
    assert business.credit_balance == 150  # 50 initial + 100


def test_debit_for_campaign_decreases_balance(db, business):
    billing_service.debit_for_campaign(business, 20, campaign_id=None, description="Envoi SMS")
    db.session.commit()
    assert business.credit_balance == 30


def test_debit_more_than_balance_raises(db, business):
    with pytest.raises(InsufficientCreditsError):
        billing_service.debit_for_campaign(business, 1000, campaign_id=None, description="Trop cher")


def test_refund_restores_balance(db, business):
    billing_service.debit_for_campaign(business, 20, campaign_id=None, description="Envoi SMS")
    billing_service.refund_for_campaign(business, 20, campaign_id=None, description="Remboursement")
    db.session.commit()
    assert business.credit_balance == 50


def test_transaction_ledger_records_balance_after(db, business):
    tx = billing_service.credit_bonus(business, 5, "Bonus fidélité")
    db.session.commit()
    assert tx.balance_after == 55
    assert tx.amount == 5
