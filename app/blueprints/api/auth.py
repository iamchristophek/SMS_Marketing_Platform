"""Authentification pour l'API JSON : deux mécanismes coexistent.

1. JWT (Authorization: Bearer <token>) — obtenu via /api/v1/auth/token,
   destiné à un futur client mobile ou à une SPA.
2. Clé d'API (en-tête X-API-Key) — destinée à l'intégration
   serveur-à-serveur (ERP, CMS e-commerce) d'une PME/PMI.

Les deux résolvent vers une `Business` (accessible via `g.current_business`)
et un rôle. Ceci permet aux routes de rester agnostiques du mécanisme
d'authentification utilisé par l'appelant.
"""
from datetime import datetime, timezone
from functools import wraps

from flask import current_app, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db
from app.models.api_key import ApiKey
from app.models.user import Business, User


def _resolve_from_api_key():
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        return False

    key_hash = ApiKey.hash_key(raw_key)
    api_key = ApiKey.query.filter_by(key_hash=key_hash, revoked=False).first()
    if api_key is None:
        return False

    api_key.last_used_at = datetime.now(timezone.utc)
    db.session.commit()
    g.current_business = api_key.business
    g.current_user = None
    return True


def _resolve_from_jwt():
    try:
        verify_jwt_in_request()
    except Exception:  # noqa: BLE001 - toute erreur JWT => non authentifié
        return False

    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id)) if user_id else None
    if user is None:
        return False

    g.current_business = user.business
    g.current_user = user
    return True


def api_auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if _resolve_from_api_key() or _resolve_from_jwt():
            return fn(*args, **kwargs)
        return jsonify(error="Authentification requise (clé API ou jeton JWT)"), 401

    return wrapper


def current_business() -> Business:
    return g.current_business
