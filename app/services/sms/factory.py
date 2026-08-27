"""Sélectionne l'implémentation SmsProvider à utiliser en fonction de la
configuration (variable d'environnement SMS_PROVIDER). Un seul point de
changement pour ajouter un nouveau fournisseur.
"""
from flask import current_app

from app.services.sms.console_provider import ConsoleSmsProvider

_cached_provider = None


def _build_provider(config):
    provider_name = (config.get("SMS_PROVIDER") or "console").lower()

    if provider_name == "console":
        return ConsoleSmsProvider()

    if provider_name == "africastalking":
        from app.services.sms.africastalking_provider import AfricasTalkingProvider

        return AfricasTalkingProvider(
            username=config.get("AT_USERNAME"), api_key=config.get("AT_API_KEY")
        )

    if provider_name == "orange":
        from app.services.sms.orange_provider import OrangeSmsProvider

        return OrangeSmsProvider(
            client_id=config.get("ORANGE_CLIENT_ID"),
            client_secret=config.get("ORANGE_CLIENT_SECRET"),
            sender_address=config.get("ORANGE_SENDER_ADDRESS"),
        )

    if provider_name == "twilio":
        from app.services.sms.twilio_provider import TwilioSmsProvider

        return TwilioSmsProvider(
            account_sid=config.get("TWILIO_ACCOUNT_SID"),
            auth_token=config.get("TWILIO_AUTH_TOKEN"),
            from_number=config.get("TWILIO_FROM_NUMBER"),
        )

    raise ValueError(f"Fournisseur SMS inconnu : {provider_name!r}")


def get_sms_provider():
    """Retourne une instance mise en cache du fournisseur SMS courant.
    Le cache est invalidé si SMS_PROVIDER change (utile pour les tests)."""
    global _cached_provider
    config = current_app.config
    if _cached_provider is None or _cached_provider.name != (config.get("SMS_PROVIDER") or "console").lower():
        _cached_provider = _build_provider(config)
    return _cached_provider


def reset_provider_cache():
    global _cached_provider
    _cached_provider = None
