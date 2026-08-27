import math
from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


# Une trame SMS GSM-7 standard = 160 caractères, ou 153 par segment si le
# message est découpé en plusieurs segments (concaténation UDH).
GSM7_SINGLE_LIMIT = 160
GSM7_MULTIPART_LIMIT = 153


def compute_sms_segments(message_body: str) -> int:
    length = len(message_body or "")
    if length == 0:
        return 0
    if length <= GSM7_SINGLE_LIMIT:
        return 1
    return math.ceil(length / GSM7_MULTIPART_LIMIT)


class Campaign(db.Model):
    __tablename__ = "campaigns"

    STATUS_DRAFT = "draft"
    STATUS_SCHEDULED = "scheduled"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    ACTIVE_STATUSES = (STATUS_DRAFT, STATUS_SCHEDULED)

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("contact_groups.id"), nullable=True)

    name = db.Column(db.String(120), nullable=False)
    message_body = db.Column(db.String(640), nullable=False)  # jusqu'à 4 segments SMS
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT, index=True)

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

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id"), nullable=True, index=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"), nullable=True)

    phone_e164 = db.Column(db.String(20), nullable=False)
    body = db.Column(db.String(640), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING, index=True)

    provider = db.Column(db.String(30))
    provider_message_id = db.Column(db.String(120), index=True)
    error_message = db.Column(db.String(255))
    credits_used = db.Column(db.Integer, nullable=False, default=0)

    queued_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    sent_at = db.Column(db.DateTime(timezone=True))
    delivered_at = db.Column(db.DateTime(timezone=True))

    campaign = db.relationship("Campaign", back_populates="messages")
    contact = db.relationship("Contact", back_populates="messages")

    def __repr__(self):
        return f"<Message to={self.phone_e164} status={self.status}>"
