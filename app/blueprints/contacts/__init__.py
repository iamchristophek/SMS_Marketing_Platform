from flask import Blueprint

contacts_bp = Blueprint("contacts", __name__, url_prefix="/contacts")

from app.blueprints.contacts import routes  # noqa: E402,F401
