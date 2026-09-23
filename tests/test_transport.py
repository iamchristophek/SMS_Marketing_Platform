"""Blocage constaté en test réel : servie en HTTP avec un cookie de session
`Secure`, l'application réaffichait les formulaires sans aucun message."""
import pytest

from app import create_app
from app.config import ProductionConfig


@pytest.fixture()
def csrf_app(app):
    app.config["WTF_CSRF_ENABLED"] = True
    return app


def test_missing_csrf_token_shows_explanation(csrf_app, client):
    response = client.post("/login", data={"username": "x", "password": "y"})
    assert response.status_code == 400
    assert "Formulaire refusé".encode() in response.data


def test_csrf_page_explains_https_when_cookie_cannot_travel(csrf_app, client):
    csrf_app.config["SESSION_COOKIE_SECURE"] = True
    response = client.post(
        "/login", data={"username": "x", "password": "y"}, base_url="http://192.0.2.10"
    )
    assert response.status_code == 400
    assert b"HTTPS" in response.data


def test_banner_when_secure_cookie_served_over_http(app, client):
    app.config["SESSION_COOKIE_SECURE"] = True
    response = client.get("/login", base_url="http://192.0.2.10")
    assert "Connexion non sécurisée".encode() in response.data


def test_no_banner_over_https_or_localhost(app, client):
    app.config["SESSION_COOKIE_SECURE"] = True
    assert "Connexion non sécurisée".encode() not in client.get(
        "/login", base_url="https://app.baoryx.ci"
    ).data
    assert "Connexion non sécurisée".encode() not in client.get(
        "/login", base_url="http://localhost"
    ).data


def test_form_validation_errors_are_displayed(client, db):
    response = client.post(
        "/register",
        data={
            "business_name": "Ma Boutique",
            "username": "boutique225",
            "email": "contact@boutique225.ci",
            "password": "SuperSecret1",
            "confirm_password": "Different1",
        },
    )
    assert "Le formulaire contient des erreurs".encode() in response.data
    assert "Les mots de passe ne correspondent pas".encode() in response.data


def test_proxy_fix_reads_forwarded_proto():
    from flask import request

    application = create_app("testing", PROXY_FIX_COUNT=1)

    @application.route("/_scheme")
    def _scheme():
        return request.scheme

    response = application.test_client().get("/_scheme", base_url="http://localhost", headers={"X-Forwarded-Proto": "https"})
    assert response.data == b"https"


def test_forwarded_headers_ignored_without_proxy():
    from flask import request

    application = create_app("testing")

    @application.route("/_scheme")
    def _scheme():
        return request.scheme

    response = application.test_client().get("/_scheme", base_url="http://localhost", headers={"X-Forwarded-Proto": "https"})
    assert response.data == b"http"


@pytest.mark.parametrize("secret", ["", "change-moi", "trop-court"])
def test_production_refuses_weak_secret_key(secret):
    class FakeApp:
        config = {
            "SECRET_KEY": secret,
            "JWT_SECRET_KEY": "x" * 64,
            "SQLALCHEMY_DATABASE_URI": "postgresql://u:p@db/x",
        }

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProductionConfig.init_app(FakeApp())


def test_production_accepts_strong_secrets():
    class FakeApp:
        config = {
            "SECRET_KEY": "s" * 64,
            "JWT_SECRET_KEY": "j" * 64,
            "SQLALCHEMY_DATABASE_URI": "postgresql://u:p@db/x",
        }

    ProductionConfig.init_app(FakeApp())
