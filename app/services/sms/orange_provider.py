import base64
import logging
import time

import requests

from app.services.sms.base import SmsProvider, SmsSendResult

logger = logging.getLogger("sms.orange")

TOKEN_URL = "https://api.orange.com/oauth/v3/token"
SEND_URL_TEMPLATE = "https://api.orange.com/smsmessaging/v1/outbound/{sender}/requests"


class OrangeSmsProvider(SmsProvider):
    """Orange SMS API (Orange Developer Center) — pertinent pour les PME
    ivoiriennes déjà clientes Orange CI. Authentification OAuth2
    client_credentials, token mis en cache en mémoire avec marge de sécurité.
    """

    name = "orange"

    def __init__(self, client_id: str, client_secret: str, sender_address: str, timeout: int = 15):
        if not client_id or not client_secret or not sender_address:
            raise ValueError(
                "ORANGE_CLIENT_ID, ORANGE_CLIENT_SECRET et ORANGE_SENDER_ADDRESS sont requis"
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.sender_address = sender_address
        self.timeout = timeout
        self._token = None
        self._token_expires_at = 0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token

        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        response = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        # marge de sécurité de 60s avant expiration réelle
        self._token_expires_at = time.time() + int(data.get("expires_in", 3600)) - 60
        return self._token

    def send(self, to_e164: str, message: str, sender_id: str) -> SmsSendResult:
        try:
            token = self._get_token()
        except requests.RequestException as exc:
            logger.error("Échec authentification Orange: %s", exc)
            return SmsSendResult(success=False, provider=self.name, error=f"Auth échouée: {exc}")

        sender_encoded = requests.utils.quote(self.sender_address, safe="")
        url = SEND_URL_TEMPLATE.format(sender=sender_encoded)
        body = {
            "outboundSMSMessageRequest": {
                "address": [f"tel:{to_e164}"],
                "senderAddress": f"tel:{self.sender_address}",
                "senderName": sender_id,
                "outboundSMSTextMessage": {"message": message},
            }
        }
        try:
            response = requests.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            resource_url = (
                data.get("outboundSMSMessageRequest", {}).get("resourceURL")
            )
            return SmsSendResult(
                success=True,
                provider=self.name,
                provider_message_id=resource_url,
                raw_response=response.text,
            )
        except requests.RequestException as exc:
            logger.error("Échec envoi Orange vers %s: %s", to_e164, exc)
            return SmsSendResult(success=False, provider=self.name, error=str(exc))
