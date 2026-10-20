import pytest

from app.models.campaign import Campaign
from app.services.content_check import check_message


@pytest.mark.parametrize("text", [
    "Orange Money: votre compte est bloqué, envoyez votre code secret au 0700000000",
    "Envoyez-nous le code reçu par SMS pour valider votre gain",
    "Tapez #144*1*0700000000*5000# pour recevoir votre bonus",
])
def test_scam_messages_are_blocked(text):
    assert not check_message(text).ok


@pytest.mark.parametrize("text", [
    "Bonjour {prenom}, -20% sur les pagnes ce week-end chez Maman Adjoua. STOP au 1234",
    "Votre commande est prête, passez la récupérer. Rep STOP pour arreter",
])
def test_normal_messages_pass(text):
    result = check_message(text)
    assert result.ok and not result.warnings


def test_mobile_money_mention_is_a_warning():
    result = check_message("Payez par Wave et gagnez 5% de remise")
    assert result.ok and result.warnings


def test_launch_refuses_scam(auth_client, db, business, user):
    from app.models.contact import Contact

    db.session.add(Contact(business_id=business.id, phone_e164="+2250712345678"))
    c = Campaign(business_id=business.id, created_by_id=user.id, name="X",
                 message_body="Votre SIM sera suspendue, envoyez votre code PIN")
    db.session.add(c)
    db.session.commit()
    assert "arnaque" in auth_client.get(f"/campaigns/{c.id}/confirm").data.decode()
    auth_client.post(f"/campaigns/{c.id}/confirm", data={})
    db.session.refresh(c)
    assert c.status == Campaign.STATUS_DRAFT
