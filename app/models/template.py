from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class MessageTemplate(db.Model):
    """Modèle de message réutilisable (repris du prototype de `main`)."""

    __tablename__ = "message_templates"

    CATEGORY_PROMOTIONAL = "promotional"
    CATEGORY_TRANSACTIONAL = "transactional"
    CATEGORY_INFORMATIONAL = "informational"

    CATEGORY_LABELS = {
        CATEGORY_PROMOTIONAL: "Promotionnel",
        CATEGORY_TRANSACTIONAL: "Transactionnel",
        CATEGORY_INFORMATIONAL: "Informatif",
    }

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(20), nullable=False, default=CATEGORY_PROMOTIONAL)
    body = db.Column(db.String(640), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    business = db.relationship("Business", back_populates="message_templates")

    __table_args__ = (db.UniqueConstraint("business_id", "name", name="uq_template_name_per_business"),)

    @property
    def category_label(self):
        return self.CATEGORY_LABELS.get(self.category, self.category)
