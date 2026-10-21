"""Gestion du solde de crédits SMS. Le registre des transactions
(CreditTransaction) est la source de vérité comptable ; `Business.credit_balance`
est un cache dénormalisé mis à jour de façon atomique à chaque mouvement.
"""
from app.extensions import db
from app.models.billing import CreditTransaction


class InsufficientCreditsError(Exception):
    pass


def get_balance(business) -> int:
    return business.credit_balance


def adjust_credits(
    business,
    amount: int,
    type_: str,
    description: str = "",
    campaign_id: int | None = None,
    payment_id: int | None = None,
    allow_negative: bool = False,
) -> CreditTransaction:
    """Applique un mouvement de crédits (positif ou négatif) et journalise
    la transaction. Lève InsufficientCreditsError si le mouvement rendrait
    le solde négatif (sauf si allow_negative=True, réservé aux corrections
    manuelles par un administrateur)."""
    new_balance = business.credit_balance + amount
    if new_balance < 0 and not allow_negative:
        raise InsufficientCreditsError(
            f"Solde insuffisant : {business.credit_balance} crédits disponibles, "
            f"{-amount} requis."
        )

    business.credit_balance = new_balance
    transaction = CreditTransaction(
        business_id=business.id,
        type=type_,
        amount=amount,
        balance_after=new_balance,
        description=description,
        campaign_id=campaign_id,
        payment_id=payment_id,
    )
    db.session.add(transaction)
    return transaction


def credit_purchase(business, amount: int, description: str, payment_id: int) -> CreditTransaction:
    return adjust_credits(
        business, amount, CreditTransaction.TYPE_PURCHASE, description, payment_id=payment_id
    )


def credit_bonus(business, amount: int, description: str) -> CreditTransaction:
    return adjust_credits(business, amount, CreditTransaction.TYPE_BONUS, description)


def debit_for_campaign(business, amount: int, campaign_id: int, description: str) -> CreditTransaction:
    return adjust_credits(
        business,
        -amount,
        CreditTransaction.TYPE_CONSUMPTION,
        description,
        campaign_id=campaign_id,
    )


def refund_for_campaign(business, amount: int, campaign_id: int, description: str) -> CreditTransaction:
    return adjust_credits(
        business, amount, CreditTransaction.TYPE_REFUND, description, campaign_id=campaign_id
    )


# ---------------------------------------------------------------------------
# Paiements (achat de packs)
# ---------------------------------------------------------------------------
TRANSACTION_LABELS = {
    CreditTransaction.TYPE_PURCHASE: "Achat",
    CreditTransaction.TYPE_CONSUMPTION: "Envoi SMS",
    CreditTransaction.TYPE_REFUND: "Remboursement",
    CreditTransaction.TYPE_BONUS: "Crédits offerts",
}


def complete_payment(payment, description: str | None = None) -> bool:
    """Marque un paiement en attente comme réussi et crédite l'entreprise.
    Idempotent : ne fait rien (et renvoie False) si le paiement n'est plus
    en attente, pour qu'un webhook rejoué, la réconciliation périodique et
    une validation manuelle ne puissent jamais créditer deux fois. Ne fait
    pas le commit : c'est à l'appelant de le faire (verrous, lots)."""
    from datetime import datetime, timezone

    from app.models.billing import Payment

    if payment.status != Payment.STATUS_PENDING:
        return False
    payment.status = Payment.STATUS_SUCCESS
    payment.completed_at = datetime.now(timezone.utc)
    credit_purchase(
        payment.business,
        payment.credits,
        description or f"Achat pack « {payment.package.name} »",
        payment.id,
    )
    return True


def fail_payment(payment) -> bool:
    from datetime import datetime, timezone

    from app.models.billing import Payment

    if payment.status != Payment.STATUS_PENDING:
        return False
    payment.status = Payment.STATUS_FAILED
    payment.completed_at = datetime.now(timezone.utc)
    return True
