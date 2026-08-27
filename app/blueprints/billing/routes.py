from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.billing import billing_bp
from app.extensions import db
from app.models.billing import CreditPackage, CreditTransaction, Payment
from app.services import billing_service
from app.services.payment import get_payment_provider


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
    return render_template(
        "billing/index.html",
        packages=packages,
        transactions=transactions,
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
        payment.status = Payment.STATUS_SUCCESS
        billing_service.credit_purchase(
            current_user.business, package.credits, f"Achat pack « {package.name} »", payment.id
        )
        db.session.commit()
        flash(f"{package.credits} crédits ajoutés à votre compte !", "success")
        return redirect(url_for("billing.index"))

    db.session.commit()
    if result.redirect_url:
        return redirect(result.redirect_url)

    flash("Paiement initié, en attente de confirmation.", "info")
    return redirect(url_for("billing.index"))
