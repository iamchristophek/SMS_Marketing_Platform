import re

from app.models.api_key import ApiKey
from app.models.contact import Contact
from app.models.user import Business, User


def test_account_page_renders(auth_client):
    html = auth_client.get("/compte/").data.decode()
    assert "Mon compte" in html and "Clés API" in html and "Changer mon mot de passe" in html


def test_update_business(auth_client, db, business):
    auth_client.post(
        "/compte/entreprise",
        data={"name": "Maquis Chez Tanti", "sector": "Restauration", "city": "Yopougon",
              "phone": "07 12 34 56 78"},
    )
    db.session.refresh(business)
    assert business.name == "Maquis Chez Tanti" and business.city == "Yopougon"
    assert business.phone == "+2250712345678"


def test_update_business_invalid_phone_shows_error(auth_client, business):
    resp = auth_client.post("/compte/entreprise", data={"name": "X Y", "phone": "123"})
    assert "invalide".encode() in resp.data


def test_update_email_must_be_unique(auth_client, db, user, business):
    db.session.add(User(username="autre", email="autre@x.ci", password_hash="h", business_id=business.id))
    db.session.commit()
    resp = auth_client.post("/compte/profil", data={"email": "autre@x.ci"})
    assert "déjà utilisée".encode() in resp.data
    auth_client.post("/compte/profil", data={"email": "nouveau@x.ci"})
    db.session.refresh(user)
    assert user.email == "nouveau@x.ci"


def test_create_api_key_shows_it_once_and_it_works(auth_client, client, db, business):
    html = auth_client.post("/compte/cles-api", data={"key_name": "Site web"}).data.decode()
    raw = re.search(r'id="new-key">([^<]+)<', html).group(1)
    key = ApiKey.query.one()
    assert key.key_hash == ApiKey.hash_key(raw) and raw not in auth_client.get("/compte/").data.decode()

    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    db.session.commit()
    resp = client.get("/api/v1/me", headers={"X-API-Key": raw})
    assert resp.status_code == 200 and resp.get_json()["business_id"] == business.id


def test_revoke_api_key(auth_client, client, db, business):
    key, raw = ApiKey.generate(business.id, "ERP")
    db.session.add(key)
    db.session.commit()
    auth_client.post(f"/compte/cles-api/{key.id}/revoquer")
    assert client.get("/api/v1/me", headers={"X-API-Key": raw}).status_code == 401


def test_cannot_revoke_other_business_key(auth_client, db):
    other = Business(name="Autre")
    db.session.add(other)
    db.session.commit()
    key, _ = ApiKey.generate(other.id, "ERP")
    db.session.add(key)
    db.session.commit()
    assert auth_client.post(f"/compte/cles-api/{key.id}/revoquer").status_code == 404
    db.session.refresh(key)
    assert not key.revoked


def test_navigation_links(auth_client):
    html = auth_client.get("/dashboard").data.decode()
    for href in ["/modeles/", "/compte/", "/billing/", "/contacts/", "/campaigns/"]:
        assert f'href="{href}"' in html


def test_error_on_one_form_does_not_leak_into_others(auth_client, business):
    html = auth_client.post("/compte/entreprise", data={"name": "Mon Entreprise", "phone": "123"}).data.decode()
    # Le champ du formulaire de clé API reste vide.
    assert re.search(r'id="key_name"[^>]*value="Mon Entreprise"', html) is None
