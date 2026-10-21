import logging
import uuid

from app.services.sms.base import SmsProvider, SmsSendResult

logger = logging.getLogger("sms.console")


class ConsoleSmsProvider(SmsProvider):
    """Fournisseur factice pour le développement local et les tests
    automatisés : n'effectue aucun appel réseau, journalise le message et
    simule toujours un envoi réussi."""

    name = "console"

    def send(self, to_e164: str, message: str, sender_id: str) -> SmsSendResult:
        fake_id = f"console-{uuid.uuid4().hex[:12]}"
        logger.info("[SMS console] de=%s vers=%s message=%r id=%s", sender_id, to_e164, message, fake_id)
        return SmsSendResult(success=True, provider=self.name, provider_message_id=fake_id)
