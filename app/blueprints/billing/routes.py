from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.billing import billing_bp
from app.extensions import db
from app.models.billing import CreditPackage, CreditTransaction, Payment
from app.services import billing_service
from app.services.payment import get_payment_provider


def _manual_instructions(payment):
    template = current_app.config.get("MANUAL_PAYMENT_INSTRUCTIONS", "")
    montant = f"{payment.amount_xof:,}".replace(",", " ")
    return template.replace("{montant}", montant).replace("{reference}", payment.provider_reference or "")


@billing_bp.route("/")
@login_required
def index():
    packages = CreditPackage.query.filter_by(is_active=True).order_by(CreditPackage.sort_order).all()
    transactions = (
        CreditTransaction.query.filter_by(business_id=current_user.business_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(30)
        .all()
    )
    pending_payments = (
        Payment.query.filter_by(business_id=current_user.business_id, status=Payment.STATUS_PENDING)
        .order_by(Payment.created_at.desc())
        .all()
    )
    return render_template(
        "billing/index.html",
        packages=packages,
        transactions=transactions,
        pending_payments=[(p, _manual_instructions(p) if p.provider == "manual" else None) for p in pending_payments],
        transaction_labels=billing_service.TRANSACTION_LABELS,
        balance=current_user.business.credit_balance,
    )


@billing_bp.route("/buy/<int:package_id>", methods=["POST"])
@login_required
def buy(package_id):
    package = CreditPackage.query.filter_by(id=package_id, is_active=True).first_or_404()

    payment = Payment(
        business_id=current_user.business_id,
        package_id=package.id,
        amount_xof=package.price_xof,
        credits=package.credits,
        provider="",
        status=Payment.STATUS_PENDING,
    )
    db.session.add(payment)
    db.session.flush()

    provider = get_payment_provider()
    payment.provider = provider.name

    result = provider.initiate(
        payment,
        notify_url=url_for("webhooks.payment_callback", _external=True),
        return_url=url_for("billing.index", _external=True),
    )
    payment.provider_reference = result.provider_reference

    if not result.success:
        payment.status = Payment.STATUS_FAILED
        db.session.commit()
        flash(f"Échec du paiement : {result.error}", "error")
        return redirect(url_for("billing.index"))

    if result.immediate_success:
        billing_service.complete_payment(payment)
        db.session.commit()
        flash(f"{package.credits} crédits ajoutés à votre compte !", "success")
        return redirect(url_for("billing.index"))

    db.session.commit()
    if result.redirect_url:
        return redirect(result.redirect_url)

    if provider.name == "manual":
        flash(f"Demande d'achat enregistrée. {_manual_instructions(payment)}", "info")
    else:
        flash("Paiement initié, en attente de confirmation.", "info")
    return redirect(url_for("billing.index"))


@billing_bp.route("/payments/<int:payment_id>/cancel", methods=["POST"])
@login_required
def cancel_payment(payment_id):
    """Le client annule une demande d'achat manuelle qu'il n'a pas payée."""
    payment = Payment.query.filter_by(
        id=payment_id, business_id=current_user.business_id
    ).first_or_404()
    if payment.provider != "manual" or not billing_service.fail_payment(payment):
        flash("Cette demande ne peut plus être annulée.", "error")
    else:
        db.session.commit()
        flash("Demande d'achat annulée.", "info")
    return redirect(url_for("billing.index"))
