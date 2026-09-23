from datetime import datetime, timezone

from flask import jsonify, request

from app.blueprints.webhooks import webhooks_bp
from app.extensions import db
from app.models.billing import Payment
from app.models.campaign import Message
from app.models.contact import Contact
from app.services import billing_service
from app.services.payment import get_payment_provider
from app.services.phone import InvalidPhoneNumberError, normalize_phone


def utcnow():
    return datetime.now(timezone.utc)


@webhooks_bp.route("/sms/delivery-report", methods=["POST"])
def sms_delivery_report():
    """Callback appelé par le fournisseur SMS lorsqu'un message est
    effectivement livré au téléphone du destinataire (ou a échoué en
    aval de l'envoi). Format générique compatible Africa's Talking
    (id, status, phoneNumber) et autres agrégateurs similaires."""
    payload = request.form if request.form else (request.get_json(silent=True) or {})
    provider_message_id = payload.get("id") or payload.get("messageId")
    status = str(payload.get("status", "")).lower()

    if not provider_message_id:
        return jsonify(error="id/messageId manquant"), 400

    message = Message.query.filter_by(provider_message_id=provider_message_id).first()
    if message is None:
        return jsonify(status="ignoré, message inconnu"), 200

    was_delivered = message.status == Message.STATUS_DELIVERED
    if status in {"success", "delivered"}:
        message.status = Message.STATUS_DELIVERED
        message.delivered_at = utcnow()
        # Les fournisseurs rejouent parfois le même accusé : on ne compte
        # une livraison qu'une seule fois.
        if message.campaign and not was_delivered:
            message.campaign.total_delivered = (message.campaign.total_delivered or 0) + 1
    elif status in {"failed", "rejected", "expired"}:
        if message.campaign and was_delivered and message.campaign.total_delivered:
            message.campaign.total_delivered -= 1
        message.status = Message.STATUS_UNDELIVERED
        message.error_message = str(payload.get("failureReason") or "")[:255]

    db.session.commit()
    return jsonify(status="ok"), 200


@webhooks_bp.route("/sms/inbound", methods=["POST"])
def sms_inbound():
    """Callback pour les SMS entrants (réponse d'un destinataire). Gère en
    particulier le mot-clé STOP pour le désabonnement, requis par les
    bonnes pratiques anti-spam."""
    payload = request.form if request.form else (request.get_json(silent=True) or {})
    from_number = payload.get("from") or payload.get("phoneNumber")
    text = str(payload.get("text", "")).strip().upper()

    if from_number and text in {"STOP", "ARRET", "ARRÊT"}:
        # Les contacts sont stockés en E.164 : le numéro reçu peut arriver
        # sans « + » ou au format local selon l'agrégateur.
        try:
            from_number = normalize_phone(str(from_number))
        except InvalidPhoneNumberError:
            return jsonify(status="ok"), 200
        contacts = Contact.query.filter_by(phone_e164=from_number).all()
        for contact in contacts:
            contact.opted_out = True
            contact.opted_out_at = utcnow()
        db.session.commit()

    return jsonify(status="ok"), 200


@webhooks_bp.route("/payment/callback", methods=["POST", "GET"])
def payment_callback():
    """Callback (notify_url) appelé par le fournisseur de paiement Mobile
    Money après une tentative de transaction. On ne fait jamais confiance
    aveuglément au contenu du callback : on revérifie systématiquement le
    statut réel auprès du fournisseur avant de créditer le compte."""
    payload = request.form if request.form else (request.get_json(silent=True) or {})
    provider_reference = (
        payload.get("transaction_id") or payload.get("cpm_trans_id") or request.args.get("token")
    )
    if not provider_reference:
        return jsonify(error="référence de transaction manquante"), 400

    payment = Payment.query.filter_by(provider_reference=provider_reference).first()
    if payment is None:
        return jsonify(status="ignoré, paiement inconnu"), 200

    if payment.status != Payment.STATUS_PENDING:
        return jsonify(status="déjà traité"), 200

    provider = get_payment_provider()
    real_status = provider.verify_status(provider_reference)

    if real_status == "success":
        payment.status = Payment.STATUS_SUCCESS
        payment.completed_at = utcnow()
        billing_service.credit_purchase(
            payment.business,
            payment.credits,
            f"Achat pack « {payment.package.name} » (Mobile Money)",
            payment.id,
        )
    elif real_status == "failed":
        payment.status = Payment.STATUS_FAILED

    db.session.commit()
    return jsonify(status="ok"), 200
