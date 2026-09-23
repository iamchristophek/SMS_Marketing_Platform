import logging

import requests

from app.services.sms.base import SmsProvider, SmsSendResult

logger = logging.getLogger("sms.africastalking")

# Africa's Talking est l'agrégateur SMS le plus répandu en Afrique de
# l'Ouest (Côte d'Ivoire incluse) : couverture multi-opérateurs (Orange,
# MTN, Moov) via une API unique.
LIVE_URL = "https://api.africastalking.com/version1/messaging"
SANDBOX_URL = "https://api.sandbox.africastalking.com/version1/messaging"

# Africa's Talking accepte plusieurs destinataires dans un seul appel (`to`
# séparés par des virgules). On limite la taille des lots pour garder des
# requêtes HTTP raisonnables sur les grosses campagnes (des milliers de
# contacts), plutôt qu'un unique appel géant.
BULK_CHUNK_SIZE = 200


class AfricasTalkingProvider(SmsProvider):
    name = "africastalking"

    def __init__(self, username: str, api_key: str, sandbox: bool = False, timeout: int = 15):
        if not username or not api_key:
            raise ValueError("AFRICASTALKING_USERNAME et AFRICASTALKING_API_KEY sont requis")
        self.username = username
        self.api_key = api_key
        self.url = SANDBOX_URL if sandbox or username == "sandbox" else LIVE_URL
        self.timeout = timeout

    def _headers(self):
        return {
            "apiKey": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def send(self, to_e164: str, message: str, sender_id: str) -> SmsSendResult:
        payload = {"username": self.username, "to": to_e164, "message": message}
        if sender_id:
            payload["from"] = sender_id

        try:
            response = requests.post(
                self.url, data=payload, headers=self._headers(), timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            recipients = data.get("SMSMessageData", {}).get("Recipients", [])
            if not recipients:
                return SmsSendResult(
                    success=False,
                    provider=self.name,
                    error="Réponse Africa's Talking sans destinataire",
                    raw_response=response.text,
                )
            recipient = recipients[0]
            success = str(recipient.get("status", "")).lower() == "success"
            return SmsSendResult(
                success=success,
                provider=self.name,
                provider_message_id=recipient.get("messageId"),
                error=None if success else recipient.get("status"),
                raw_response=response.text,
            )
        except requests.RequestException as exc:
            logger.error("Échec envoi Africa's Talking vers %s: %s", to_e164, exc)
            return SmsSendResult(success=False, provider=self.name, error=str(exc))

    def send_bulk(self, recipients, message: str, sender_id: str):
        """Envoi groupé réel : Africa's Talking accepte une liste de
        numéros séparés par des virgules dans un seul appel et retourne un
        `Recipients[]` avec un statut par numéro, au lieu d'un aller-retour
        HTTP par destinataire."""
        recipients = list(recipients)
        results = []
        for start in range(0, len(recipients), BULK_CHUNK_SIZE):
            chunk = recipients[start : start + BULK_CHUNK_SIZE]
            results.extend(self._send_chunk(chunk, message, sender_id))
        return results

    def _send_chunk(self, chunk, message: str, sender_id: str):
        payload = {"username": self.username, "to": ",".join(chunk), "message": message}
        if sender_id:
            payload["from"] = sender_id

        try:
            response = requests.post(
                self.url, data=payload, headers=self._headers(), timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            recipients_data = data.get("SMSMessageData", {}).get("Recipients", [])
        except requests.RequestException as exc:
            logger.error("Échec envoi groupé Africa's Talking (%s destinataires): %s", len(chunk), exc)
            return [SmsSendResult(success=False, provider=self.name, error=str(exc)) for _ in chunk]

        # L'API ne garantit pas que Recipients[] respecte l'ordre d'entrée :
        # on ré-associe chaque résultat à son numéro d'origine.
        by_number = {r.get("number"): r for r in recipients_data}
        results = []
        for number in chunk:
            recipient = by_number.get(number)
            if recipient is None:
                results.append(
                    SmsSendResult(success=False, provider=self.name, error="Absent de la réponse Africa's Talking")
                )
                continue
            success = str(recipient.get("status", "")).lower() == "success"
            results.append(
                SmsSendResult(
                    success=success,
                    provider=self.name,
                    provider_message_id=recipient.get("messageId"),
                    error=None if success else recipient.get("status"),
                )
            )
        return results
