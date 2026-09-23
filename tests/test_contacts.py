import io
import re

import pytest

from app.models.contact import Contact, ContactGroup
from app.services.phone import detect_operator


@pytest.fixture()
def contacts(db, business):
    vip = ContactGroup(business_id=business.id, name="VIP")
    db.session.add(vip)
    rows = [
        Contact(business_id=business.id, first_name="Koffi", last_name="Kouassi", phone_e164="+2250712345678"),
        Contact(business_id=business.id, first_name="Aya", phone_e164="+2250512345678", consent_given=True),
        Contact(business_id=business.id, first_name="Yao", phone_e164="+2250112345678", opted_out=True),
        Contact(business_id=business.id, first_name="Bureau", phone_e164="+2252722334455"),
    ]
    rows[0].groups.append(vip)
    db.session.add_all(rows)
    db.session.commit()
    return rows


@pytest.mark.parametrize(
    "phone,operator",
    [
        ("+2250712345678", "orange"),
        ("+2250512345678", "mtn"),
        ("+2250112345678", "moov"),
        ("+2252722334455", "fixe"),
        ("+33612345678", "international"),
    ],
)
def test_detect_operator(phone, operator):
    assert detect_operator(phone) == operator


def test_edit_contact_updates_fields_groups_and_consent(auth_client, db, contacts):
    koffi = contacts[0]
    group = ContactGroup(business_id=koffi.business_id, name="Abidjan")
    db.session.add(group)
    db.session.commit()

    resp = auth_client.post(
        f"/contacts/{koffi.id}/edit",
        data={
            "first_name": "Koffi",
            "last_name": "N'Guessan",
            "phone": "07 12 34 56 78",
            "email": "koffi@exemple.ci",
            "groups": [group.id],
            "consent_given": "y",
        },
    )
    assert resp.status_code == 302
    db.session.refresh(koffi)
    assert koffi.last_name == "N'Guessan"
    assert [g.name for g in koffi.groups] == ["Abidjan"]
    assert koffi.consent_given and koffi.consent_given_at is not None


def test_edit_contact_rejects_duplicate_phone(auth_client, db, contacts):
    resp = auth_client.post(
        f"/contacts/{contacts[0].id}/edit", data={"phone": "0512345678"}
    )
    assert resp.status_code == 200
    assert "existe déjà".encode() in resp.data


def test_edit_contact_of_other_business_is_404(auth_client, db, contacts):
    from app.models.user import Business

    other = Business(name="Autre")
    db.session.add(other)
    db.session.commit()
    foreign = Contact(business_id=other.id, phone_e164="+2250799999999")
    db.session.add(foreign)
    db.session.commit()
    assert auth_client.get(f"/contacts/{foreign.id}/edit").status_code == 404


def test_resubscribe_requires_explicit_checkbox(auth_client, db, contacts):
    yao = contacts[2]
    auth_client.post(f"/contacts/{yao.id}/edit", data={"phone": yao.phone_e164})
    db.session.refresh(yao)
    assert yao.opted_out
    auth_client.post(f"/contacts/{yao.id}/edit", data={"phone": yao.phone_e164, "resubscribe": "y"})
    db.session.refresh(yao)
    assert not yao.opted_out


def test_bulk_add_and_remove_from_group(auth_client, db, contacts):
    vip = ContactGroup.query.filter_by(name="VIP").one()
    ids = [contacts[1].id, contacts[2].id]
    auth_client.post("/contacts/bulk", data={"action": "add_to_group", "group_id": vip.id, "contact_ids": ids})
    assert len(vip.contacts) == 3

    auth_client.post("/contacts/bulk", data={"action": "remove_from_group", "group_id": vip.id, "contact_ids": ids})
    db.session.refresh(vip)
    assert [c.first_name for c in vip.contacts] == ["Koffi"]


def test_bulk_consent_and_delete(auth_client, db, contacts):
    auth_client.post("/contacts/bulk", data={"action": "consent", "group_id": 0, "contact_ids": [contacts[0].id]})
    db.session.refresh(contacts[0])
    assert contacts[0].consent_given

    auth_client.post("/contacts/bulk", data={"action": "delete", "group_id": 0, "contact_ids": [contacts[3].id]})
    assert Contact.query.count() == 3


