"""Paiement « manual » (validation par un administrateur) et commandes CLI
d'administration."""
import pytest

from app.models.billing import CreditPackage, CreditTransaction, Payment
from app.models.user import Business, User


@pytest.fixture()
def package(db):
    pkg = CreditPackage(name="Starter", credits=500, price_xof=9000, sort_order=1)
    db.session.add(pkg)
    db.session.commit()
    return pkg


@pytest.fixture()
def pending_payment(auth_client, db, package):
    auth_client.post(f"/billing/buy/{package.id}")
    return Payment.query.one()


def test_auto_approve_option_credits_immediately(app, auth_client, db, business, package):
    app.config["MANUAL_PAYMENT_AUTO_APPROVE"] = True
    before = business.credit_balance
    auth_client.post(f"/billing/buy/{package.id}")
    db.session.refresh(business)
    assert business.credit_balance == before + 500
    assert Payment.query.one().status == Payment.STATUS_SUCCESS


def test_production_refuses_auto_approve():
    from app.config import ProductionConfig

    class FakeApp:
        config = {
            "SECRET_KEY": "s" * 64,
            "JWT_SECRET_KEY": "j" * 64,
            "SQLALCHEMY_DATABASE_URI": "postgresql://u:p@db/x",
            "MANUAL_PAYMENT_AUTO_APPROVE": True,
        }

    with pytest.raises(RuntimeError, match="MANUAL_PAYMENT_AUTO_APPROVE"):
        ProductionConfig.init_app(FakeApp())


def test_admin_approves_payment_once(app, db, business, pending_payment):
    runner = app.test_cli_runner()
    before = business.credit_balance

    result = runner.invoke(args=["payments", "approve", str(pending_payment.id)])
    assert result.exit_code == 0, result.output
    db.session.refresh(business)
    assert business.credit_balance == before + 500
    tx = CreditTransaction.query.filter_by(payment_id=pending_payment.id).one()
    assert tx.type == CreditTransaction.TYPE_PURCHASE

    # Une seconde validation ne crédite jamais deux fois.
    again = runner.invoke(args=["payments", "approve", str(pending_payment.id)])
    assert again.exit_code != 0
    db.session.refresh(business)
    assert business.credit_balance == before + 500


def test_admin_rejects_payment(app, db, business, pending_payment):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["payments", "reject", str(pending_payment.id)])
    assert result.exit_code == 0, result.output
    db.session.refresh(pending_payment)
    assert pending_payment.status == Payment.STATUS_FAILED


def test_payments_list_shows_pending(app, pending_payment):
    result = app.test_cli_runner().invoke(args=["payments", "list"])
    assert pending_payment.provider_reference in result.output


def test_client_can_cancel_pending_request(auth_client, db, pending_payment):
    auth_client.post(f"/billing/payments/{pending_payment.id}/cancel")
    db.session.refresh(pending_payment)
    assert pending_payment.status == Payment.STATUS_FAILED


def test_reconciliation_ignores_manual_payments(app, db, business, pending_payment):
    from app.tasks.payment_tasks import reconcile_pending_payments

    app.config["PAYMENT_RECONCILE_AFTER_MINUTES"] = -1
    reconcile_pending_payments()
    db.session.refresh(pending_payment)
    assert pending_payment.status == Payment.STATUS_PENDING


def test_billing_page_without_packages_explains(auth_client):
    resp = auth_client.get("/billing/")
    assert "Aucune offre de recharge".encode() in resp.data


def test_seed_packages(app, db):
    runner = app.test_cli_runner()
    assert "4 pack(s)" in runner.invoke(args=["seed-packages"]).output
    assert CreditPackage.query.count() == 4
    assert "rien à faire" in runner.invoke(args=["seed-packages"]).output


def test_seed_demo_refused_in_production(app, db):
    app.config["ENV"] = "production"
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code != 0
    assert User.query.filter_by(username="demo").first() is None


def test_seed_demo_creates_contacts_and_ledger(app, db):
    result = app.test_cli_runner().invoke(args=["seed-demo"])
    assert result.exit_code == 0, result.output
    demo = User.query.filter_by(username="demo").one()
    assert len(demo.business.contacts) == 3
    assert demo.business.credit_balance == 100
    assert CreditTransaction.query.filter_by(business_id=demo.business_id).one().amount == 100


def test_registration_credits_are_in_ledger(client, db):
    client.post(
        "/register",
        data={
            "business_name": "Maquis Chez Tanti",
            "username": "tanti225",
            "email": "tanti@maquis.ci",
            "password": "Motdepasse1",
            "confirm_password": "Motdepasse1",
        },
    )
    business = Business.query.filter_by(name="Maquis Chez Tanti").one()
    ledger = CreditTransaction.query.filter_by(business_id=business.id).all()
    assert sum(t.amount for t in ledger) == business.credit_balance == 20
    assert ledger[0].type == CreditTransaction.TYPE_BONUS


def test_reset_password(app, db, user):
    result = app.test_cli_runner().invoke(
        args=["reset-password", "testuser", "--password", "NouveauMdp1"]
    )
    assert result.exit_code == 0, result.output
    db.session.refresh(user)
    assert user.check_password("NouveauMdp1")


def test_reset_password_rejects_short_password(app, db, user):
    result = app.test_cli_runner().invoke(args=["reset-password", "testuser", "--password", "court"])
    assert result.exit_code != 0


def test_credits_add_is_journaled(app, db, business, user):
    result = app.test_cli_runner().invoke(
        args=["credits", "add", "testuser", "30", "--reason", "Geste commercial"]
    )
    assert result.exit_code == 0, result.output
    db.session.refresh(business)
    assert business.credit_balance == 80
    assert CreditTransaction.query.filter_by(description="Geste commercial").one().amount == 30
