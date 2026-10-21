from flask import current_app

from app.services.payment.manual_provider import ManualPaymentProvider


def get_payment_provider():
    config = current_app.config
    provider_name = (config.get("PAYMENT_PROVIDER") or "manual").lower()

    if provider_name == "manual":
        return ManualPaymentProvider()

    if provider_name == "cinetpay":
        from app.services.payment.cinetpay_provider import CinetPayProvider

        return CinetPayProvider(
            api_key=config.get("CINETPAY_API_KEY"),
            site_id=config.get("CINETPAY_SITE_ID"),
            secret_key=config.get("CINETPAY_SECRET_KEY"),
        )

    raise ValueError(f"Fournisseur de paiement inconnu : {provider_name!r}")
