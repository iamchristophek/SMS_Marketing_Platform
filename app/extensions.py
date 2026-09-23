"""Instances des extensions Flask, créées une seule fois et initialisées
dans l'application factory (app/__init__.py). Les importer d'ici évite les
imports circulaires entre modèles, blueprints et services.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from sqlalchemy import MetaData, event
from sqlalchemy.engine import Engine

# Convention de nommage explicite des contraintes : les migrations Alembic
# générées sont ainsi déterministes et identiques sur SQLite et PostgreSQL
# (indispensable pour pouvoir supprimer/modifier une contrainte plus tard).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
# render_as_batch : permet les ALTER TABLE sur SQLite (dev), sans effet
# sur PostgreSQL.
migrate = Migrate(render_as_batch=True, compare_type=True)
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
jwt = JWTManager()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite n'applique pas les clés étrangères par défaut. On les active
    pour que le développement et les tests se comportent comme PostgreSQL
    (sinon une violation de contrainte n'apparaît qu'en production)."""
    import sqlite3

    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


login_manager.login_view = "auth.login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"
