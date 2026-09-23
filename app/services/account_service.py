"""Création des comptes clients (entreprise + propriétaire)."""
from app.extensions import db


def create_business_with_owner(name, username, email, password, trial_credits, **business_fields):
    """Crée une entreprise, son propriétaire et, le cas échéant, les crédits
    offerts — toujours inscrits au journal comptable. Partagé par
    l'inscription web et les commandes CLI. Ne fait pas le commit."""
    from app.models.user import Business, User
    from app.services import billing_service

    business = Business(name=name, credit_balance=0, **business_fields)
    db.session.add(business)
    db.session.flush()

    user = User(username=username, email=email, role=User.ROLE_OWNER, business_id=business.id)
    user.set_password(password)
    db.session.add(user)

    if trial_credits:
        billing_service.credit_bonus(business, trial_credits, "Crédits offerts à l'inscription")
    return business, user
