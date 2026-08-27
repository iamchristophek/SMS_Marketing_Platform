from app.models.user import Business, User


def test_register_creates_business_and_user(client, db):
    response = client.post(
        "/register",
        data={
            "business_name": "Ma Boutique",
            "username": "boutique225",
            "email": "contact@boutique225.ci",
            "password": "SuperSecret1",
            "confirm_password": "SuperSecret1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    user = User.query.filter_by(username="boutique225").first()
    assert user is not None
    assert user.business is not None
    assert user.business.credit_balance == 20  # FREE_TRIAL_CREDITS en config de test


def test_login_with_wrong_password_fails(client, user):
    response = client.post(
        "/login", data={"username": "testuser", "password": "wrong"}, follow_redirects=True
    )
    assert b"incorrect" in response.data.lower()


def test_login_success_redirects_to_dashboard(client, user):
    response = client.post(
        "/login", data={"username": "testuser", "password": "Password123!"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Tableau de bord" in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302


def test_password_is_hashed(user):
    assert user.password_hash != "Password123!"
    assert user.check_password("Password123!")
    assert not user.check_password("wrong")
