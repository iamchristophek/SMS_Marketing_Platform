from flask import Blueprint

campaigns_bp = Blueprint("campaigns", __name__, url_prefix="/campaigns")

from app.blueprints.campaigns import routes  # noqa: E402,F401
