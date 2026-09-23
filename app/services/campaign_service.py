"""Logique métier des campagnes : résolution des destinataires, calcul du
coût en crédits, exécution de l'envoi (utilisée par la tâche Celery
asynchrone comme par le mode d'exécution immédiate en tests/développement).
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models.campaign import Campaign, Message, compute_sms_segments
from app.models.contact import Contact
from app.services import billing_service
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


def _claim_campaign(campaign_id: int, resume: bool) -> bool:
    """Passe atomiquement la campagne en « sending ». Un seul worker peut
    réussir ce passage : protège contre un double envoi si la campagne est
    mise en file à la fois par la route web et par Celery beat."""
    claimable = [Campaign.STATUS_SCHEDULED, Campaign.STATUS_DRAFT]
    if resume:
        claimable.append(Campaign.STATUS_SENDING)
    updated = Campaign.query.filter(
        Campaign.id == campaign_id, Campaign.status.in_(claimable)
    ).update({Campaign.status: Campaign.STATUS_SENDING}, synchronize_session=False)
    db.session.commit()
    return updated == 1


def _recompute_totals(campaign: Campaign):
    """Recalcule les compteurs à partir des messages réellement enregistrés
    (source de vérité, y compris après une reprise sur incident)."""
    messages = Message.query.filter_by(campaign_id=campaign.id)
    failed = messages.filter(Message.status == Message.STATUS_FAILED).count()
    sent = messages.filter(Message.status != Message.STATUS_FAILED).count()
    credits_used = (
        db.session.query(db.func.coalesce(db.func.sum(Message.credits_used), 0))
        .filter(Message.campaign_id == campaign.id)
        .scalar()
    )
    campaign.total_sent = sent
    campaign.total_failed = failed
    campaign.credits_used = int(credits_used)
    return sent, failed, int(credits_used)


def _refund_unused(campaign: Campaign, reason: str):
    unused = (campaign.credits_reserved or 0) - (campaign.credits_used or 0)
    if unused > 0:
        billing_service.refund_for_campaign(
            campaign.business, unused, campaign.id, f"{reason} « {campaign.name} »"
        )


def execute_campaign(campaign_id: int, sender_id: str, sms_cost_credits: int, resume: bool = False):
    """Envoie effectivement les SMS d'une campagne déjà planifiée/en file
    d'attente. Conçu pour être appelé depuis une tâche Celery (ou
    directement en environnement de test avec CELERY_TASK_ALWAYS_EAGER).

    `resume=True` (nouvelle tentative Celery après une erreur) autorise la
    reprise d'une campagne restée « sending » : les contacts ayant déjà un
    message pour cette campagne ne sont jamais relancés."""
    if not _claim_campaign(campaign_id, resume):
        return None
    campaign = db.session.get(Campaign, campaign_id)
    if campaign.started_at is None:
        campaign.started_at = utcnow()
        db.session.commit()

    provider = get_sms_provider()
    segments = compute_sms_segments(campaign.message_body)
    already_handled = {
        contact_id
        for (contact_id,) in db.session.query(Message.contact_id).filter(
            Message.campaign_id == campaign.id, Message.contact_id.isnot(None)
        )
    }

    for contact in get_recipients(campaign):
        if contact.id in already_handled:
            continue
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
        else:
            message.status = Message.STATUS_FAILED
            message.error_message = (result.error or "")[:255]

        db.session.commit()

    sent, failed, _ = _recompute_totals(campaign)
    campaign.status = Campaign.STATUS_SENT if failed == 0 or sent > 0 else Campaign.STATUS_FAILED
    campaign.completed_at = utcnow()

    # Rembourse les crédits réservés mais non consommés (échecs d'envoi).
    _refund_unused(campaign, "Remboursement échecs")

    db.session.commit()
    return campaign


def mark_campaign_failed(campaign_id: int):
    """Échec définitif (toutes les tentatives épuisées) : la campagne passe
    en « failed » et les crédits réservés non consommés sont remboursés.
    Idempotent : ne fait rien si la campagne est déjà terminée."""
    campaign = db.session.get(Campaign, campaign_id)
    if campaign is None or campaign.status in (
        Campaign.STATUS_SENT,
        Campaign.STATUS_FAILED,
        Campaign.STATUS_CANCELLED,
    ):
        return campaign
    _recompute_totals(campaign)
    campaign.status = Campaign.STATUS_FAILED
    campaign.completed_at = utcnow()
    _refund_unused(campaign, "Remboursement campagne en échec")
    db.session.commit()
    return campaign
