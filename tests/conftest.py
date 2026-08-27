import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import Business, User


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def business(db):
    biz = Business(name="PME Test", credit_balance=50)
    db.session.add(biz)
    db.session.commit()
    return biz


@pytest.fixture()
def user(db, business):
    u = User(username="testuser", email="test@example.com", role=User.ROLE_OWNER, business_id=business.id)
    u.set_password("Password123!")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def auth_client(client, user):
    client.post("/login", data={"username": "testuser", "password": "Password123!"}, follow_redirects=True)
    return client
