import secrets

from flask import current_app

from app.services.payment.base import PaymentInitResult, PaymentProvider


class ManualPaymentProvider(PaymentProvider):
    """Paiement hors plateforme, en attendant l'intégration d'une API Mobile
    Money : le client envoie l'argent (Orange Money, MTN MoMo, Moov, Wave,
    virement...) en indiquant la référence du paiement, puis un
    administrateur valide la demande avec `flask payments approve <id>`.

    MANUAL_PAYMENT_AUTO_APPROVE=true crédite immédiatement : réservé aux
    démonstrations et au développement local, jamais en production."""

    name = "manual"

    def initiate(self, payment, notify_url: str, return_url: str) -> PaymentInitResult:
        # Référence courte et lisible, à recopier dans le motif du transfert.
        reference = f"BX{payment.id}-{secrets.token_hex(2).upper()}"
        return PaymentInitResult(
            success=True,
            provider_reference=reference,
            immediate_success=current_app.config.get("MANUAL_PAYMENT_AUTO_APPROVE", False),
        )

    def verify_status(self, provider_reference: str) -> str:
        # Aucune vérification automatique possible : seule la validation
        # d'un administrateur fait passer le paiement en « success ».
        return "pending"
