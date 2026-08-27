from datetime import datetime, timezone

from flask import current_app, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, get_jwt_identity, jwt_required
from flask_login import login_required, current_user as flask_login_current_user

from app.blueprints.api import api_bp
from app.blueprints.api.auth import api_auth_required, current_business
from app.extensions import csrf, db, limiter
from app.models.api_key import ApiKey
from app.models.campaign import Campaign, Message, compute_sms_segments
from app.models.contact import Contact, ContactGroup
from app.models.user import User
from app.services import billing_service, campaign_service
from app.services.billing_service import InsufficientCreditsError
from app.services.phone import InvalidPhoneNumberError, normalize_phone
from app.services.sms import get_sms_provider
from app.tasks.sms_tasks import send_campaign


# ---------------------------------------------------------------------------
# Authentification JWT (pour un futur client mobile / SPA)
# ---------------------------------------------------------------------------
@api_bp.route("/auth/token", methods=["POST"])
@csrf.exempt
@limiter.limit("10 per minute")
def auth_token():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=data.get("username", "")).first()
    if not user or not user.is_active_account or not user.check_password(data.get("password", "")):
        return jsonify(error="Identifiants invalides"), 401

    identity = str(user.id)
    return jsonify(
        access_token=create_access_token(identity=identity),
        refresh_token=create_refresh_token(identity=identity),
    )


@api_bp.route("/auth/refresh", methods=["POST"])
@csrf.exempt
@jwt_required(refresh=True)
def auth_refresh():
    return jsonify(access_token=create_access_token(identity=get_jwt_identity()))


# ---------------------------------------------------------------------------
# Compte / solde
# ---------------------------------------------------------------------------
@api_bp.route("/me")
@api_auth_required
def me():
    business = current_business()
    return jsonify(
        business_id=business.id,
        name=business.name,
        credit_balance=business.credit_balance,
    )


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
def _contact_to_dict(contact: Contact):
    return {
        "id": contact.id,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "phone": contact.phone_e164,
        "email": contact.email,
        "opted_out": contact.opted_out,
        "groups": [g.id for g in contact.groups],
    }


@api_bp.route("/contacts", methods=["GET"])
@api_auth_required
def list_contacts():
    business = current_business()
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 50, type=int), 200)
    pagination = Contact.query.filter_by(business_id=business.id).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify(
        items=[_contact_to_dict(c) for c in pagination.items],
        page=pagination.page,
        pages=pagination.pages,
        total=pagination.total,
    )


@api_bp.route("/contacts", methods=["POST"])
@csrf.exempt
@api_auth_required
def create_contact():
    business = current_business()
    data = request.get_json(silent=True) or {}

    try:
        phone = normalize_phone(data.get("phone", ""))
    except InvalidPhoneNumberError as exc:
        return jsonify(error=str(exc)), 400

    if Contact.query.filter_by(business_id=business.id, phone_e164=phone).first():
        return jsonify(error="Un contact avec ce numéro existe déjà"), 409

    contact = Contact(
        business_id=business.id,
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        phone_e164=phone,
        email=data.get("email"),
    )
    db.session.add(contact)
    db.session.commit()
    return jsonify(_contact_to_dict(contact)), 201


# ---------------------------------------------------------------------------
# Groupes
# ---------------------------------------------------------------------------
@api_bp.route("/groups", methods=["GET"])
@api_auth_required
def list_groups():
    business = current_business()
    groups = ContactGroup.query.filter_by(business_id=business.id).all()
    return jsonify(
        items=[
            {"id": g.id, "name": g.name, "contact_count": g.active_contact_count} for g in groups
        ]
    )


# ---------------------------------------------------------------------------
# Envoi transactionnel unitaire (ex: confirmation de commande e-commerce)
# ---------------------------------------------------------------------------
@api_bp.route("/sms/send", methods=["POST"])
@csrf.exempt
@api_auth_required
@limiter.limit("60 per minute")
def send_single_sms():
    business = current_business()
    data = request.get_json(silent=True) or {}

    message_body = (data.get("message") or "").strip()
    if not message_body:
        return jsonify(error="Le champ 'message' est requis"), 400
    if len(message_body) > 640:
        return jsonify(error="Message trop long (640 caractères maximum)"), 400

    try:
        phone = normalize_phone(data.get("to", ""))
    except InvalidPhoneNumberError as exc:
        return jsonify(error=str(exc)), 400

    segments = compute_sms_segments(message_body)
    cost = segments * current_app.config["SMS_COST_CREDITS"]

    try:
        billing_service.debit_for_campaign(business, cost, None, "Envoi SMS transactionnel API")
    except InsufficientCreditsError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 402

    message = Message(
        business_id=business.id,
        phone_e164=phone,
        body=message_body,
    )
    db.session.add(message)
    db.session.flush()

    result = get_sms_provider().send(phone, message_body, current_app.config["SMS_SENDER_ID"])
    message.provider = result.provider
    if result.success:
        message.status = Message.STATUS_SENT
        message.provider_message_id = result.provider_message_id
        message.sent_at = datetime.now(timezone.utc)
        message.credits_used = cost
    else:
        message.status = Message.STATUS_FAILED
        message.error_message = (result.error or "")[:255]
        billing_service.refund_for_campaign(business, cost, None, "Remboursement échec envoi API")

    db.session.commit()

    return jsonify(
        id=message.id,
        status=message.status,
        provider_message_id=message.provider_message_id,
        credits_used=message.credits_used,
        error=message.error_message,
    ), (201 if result.success else 502)


