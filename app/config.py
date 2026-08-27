"""Configuration de l'application, pilotée par variables d'environnement.

Trois profils : développement, test, production. En production, toute
valeur sensible (clé secrète, identifiants API, base de données) DOIT
provenir de l'environnement — aucune valeur par défaut faible n'est
acceptée.
"""
import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


def _bool_env(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class BaseConfig:
    ENV = "base"
    TESTING = False
    DEBUG = False

    SECRET_KEY = os.environ.get("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'sms_marketing.db')}"
    )
    # Certains hébergeurs (Render, Heroku) fournissent postgres:// alors que
    # SQLAlchemy 2.x exige postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # --- Sécurité session / cookies ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", True)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    WTF_CSRF_TIME_LIMIT = None

    # --- JWT (API) ---
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]

    # --- Rate limiting ---
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = "200 per hour"

    # --- Celery / Redis ---
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
    )
    CELERY_TASK_ALWAYS_EAGER = _bool_env("CELERY_TASK_ALWAYS_EAGER", False)

    # --- Fournisseur SMS ---
    # Valeurs possibles : console (dev/local), africastalking, orange, twilio
    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console")
    SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "PMEPMI")
    SMS_MAX_PER_MESSAGE_SEGMENTS = int(os.environ.get("SMS_MAX_PER_MESSAGE_SEGMENTS", 3))

    AT_USERNAME = os.environ.get("AFRICASTALKING_USERNAME")
    AT_API_KEY = os.environ.get("AFRICASTALKING_API_KEY")

    ORANGE_CLIENT_ID = os.environ.get("ORANGE_CLIENT_ID")
    ORANGE_CLIENT_SECRET = os.environ.get("ORANGE_CLIENT_SECRET")
    ORANGE_SENDER_ADDRESS = os.environ.get("ORANGE_SENDER_ADDRESS")

    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER")

    # --- Mobile Money / paiement ---
    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "manual")
    CINETPAY_API_KEY = os.environ.get("CINETPAY_API_KEY")
    CINETPAY_SITE_ID = os.environ.get("CINETPAY_SITE_ID")
    CINETPAY_SECRET_KEY = os.environ.get("CINETPAY_SECRET_KEY")

    # --- Crédits / tarification ---
    SMS_COST_CREDITS = int(os.environ.get("SMS_COST_CREDITS", 1))
    FREE_TRIAL_CREDITS = int(os.environ.get("FREE_TRIAL_CREDITS", 20))

    # --- Divers ---
    DEFAULT_COUNTRY_CODE = "225"  # Côte d'Ivoire
    MAIL_SUPPORT_ADDRESS = os.environ.get("MAIL_SUPPORT_ADDRESS", "support@pmesms.ci")
    PREFERRED_URL_SCHEME = "https"

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", False)
    CELERY_TASK_ALWAYS_EAGER = _bool_env("CELERY_TASK_ALWAYS_EAGER", True)


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    CELERY_TASK_ALWAYS_EAGER = True
    SMS_PROVIDER = "console"
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    ENV = "production"

    @staticmethod
    def init_app(app):
        BaseConfig.init_app(app)
        if not app.config.get("SECRET_KEY"):
            raise RuntimeError(
                "SECRET_KEY doit être défini via variable d'environnement en production."
            )
        if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite") and not _bool_env(
            "ALLOW_SQLITE_IN_PROD"
        ):
            raise RuntimeError(
                "SQLite n'est pas recommandé en production. Définissez DATABASE_URL "
                "vers PostgreSQL, ou définissez ALLOW_SQLITE_IN_PROD=1 pour forcer."
            )


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
