from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


# Calcul GSM-7 / UCS-2 : voir app/services/sms/encoding.py. Réexporté ici
# pour les imports existants (services, API, tests).
from app.services.sms.encoding import analyze_message, compute_sms_segments  # noqa: E402,F401


class Campaign(db.Model):
    __tablename__ = "campaigns"

    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    ACTIVE_STATUSES = (STATUS_DRAFT, STATUS_SCHEDULED)

    STATUS_LABELS = {
        STATUS_DRAFT: "Brouillon",
        STATUS_SCHEDULED: "Planifiée",
        STATUS_SENDING: "En cours d'envoi",
        STATUS_SENT: "Envoyée",
        STATUS_FAILED: "Échec",
        STATUS_CANCELLED: "Annulée",
    }

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    group_id = db.Column(
        db.Integer, db.ForeignKey("contact_groups.id", ondelete="SET NULL"), nullable=True
    )

    name = db.Column(db.String(120), nullable=False)
    message_body = db.Column(db.String(640), nullable=False)  # jusqu'à 4 segments SMS
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT, index=True)
    # N'envoyer qu'aux contacts ayant donné leur consentement marketing.
    consent_only = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    scheduled_at = db.Column(db.DateTime(timezone=True))
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    total_recipients = db.Column(db.Integer, nullable=False, default=0)
    total_sent = db.Column(db.Integer, nullable=False, default=0)
    total_delivered = db.Column(db.Integer, nullable=False, default=0)
    total_failed = db.Column(db.Integer, nullable=False, default=0)
    credits_reserved = db.Column(db.Integer, nullable=False, default=0)
    credits_used = db.Column(db.Integer, nullable=False, default=0)

    business = db.relationship("Business", back_populates="campaigns")
    created_by = db.relationship("User")
    group = db.relationship("ContactGroup")
    messages = db.relationship(
        "Message", back_populates="campaign", cascade="all, delete-orphan", lazy="dynamic"
    )

    @property
    def segments_per_message(self):
        return compute_sms_segments(self.message_body)

    @property
    def sms_info(self):
        return analyze_message(self.message_body)

    @property
    def open_rate(self):
        """Taux de livraison (proxy du taux d'ouverture, un SMS livré étant
        considéré comme lu par le destinataire)."""
        if self.total_sent == 0:
            return 0
        return round((self.total_delivered / self.total_sent) * 100, 1)

    def is_editable(self):
        return self.status in self.ACTIVE_STATUSES

    def __repr__(self):
        return f"<Campaign {self.name} ({self.status})>"


class Message(db.Model):
    """Un SMS individuel envoyé dans le cadre d'une campagne (ou hors
    campagne, pour un envoi ponctuel via l'API)."""

    __tablename__ = "messages"

    STATUS_PENDING = "pending"
    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_FAILED = "failed"
    STATUS_UNDELIVERED = "undelivered"

    STATUS_LABELS = {
        STATUS_PENDING: "En attente",
        STATUS_QUEUED: "En file d'attente",
        STATUS_SENT: "Envoyé",
        STATUS_DELIVERED: "Livré",
        STATUS_FAILED: "Échec d'envoi",
        STATUS_UNDELIVERED: "Non livré",
    }

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.Integer, db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True
    )
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    # SET NULL : l'historique d'envoi est conservé si le contact est supprimé.
    contact_id = db.Column(
        db.Integer, db.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    phone_e164 = db.Column(db.String(20), nullable=False)
    body = db.Column(db.String(640), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)

    provider = db.Column(db.String(30))
    provider_message_id = db.Column(db.String(120), index=True)
    error_message = db.Column(db.String(255))
    credits_used = db.Column(db.Integer, nullable=False, default=0)
    # Coût réservé à la confirmation de la campagne ; facturé (credits_used)
    # seulement si le SMS part, sinon rendu au client.
    credits_reserved = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    queued_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))
    delivered_at = db.Column(db.DateTime(timezone=True))

    campaign = db.relationship("Campaign", back_populates="messages")
    contact = db.relationship("Contact", back_populates="messages")

    def __repr__(self):
        return f"<Message to={self.phone_e164} status={self.status}>"
