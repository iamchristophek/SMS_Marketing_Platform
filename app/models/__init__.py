"""Regroupe tous les modèles pour que Flask-Migrate les détecte via un
import unique : `from app.models import db, User, Business, ...`.
"""
from app.extensions import db
from app.models.user import User, Business
from app.models.contact import Contact, ContactGroup, contact_group_members
from app.models.campaign import Campaign, Message
from app.models.billing import CreditPackage, CreditTransaction, Payment
from app.models.api_key import ApiKey

__all__ = [
    "db",
    "User",
    "Business",
    "Contact",
    "ContactGroup",
    "contact_group_members",
    "Campaign",
    "Message",
    "CreditPackage",
    "CreditTransaction",
    "Payment",
    "ApiKey",
]
