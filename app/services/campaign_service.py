"""Logique métier des campagnes : résolution des destinataires, calcul du
coût en crédits, exécution de l'envoi (utilisée par la tâche Celery
asynchrone comme par le mode d'exécution immédiate en tests/développement).
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models.campaign import Campaign, Message, compute_sms_segments
from app.models.contact import Contact
from app.services import billing_service
from app.services.billing_service import InsufficientCreditsError
from app.services.sms import get_sms_provider


def utcnow():
    return datetime.now(timezone.utc)


def get_recipients(campaign: Campaign):
    """Retourne la liste des contacts actifs (non désabonnés) ciblés par
    la campagne : soit un groupe précis, soit tous les contacts de
    l'entreprise."""
    query = Contact.query.filter_by(business_id=campaign.business_id, opted_out=False)
    if campaign.group_id:
        query = query.filter(Contact.groups.any(id=campaign.group_id))
    return query.all()


def estimate_cost(campaign: Campaign, sms_cost_credits: int, recipient_count: int | None = None) -> int:
    segments = compute_sms_segments(campaign.message_body)
    count = recipient_count if recipient_count is not None else len(get_recipients(campaign))
    return segments * sms_cost_credits * count


def reserve_credits(campaign: Campaign, sms_cost_credits: int):
    """Réserve (débite) les crédits nécessaires avant l'envoi. Toute
    campagne DOIT réserver ses crédits avant de passer en file d'attente,
    pour éviter qu'une entreprise dépense plus que son solde en lançant
    plusieurs campagnes simultanément."""
    recipients = get_recipients(campaign)
    cost = estimate_cost(campaign, sms_cost_credits, len(recipients))
    if cost > 0:
        billing_service.debit_for_campaign(
            campaign.business, cost, campaign.id, f"Réservation campagne « {campaign.name} »"
        )
    campaign.credits_reserved = cost
    campaign.total_recipients = len(recipients)
    return recipients, cost


def execute_campaign(campaign_id: int, sender_id: str, sms_cost_credits: int):
    """Envoie effectivement les SMS d'une campagne déjà planifiée/en file
    d'attente. Conçu pour être appelé depuis une tâche Celery (ou
    directement en environnement de test avec CELERY_TASK_ALWAYS_EAGER)."""
    campaign = Campaign.query.get(campaign_id)
    if campaign is None:
        return
    if campaign.status not in (Campaign.STATUS_SCHEDULED, Campaign.STATUS_DRAFT):
        return

    provider = get_sms_provider()
    campaign.status = Campaign.STATUS_SENDING
    campaign.started_at = utcnow()
    db.session.commit()

    recipients = get_recipients(campaign)
    segments = compute_sms_segments(campaign.message_body)
    sent, failed, credits_used = 0, 0, 0

    for contact in recipients:
        message = Message(
            campaign_id=campaign.id,
            business_id=campaign.business_id,
            contact_id=contact.id,
            phone_e164=contact.phone_e164,
            body=campaign.message_body,
            status=Message.STATUS_QUEUED,
        )
        db.session.add(message)
        db.session.flush()

        result = provider.send(contact.phone_e164, campaign.message_body, sender_id)
        message.provider = result.provider
        if result.success:
            message.status = Message.STATUS_SENT
            message.provider_message_id = result.provider_message_id
            message.sent_at = utcnow()
            message.credits_used = segments * sms_cost_credits
            sent += 1
            credits_used += message.credits_used
        else:
            message.status = Message.STATUS_FAILED
            message.error_message = (result.error or "")[:255]
            failed += 1

        db.session.commit()

    campaign.total_sent = sent
    campaign.total_failed = failed
    campaign.credits_used = credits_used
    campaign.status = Campaign.STATUS_SENT if failed == 0 or sent > 0 else Campaign.STATUS_FAILED
    campaign.completed_at = utcnow()

    # Rembourse les crédits réservés mais non consommés (échecs d'envoi).
    unused = campaign.credits_reserved - credits_used
    if unused > 0:
        billing_service.refund_for_campaign(
            campaign.business, unused, campaign.id, f"Remboursement échecs « {campaign.name} »"
        )

    db.session.commit()
    return campaign
