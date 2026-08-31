import hashlib
import secrets
from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class ApiKey(db.Model):
    """Clé d'API permettant à une Business d'intégrer la plateforme depuis
    ses propres systèmes (ERP, e-commerce, CRM) sans passer par l'UI web.
    Seul le hash de la clé est stocké ; la valeur en clair n'est montrée
    qu'une seule fois, à la création.
    """

    __tablename__ = "api_keys"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)

    name = db.Column(db.String(80), nullable=False)
    key_prefix = db.Column(db.String(10), nullable=False)
    key_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_used_at = db.Column(db.DateTime(timezone=True))
    revoked = db.Column(db.Boolean, nullable=False, default=False)

    business = db.relationship("Business", back_populates="api_keys")

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def generate(cls, business_id, name):
        """Génère une nouvelle clé. Retourne (instance, valeur_en_clair)."""
        raw_key = f"baoryx_{secrets.token_urlsafe(32)}"
        instance = cls(
            business_id=business_id,
            name=name,
            key_prefix=raw_key[:14],
            key_hash=cls.hash_key(raw_key),
        )
        return instance, raw_key

    def __repr__(self):
        return f"<ApiKey {self.key_prefix}...>"
