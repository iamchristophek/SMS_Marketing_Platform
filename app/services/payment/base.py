from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PaymentInitResult:
    success: bool
    provider_reference: str
    redirect_url: Optional[str] = None
    error: Optional[str] = None
    immediate_success: bool = False  # True pour un fournisseur factice sans redirection


class PaymentProvider(ABC):
    name = "base"

    @abstractmethod
    def initiate(self, payment, notify_url: str, return_url: str) -> PaymentInitResult:
        """Démarre une transaction de paiement (Mobile Money ou carte)."""
        raise NotImplementedError

    def verify_status(self, provider_reference: str) -> str:
        """Interroge le fournisseur pour l'état réel d'une transaction.
        Retourne 'success', 'failed' ou 'pending'."""
        return "pending"

    def verify_notification_signature(self, payload: dict, received_token: str) -> bool:
        """Vérifie l'authenticité d'une notification webhook entrante.
        Par défaut (fournisseur sans mécanisme de signature, ex. paiement
        manuel en dev) : aucune vérification disponible, on laisse passer."""
        return True
