from flask import Blueprint

templates_bp = Blueprint("templates_msg", __name__, url_prefix="/modeles")

from app.blueprints.templates_msg import routes  # noqa: E402,F401
