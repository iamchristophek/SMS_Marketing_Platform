"""Interface commune à tous les fournisseurs SMS.

Chaque fournisseur (Africa's Talking, Orange, Twilio, ou la console pour
le développement local) implémente `SmsProvider.send`. Cette abstraction
permet de changer de fournisseur — ou d'en ajouter un nouveau — sans
toucher au reste de l'application (services de campagne, tâches Celery).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SmsSendResult:
    success: bool
    provider: str
    provider_message_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None


class SmsProvider(ABC):
    name = "base"

    @abstractmethod
    def send(self, to_e164: str, message: str, sender_id: str) -> SmsSendResult:
        """Envoie un SMS unique. Doit toujours retourner un SmsSendResult,
        jamais lever d'exception réseau non gérée (les erreurs sont
        encapsulées dans le champ `error`)."""
        raise NotImplementedError

    def send_bulk(self, recipients, message: str, sender_id: str):
        """Implémentation par défaut : envoi séquentiel. Les fournisseurs
        supportant un vrai envoi groupé (ex: Africa's Talking) peuvent
        surcharger cette méthode pour réduire le nombre d'appels HTTP."""
        return [self.send(to, message, sender_id) for to in recipients]
