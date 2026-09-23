from app.models.template import MessageTemplate


def test_create_edit_delete_template(auth_client, db, business):
    auth_client.post("/modeles/new", data={"name": "Relance", "category": "informational", "body": "Bonjour {prenom}"})
    template = MessageTemplate.query.one()
    assert template.business_id == business.id and template.category_label == "Informatif"

    auth_client.post(
        f"/modeles/{template.id}/edit", data={"name": "Relance", "category": "promotional", "body": "Promo"}
    )
    db.session.refresh(template)
    assert template.body == "Promo"

    html = auth_client.get("/modeles/").data.decode()
    assert "Relance" in html and "GSM-7" in html

    auth_client.post(f"/modeles/{template.id}/delete")
    assert MessageTemplate.query.count() == 0


def test_template_name_unique_per_business(auth_client, db, business):
    auth_client.post("/modeles/new", data={"name": "Relance", "category": "informational", "body": "A"})
    resp = auth_client.post("/modeles/new", data={"name": "Relance", "category": "informational", "body": "B"})
    assert "existe déjà".encode() in resp.data
    assert MessageTemplate.query.count() == 1


def test_template_of_other_business_is_404(auth_client, db):
    from app.models.user import Business

    other = Business(name="Autre")
    db.session.add(other)
    db.session.commit()
    template = MessageTemplate(business_id=other.id, name="X", body="Y")
    db.session.add(template)
    db.session.commit()
    assert auth_client.get(f"/modeles/{template.id}/edit").status_code == 404