def test_bulk_ignores_contacts_of_other_business(auth_client, db, contacts):
    from app.models.user import Business

    other = Business(name="Autre")
    db.session.add(other)
    db.session.commit()
    foreign = Contact(business_id=other.id, phone_e164="+2250799999999")
    db.session.add(foreign)
    db.session.commit()
    auth_client.post("/contacts/bulk", data={"action": "delete", "group_id": 0, "contact_ids": [foreign.id]})
    assert db.session.get(Contact, foreign.id) is not None


@pytest.mark.parametrize(
    "query,expected",
    [
        ("q=kouassi", {"Koffi"}),
        ("q=05 12 34", {"Aya"}),
        ("status=desabonnes", {"Yao"}),
        ("status=consentants", {"Aya"}),
        ("operator=mtn", {"Aya"}),
        ("operator=fixe", {"Bureau"}),
    ],
)
def test_contact_filters(auth_client, contacts, query, expected):
    body = auth_client.get(f"/contacts/?{query}").data.decode()
    shown = {c.first_name for c in contacts if f">{c.first_name}" in body}
    assert shown == expected


def test_group_filter(auth_client, contacts):
    vip = ContactGroup.query.filter_by(name="VIP").one()
    body = auth_client.get(f"/contacts/?group={vip.id}").data.decode()
    assert ">Koffi" in body and ">Aya" not in body


def test_export_csv_respects_filters(auth_client, contacts):
    resp = auth_client.get("/contacts/export.csv?operator=orange")
    text = resp.data.decode("utf-8-sig")
    assert resp.mimetype == "text/csv"
    lines = text.strip().splitlines()
    assert lines[0].startswith("prenom;nom;telephone")
    assert len(lines) == 2 and "07 12 34 56 78" in lines[1] and "Orange" in lines[1]


def test_import_semicolon_csv_with_consent_column(auth_client, db, business):
    data = "prenom;nom;telephone;consentement\nKoffi;K;07 12 34 56 78;oui\nAya;T;0512345678;non\n"
    auth_client.post(
        "/contacts/import",
        data={"file": (io.BytesIO(data.encode("utf-8")), "c.csv"), "group_id": 0},
        content_type="multipart/form-data",
    )
    by_name = {c.first_name: c for c in Contact.query.all()}
    assert by_name["Koffi"].consent_given is True
    assert by_name["Aya"].consent_given is False


def test_import_consent_all_checkbox(auth_client, db, business):
    data = "phone\n0712345678\n"
    auth_client.post(
        "/contacts/import",
        data={"file": (io.BytesIO(data.encode()), "c.csv"), "group_id": 0, "consent_all": "y"},
        content_type="multipart/form-data",
    )
    assert Contact.query.one().consent_given


def test_rename_group(auth_client, db, contacts):
    vip = ContactGroup.query.filter_by(name="VIP").one()
    auth_client.post(f"/contacts/groups/{vip.id}/edit", data={"name": "Clients VIP"})
    db.session.refresh(vip)
    assert vip.name == "Clients VIP"


PAGES_WITH_FORMS = [
    "/compte/", "/modeles/new",
    "/contacts/", "/contacts/new", "/contacts/groups", "/contacts/import", "/campaigns/new",
    "/billing/", "/change-password",
]


def test_every_post_form_carries_a_csrf_token(app, auth_client, db, contacts, user):
    """Régression : trois formulaires de suppression n'avaient pas de jeton
    CSRF et échouaient en production (les tests désactivent CSRF)."""
    from app.models.billing import CreditPackage
    from app.models.campaign import Campaign

    db.session.add(CreditPackage(name="Starter", credits=500, price_xof=9000, sort_order=1))
    campaign = Campaign(business_id=contacts[0].business_id, created_by_id=user.id, name="C", message_body="M")
    db.session.add(campaign)
    db.session.commit()

    app.config["WTF_CSRF_ENABLED"] = True
    pages = PAGES_WITH_FORMS + [f"/contacts/{contacts[0].id}/edit", f"/campaigns/{campaign.id}"]
    for page in pages:
        html = auth_client.get(page).data.decode()
        for form in re.findall(r"<form[^>]*method=\"POST\"[^>]*>.*?</form>", html, flags=re.S | re.I):
            assert 'name="csrf_token"' in form, f"Formulaire sans jeton CSRF sur {page} :\n{form[:200]}"
