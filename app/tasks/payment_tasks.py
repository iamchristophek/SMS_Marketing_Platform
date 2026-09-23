import logging
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.billing import Payment
from app.services import billing_service
from app.services.payment import get_payment_provider
from app.tasks import celery_app

logger = logging.getLogger("tasks.payment")


@celery_app.task(name="app.tasks.payment_tasks.reconcile_pending_payments")
def reconcile_pending_payments():
    """Filet de sécurité : certains paiements Mobile Money restent bloqués
    en 'pending' si la notification webhook de CinetPay n'arrive jamais
    (perte réseau, timeout côté opérateur...). Cette tâche périodique
    reconterroge activement le fournisseur pour les paiements en attente
    depuis trop longtemps, au lieu de dépendre uniquement du webhook."""
    threshold_minutes = current_app.config.get("PAYMENT_RECONCILE_AFTER_MINUTES", 15)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)

    provider = get_payment_provider()
    # Seuls les paiements du fournisseur actif peuvent être vérifiés auprès
    # de lui ; les paiements « manual » attendent une validation humaine.
    stale_payments = Payment.query.filter(
        Payment.status == Payment.STATUS_PENDING,
        Payment.provider == provider.name,
        Payment.provider != "manual",
        Payment.created_at <= cutoff,
    ).all()

    reconciled = 0
    for payment in stale_payments:
        if not payment.provider_reference:
            continue
        real_status = provider.verify_status(payment.provider_reference)
        if real_status == "success":
            billing_service.complete_payment(
                payment, f"Achat pack « {payment.package.name} » (Mobile Money, réconcilié)"
            )
            reconciled += 1
        elif real_status == "failed":
            billing_service.fail_payment(payment)
            reconciled += 1

    db.session.commit()
    logger.info("Réconciliation paiements : %s/%s traités", reconciled, len(stale_payments))
    return reconciled
