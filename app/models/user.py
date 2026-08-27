from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Business(db.Model):
    """Le compte 'entreprise' (PME/PMI) — unité de facturation et de
    cloisonnement des données (multi-tenant). Chaque utilisateur appartient
    à une Business ; toutes les ressources (contacts, campagnes...) sont
    rattachées à une Business, jamais directement à un User.
    """

    __tablename__ = "businesses"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sector = db.Column(db.String(80))
    city = db.Column(db.String(80))
    phone = db.Column(db.String(20))
    credit_balance = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    users = db.relationship("User", back_populates="business", cascade="all, delete-orphan")
    contacts = db.relationship("Contact", back_populates="business", cascade="all, delete-orphan")
    groups = db.relationship("ContactGroup", back_populates="business", cascade="all, delete-orphan")
    campaigns = db.relationship("Campaign", back_populates="business", cascade="all, delete-orphan")
    credit_transactions = db.relationship(
        "CreditTransaction", back_populates="business", cascade="all, delete-orphan"
    )
    payments = db.relationship("Payment", back_populates="business", cascade="all, delete-orphan")
    api_keys = db.relationship("ApiKey", back_populates="business", cascade="all, delete-orphan")

    def has_sufficient_credits(self, amount):
        return self.credit_balance >= amount

    def __repr__(self):
        return f"<Business {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLE_OWNER = "owner"
    ROLE_STAFF = "staff"

    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)

    username = db.Column(db.String(30), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_OWNER)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))

    business = db.relationship("Business", back_populates="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.is_active_account

    def is_owner(self):
        return self.role == self.ROLE_OWNER

    def __repr__(self):
        return f"<User {self.username}>"
