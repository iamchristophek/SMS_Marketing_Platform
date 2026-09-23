from flask import Blueprint

billing_bp = Blueprint("billing", __name__, url_prefix="/billing")

from app.blueprints.billing import routes  # noqa: E402,F401
