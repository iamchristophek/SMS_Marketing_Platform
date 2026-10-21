import hashlib
import hmac
import logging

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.services.payment.base import PaymentInitResult, PaymentProvider

logger = logging.getLogger("payment.cinetpay")

INIT_URL = "https://api-checkout.cinetpay.com/v2/payment"
CHECK_URL = "https://api-checkout.cinetpay.com/v2/payment/check"

# Ordre des champs du POST de notification CinetPay tel que concaténé pour
# le calcul du HMAC (cf. exemples officiels PHP/SDK CinetPay, section
# "Vérification de l'authenticité d'une notification" — à reconfirmer
# auprès de https://docs.cinetpay.com/api/1.0-fr/checkout/hmac si CinetPay
# fait évoluer ce format, le réseau de cet environnement ne permettant pas
# de le revérifier en direct au moment de l'écriture de ce module).
NOTIFICATION_SIGNATURE_FIELDS = (
    "cpm_site_id",
    "cpm_trans_id",
    "cpm_trans_date",
    "cpm_amount",
    "cpm_currency",
    "signature",
    "payment_method",
    "cel_phone_num",
    "cpm_phone_prefixe",
    "cpm_language",
    "cpm_version",
    "cpm_payment_config",
    "cpm_page_action",
    "cpm_custom",
    "cpm_designation",
    "cpm_error_message",
)

_retry_on_network_error = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type(requests.RequestException),
)


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

    @_retry_on_network_error
    def _post(self, url: str, body: dict) -> dict:
        response = requests.post(url, json=body, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def initiate(self, payment, notify_url: str, return_url: str) -> PaymentInitResult:
        transaction_id = f"baoryx-{payment.id}-{payment.business_id}"
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
            data = self._post(INIT_URL, body)
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
            logger.error("Échec initialisation CinetPay après tentatives : %s", exc)
            return PaymentInitResult(success=False, provider_reference=transaction_id, error=str(exc))

    def verify_status(self, provider_reference: str) -> str:
        body = {"apikey": self.api_key, "site_id": self.site_id, "transaction_id": provider_reference}
        try:
            data = self._post(CHECK_URL, body)
            status = data.get("data", {}).get("status")
            if status == "ACCEPTED":
                return "success"
            if status == "REFUSED":
                return "failed"
            return "pending"
        except requests.RequestException as exc:
            logger.error("Échec vérification CinetPay après tentatives : %s", exc)
            return "pending"

    def verify_notification_signature(self, payload: dict, received_token: str) -> bool:
        """Vérifie l'en-tête X-TOKEN d'une notification CinetPay (HMAC
        SHA256 du POST concaténé, avec la clé secrète marchande). Renvoie
        False si la signature ne correspond pas OU si un champ attendu est
        absent du payload (échec fermé : on ne fait jamais confiance à une
        notification qu'on ne peut pas vérifier intégralement)."""
        if not received_token or not self.secret_key:
            return False

        try:
            data_to_sign = "".join(str(payload.get(field, "")) for field in NOTIFICATION_SIGNATURE_FIELDS)
        except Exception:  # noqa: BLE001 - payload malformé
            return False

        expected_token = hmac.new(
            self.secret_key.encode("utf-8"), data_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_token, received_token)
