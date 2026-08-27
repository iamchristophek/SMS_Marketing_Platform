import logging
from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models.campaign import Campaign
from app.services import campaign_service
from app.tasks import celery_app

logger = logging.getLogger("tasks.sms")


@celery_app.task(name="app.tasks.sms_tasks.send_campaign", bind=True, max_retries=3, default_retry_delay=30)
def send_campaign(self, campaign_id: int):
    """Envoie une campagne (immédiatement ou parce que son heure planifiée
    est arrivée). Les échecs réseau transitoires déclenchent une nouvelle
    tentative automatique ; les envois individuels déjà réussis ne sont
    jamais rejoués (idempotence assurée par le statut de chaque Message)."""
    try:
        return campaign_service.execute_campaign(
            campaign_id,
            sender_id=current_app.config["SMS_SENDER_ID"],
            sms_cost_credits=current_app.config["SMS_COST_CREDITS"],
        )
    except Exception as exc:  # noqa: BLE001 - on journalise puis on relance via Celery
        logger.exception("Échec traitement campagne %s", campaign_id)
        campaign = Campaign.query.get(campaign_id)
        if campaign:
            campaign.status = Campaign.STATUS_FAILED
            db.session.commit()
        raise self.retry(exc=exc)


@celery_app.task(name="app.tasks.sms_tasks.dispatch_scheduled_campaigns")
def dispatch_scheduled_campaigns():
    """Tâche périodique (Celery beat) : recherche les campagnes planifiées
    dont l'heure d'envoi est arrivée et les met en file d'attente."""
    now = datetime.now(timezone.utc)
    due_campaigns = Campaign.query.filter(
        Campaign.status == Campaign.STATUS_SCHEDULED,
        Campaign.scheduled_at <= now,
    ).all()
    for campaign in due_campaigns:
        send_campaign.delay(campaign.id)
    return len(due_campaigns)
