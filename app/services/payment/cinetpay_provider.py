import logging

import requests

from app.services.payment.base import PaymentInitResult, PaymentProvider

logger = logging.getLogger("payment.cinetpay")

INIT_URL = "https://api-checkout.cinetpay.com/v2/payment"
CHECK_URL = "https://api-checkout.cinetpay.com/v2/payment/check"


class CinetPayProvider(PaymentProvider):
    """CinetPay est un agrégateur de paiement largement utilisé en Côte
    d'Ivoire, regroupant Orange Money, MTN Mobile Money, Moov Money, Wave
    et les cartes bancaires derrière une seule intégration — pertinent
    pour ne pas avoir à négocier séparément avec chaque opérateur."""

    name = "cinetpay"

    def __init__(self, api_key: str, site_id: str, secret_key: str, timeout: int = 20):
        if not api_key or not site_id:
            raise ValueError("CINETPAY_API_KEY et CINETPAY_SITE_ID sont requis")
        self.api_key = api_key
        self.site_id = site_id
        self.secret_key = secret_key
        self.timeout = timeout

    def initiate(self, payment, notify_url: str, return_url: str) -> PaymentInitResult:
        transaction_id = f"pmesms-{payment.id}-{payment.business_id}"
        body = {
            "apikey": self.api_key,
            "site_id": self.site_id,
            "transaction_id": transaction_id,
            "amount": payment.amount_xof,
            "currency": "XOF",
            "description": f"Achat de {payment.credits} crédits SMS",
            "notify_url": notify_url,
            "return_url": return_url,
            "channels": "ALL",
        }
        try:
            response = requests.post(INIT_URL, json=body, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "201":
                return PaymentInitResult(
                    success=True,
                    provider_reference=transaction_id,
                    redirect_url=data.get("data", {}).get("payment_url"),
                )
            return PaymentInitResult(
                success=False,
                provider_reference=transaction_id,
                error=data.get("message", "Échec d'initialisation du paiement"),
            )
        except requests.RequestException as exc:
            logger.error("Échec initialisation CinetPay: %s", exc)
            return PaymentInitResult(success=False, provider_reference=transaction_id, error=str(exc))

    def verify_status(self, provider_reference: str) -> str:
        body = {"apikey": self.api_key, "site_id": self.site_id, "transaction_id": provider_reference}
        try:
            response = requests.post(CHECK_URL, json=body, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            status = data.get("data", {}).get("status")
            if status == "ACCEPTED":
                return "success"
            if status == "REFUSED":
                return "failed"
            return "pending"
        except requests.RequestException as exc:
            logger.error("Échec vérification CinetPay: %s", exc)
            return "pending"