# ---------------------------------------------------------------------------
# Campagnes
# ---------------------------------------------------------------------------
@api_bp.route("/campaigns", methods=["POST"])
@csrf.exempt
@api_auth_required
def create_campaign():
    business = current_business()
    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()
    message_body = (data.get("message") or "").strip()
    if not name or not message_body:
        return jsonify(error="Les champs 'name' et 'message' sont requis"), 400

    group_id = data.get("group_id")
    if group_id and not ContactGroup.query.filter_by(id=group_id, business_id=business.id).first():
        return jsonify(error="Groupe introuvable"), 404

    owner = User.query.filter_by(business_id=business.id, role=User.ROLE_OWNER).first()
    campaign = Campaign(
        business_id=business.id,
        created_by_id=(flask_login_current_user.id if flask_login_current_user.is_authenticated else owner.id),
        name=name,
        message_body=message_body,
        group_id=group_id,
        status=Campaign.STATUS_DRAFT,
    )
    db.session.add(campaign)
    db.session.flush()

    try:
        campaign_service.reserve_credits(campaign, current_app.config["SMS_COST_CREDITS"])
    except InsufficientCreditsError as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 402

    scheduled_at_raw = data.get("scheduled_at")
    now = datetime.now(timezone.utc)
    scheduled_at = None
    if scheduled_at_raw:
        try:
            scheduled_at = datetime.fromisoformat(scheduled_at_raw)
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return jsonify(error="scheduled_at doit être au format ISO 8601"), 400

    if scheduled_at and scheduled_at > now:
        campaign.status = Campaign.STATUS_SCHEDULED
        campaign.scheduled_at = scheduled_at
        db.session.commit()
    else:
        campaign.status = Campaign.STATUS_SCHEDULED
        campaign.scheduled_at = now
        db.session.commit()
        send_campaign.delay(campaign.id)

    return jsonify(id=campaign.id, status=campaign.status, total_recipients=campaign.total_recipients), 201


@api_bp.route("/campaigns/<int:campaign_id>", methods=["GET"])
@api_auth_required
def get_campaign(campaign_id):
    business = current_business()
    campaign = Campaign.query.filter_by(id=campaign_id, business_id=business.id).first()
    if campaign is None:
        return jsonify(error="Campagne introuvable"), 404
    return jsonify(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        total_recipients=campaign.total_recipients,
        total_sent=campaign.total_sent,
        total_delivered=campaign.total_delivered,
        total_failed=campaign.total_failed,
        credits_used=campaign.credits_used,
    )


# ---------------------------------------------------------------------------
# Gestion des clés d'API (nécessite une session propriétaire authentifiée)
# ---------------------------------------------------------------------------
@api_bp.route("/api-keys", methods=["GET"])
@login_required
def list_api_keys():
    keys = ApiKey.query.filter_by(business_id=flask_login_current_user.business_id).all()
    return jsonify(
        items=[
            {
                "id": k.id,
                "name": k.name,
                "prefix": k.key_prefix,
                "revoked": k.revoked,
                "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            }
            for k in keys
        ]
    )


@api_bp.route("/api-keys", methods=["POST"])
@login_required
def create_api_key():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "Clé API").strip()
    api_key, raw_key = ApiKey.generate(flask_login_current_user.business_id, name)
    db.session.add(api_key)
    db.session.commit()
    return jsonify(id=api_key.id, name=api_key.name, key=raw_key), 201


@api_bp.route("/api-keys/<int:key_id>", methods=["DELETE"])
@login_required
def revoke_api_key(key_id):
    api_key = ApiKey.query.filter_by(
        id=key_id, business_id=flask_login_current_user.business_id
    ).first_or_404()
    api_key.revoked = True
    db.session.commit()
    return jsonify(status="revoked")
