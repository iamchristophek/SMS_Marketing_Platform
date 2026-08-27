from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


contact_group_members = db.Table(
    "contact_group_members",
    db.Column("contact_id", db.Integer, db.ForeignKey("contacts.id"), primary_key=True),
    db.Column("group_id", db.Integer, db.ForeignKey("contact_groups.id"), primary_key=True),
)


class ContactGroup(db.Model):
    """Segment de contacts (ex: 'Clients VIP', 'Prospects Abidjan')."""

    __tablename__ = "contact_groups"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    business = db.relationship("Business", back_populates="groups")
    contacts = db.relationship(
        "Contact", secondary=contact_group_members, back_populates="groups"
    )

    __table_args__ = (db.UniqueConstraint("business_id", "name", name="uq_group_name_per_business"),)

    @property
    def active_contact_count(self):
        return sum(1 for c in self.contacts if not c.opted_out)


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)

    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    phone_e164 = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120))

    opted_out = db.Column(db.Boolean, nullable=False, default=False)
    opted_out_at = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    business = db.relationship("Business", back_populates="contacts")
    groups = db.relationship(
        "ContactGroup", secondary=contact_group_members, back_populates="contacts"
    )
    messages = db.relationship("Message", back_populates="contact")

    __table_args__ = (
        db.UniqueConstraint("business_id", "phone_e164", name="uq_contact_phone_per_business"),
    )

    @property
    def full_name(self):
        name = " ".join(part for part in [self.first_name, self.last_name] if part)
        return name or self.phone_e164

    def __repr__(self):
        return f"<Contact {self.phone_e164}>"
