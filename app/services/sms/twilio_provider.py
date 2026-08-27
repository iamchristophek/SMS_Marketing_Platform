import logging

import requests

from app.services.sms.base import SmsProvider, SmsSendResult

logger = logging.getLogger("sms.twilio")

API_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


class TwilioSmsProvider(SmsProvider):
    """Fournisseur de secours (fallback) international, utile en phase
    pilote ou pour les envois hors Afrique de l'Ouest."""

    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, from_number: str, timeout: int = 15):
        if not account_sid or not auth_token or not from_number:
            raise ValueError(
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN et TWILIO_FROM_NUMBER sont requis"
            )
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        self.timeout = timeout

    def send(self, to_e164: str, message: str, sender_id: str) -> SmsSendResult:
        url = API_URL_TEMPLATE.format(sid=self.account_sid)
        try:
            response = requests.post(
                url,
                data={"To": to_e164, "From": self.from_number, "Body": message},
                auth=(self.account_sid, self.auth_token),
                timeout=self.timeout,
            )
            data = response.json()
            if response.status_code >= 400:
                return SmsSendResult(
                    success=False,
                    provider=self.name,
                    error=data.get("message", f"HTTP {response.status_code}"),
                    raw_response=response.text,
                )
            return SmsSendResult(
                success=True,
                provider=self.name,
                provider_message_id=data.get("sid"),
                raw_response=response.text,
            )
        except requests.RequestException as exc:
            logger.error("Échec envoi Twilio vers %s: %s", to_e164, exc)
            return SmsSendResult(success=False, provider=self.name, error=str(exc))
