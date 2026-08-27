import logging
import os

from flask import Flask, jsonify, render_template, request

from app.config import config
from app.extensions import csrf, db, jwt, limiter, login_manager, migrate


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    os.makedirs(app.instance_path, exist_ok=True)

    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_cli(app)
    _register_hooks(app)
    _configure_logging(app)

    return app


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    jwt.init_app(app)
    if app.config.get("RATELIMIT_ENABLED", True):
        limiter.init_app(app)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))


def _register_blueprints(app):
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.contacts import contacts_bp
    from app.blueprints.campaigns import campaigns_bp
    from app.blueprints.billing import billing_bp
    from app.blueprints.webhooks import webhooks_bp
    from app.blueprints.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    # Les webhooks (callbacks externes signés par le fournisseur) ne
    # transitent jamais par un cookie de session : pas de jeton CSRF
    # disponible côté appelant, donc exemption au niveau du blueprint.
    # L'API JSON (app/blueprints/api) est authentifiée par clé API ou JWT
    # (en-têtes explicites, jamais un cookie envoyé automatiquement par le
    # navigateur) : chaque route y est donc exemptée individuellement,
    # SAUF les routes de gestion des clés API qui s'appuient sur la
    # session de connexion web et doivent rester protégées par CSRF.
    csrf.exempt(webhooks_bp)


def _register_error_handlers(app):
    def wants_json():
        return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"

    @app.errorhandler(404)
    def not_found(error):
        if wants_json():
            return jsonify(error="Ressource introuvable"), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(error):
        if wants_json():
            return jsonify(error="Accès refusé"), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        if wants_json():
            return jsonify(error="Erreur interne du serveur"), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def rate_limited(error):
        if wants_json():
            return jsonify(error="Trop de requêtes, réessayez plus tard"), 429
        return render_template("errors/429.html"), 429


def _register_cli(app):
    from app.cli import register_cli_commands

    register_cli_commands(app)


def _register_hooks(app):
    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    @app.route("/healthz")
    def healthz():
        return jsonify(status="ok"), 200


def _configure_logging(app):
    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)
