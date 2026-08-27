import uuid

from app.services.payment.base import PaymentInitResult, PaymentProvider


class ManualPaymentProvider(PaymentProvider):
    """Fournisseur par défaut pour le développement et la phase pilote :
    aucune intégration Mobile Money réelle, le paiement est validé
    immédiatement (utile pour les démonstrations, ou en attendant la
    signature d'un contrat avec un agrégateur Mobile Money local)."""

    name = "manual"

    def initiate(self, payment, notify_url: str, return_url: str) -> PaymentInitResult:
        return PaymentInitResult(
            success=True,
            provider_reference=f"manual-{uuid.uuid4().hex[:16]}",
            immediate_success=True,
        )

    def verify_status(self, provider_reference: str) -> str:
        return "success"
