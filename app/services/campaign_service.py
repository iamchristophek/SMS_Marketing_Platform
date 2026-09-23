"""Logique métier des campagnes.

Cycle de vie :
    brouillon ──(confirmation : liste figée + crédits réservés)──▶ planifiée
    planifiée ──(heure atteinte, tâche Celery)──▶ en cours ──▶ envoyée / échec
    planifiée ──(annulation)──▶ annulée (crédits rendus)

À la confirmation, chaque SMS devient une ligne `Message` « en attente »
avec son texte personnalisé et son coût exact : ce qui est réservé est
exactement ce qui partira. Un contact ajouté après la confirmation ne
reçoit donc pas la campagne (et n'est pas facturé), et un contact qui se
désabonne entre-temps est retiré au moment de l'envoi, crédits rendus.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import or_

from app.extensions import db
from app.models.campaign import Campaign, Message
from app.models.contact import Contact, ContactGroup
from app.services import billing_service
from app.services.phone import CI_COUNTRY_CODE, FIXED_PREFIXES
from app.services.sms import get_sms_provider
from app.services.sms.encoding import ENCODING_UCS2, analyze_message


class CampaignError(Exception):
    """Erreur métier affichable au client (pas de destinataire, etc.)."""


def utcnow():
    return datetime.now(timezone.utc)


# --- Personnalisation ---------------------------------------------------------

PLACEHOLDERS = {
    "prenom": lambda c: c.first_name or "",
    "prénom": lambda c: c.first_name or "",
    "nom": lambda c: c.last_name or "",
}
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}", re.UNICODE)


def render_message(body: str, contact) -> str:
    """Remplace {prenom} et {nom} par les valeurs du contact. Une variable
    vide ne laisse pas d'espace double (« Bonjour {prenom} ! » → « Bonjour ! »)."""

    def replace(match):
        getter = PLACEHOLDERS.get(match.group(1).lower())
        return getter(contact) if getter else match.group(0)

    rendered = _PLACEHOLDER_RE.sub(replace, body or "")
    return re.sub(r"[ \t]{2,}", " ", rendered).strip()


def has_placeholders(body: str) -> bool:
    return any(m.group(1).lower() in PLACEHOLDERS for m in _PLACEHOLDER_RE.finditer(body or ""))


# --- Destinataires -------------------------------------------------------------

def recipients_query(business_id, group_id=None, consent_only=False):
    """Contacts qui recevront une campagne : non désabonnés, pas de ligne
    fixe (elles ne reçoivent pas de SMS), du groupe choisi le cas échéant,
    et ayant donné leur consentement si demandé."""
    query = Contact.query.filter(Contact.business_id == business_id, Contact.opted_out.is_(False))
    query = query.filter(
        ~or_(*[Contact.phone_e164.like(f"+{CI_COUNTRY_CODE}{p}%") for p in FIXED_PREFIXES])
    )
    if group_id:
        query = query.filter(Contact.groups.any(ContactGroup.id == group_id))
    if consent_only:
        query = query.filter(Contact.consent_given.is_(True))
    return query


def get_recipients(campaign: Campaign):
    return recipients_query(campaign.business_id, campaign.group_id, campaign.consent_only).all()


@dataclass
class CampaignEstimate:
    recipients: int = 0
    total_segments: int = 0
    credits: int = 0
    encoding: str = "GSM-7"
    non_gsm_chars: tuple = ()
    segments_min: int = 0
    segments_max: int = 0
    excluded_opted_out: int = 0
    excluded_fixed: int = 0
    excluded_no_consent: int = 0
    sample: list = field(default_factory=list)  # [(contact, texte rendu)]


def estimate(campaign: Campaign, sms_cost_credits: int) -> CampaignEstimate:
    """Aperçu avant confirmation : destinataires, segments, coût exact
    (personnalisation comprise) et contacts écartés, avec la raison."""
    recipients = get_recipients(campaign)
    result = CampaignEstimate(recipients=len(recipients))
    base_info = analyze_message(campaign.message_body)
    result.encoding, result.non_gsm_chars = base_info.encoding, base_info.non_gsm_chars

    segments_list = []
    for contact in recipients:
        text = render_message(campaign.message_body, contact)
        info = analyze_message(text)
        segments_list.append(info.segments)
        if info.encoding == ENCODING_UCS2:
            result.encoding = ENCODING_UCS2
        if len(result.sample) < 3:
            result.sample.append((contact, text))
    result.total_segments = sum(segments_list)
    result.credits = result.total_segments * sms_cost_credits
    result.segments_min = min(segments_list, default=0)
    result.segments_max = max(segments_list, default=0)

    targeted = Contact.query.filter(Contact.business_id == campaign.business_id)
    if campaign.group_id:
        targeted = targeted.filter(Contact.groups.any(ContactGroup.id == campaign.group_id))
    result.excluded_opted_out = targeted.filter(Contact.opted_out.is_(True)).count()
    result.excluded_fixed = targeted.filter(
        Contact.opted_out.is_(False),
        or_(*[Contact.phone_e164.like(f"+{CI_COUNTRY_CODE}{p}%") for p in FIXED_PREFIXES]),
    ).count()
    if campaign.consent_only:
        reachable = recipients_query(campaign.business_id, campaign.group_id, consent_only=False)
        result.excluded_no_consent = reachable.filter(Contact.consent_given.is_(False)).count()
    return result


# --- Confirmation / réservation -------------------------------------------------

def reserve_credits(campaign: Campaign, sms_cost_credits: int):
    """Fige la liste des destinataires (un Message « en attente » par
    contact, texte personnalisé) et débite le coût exact. Lève
    InsufficientCreditsError si le solde ne suffit pas (rien n'est alors
    écrit : l'appelant fait le rollback)."""
    recipients = get_recipients(campaign)
    cost = 0
    for contact in recipients:
        text = render_message(campaign.message_body, contact)
        credits = analyze_message(text).segments * sms_cost_credits
        cost += credits
        db.session.add(
            Message(
                campaign_id=campaign.id,
                business_id=campaign.business_id,
                contact_id=contact.id,
                phone_e164=contact.phone_e164,
                body=text,
                status=Message.STATUS_PENDING,
                credits_used=0,
                # Coût réservé pour ce SMS, facturé seulement s'il part.
                credits_reserved=credits,
            )
        )
    if cost > 0:
        billing_service.debit_for_campaign(
            campaign.business, cost, campaign.id, f"Réservation campagne « {campaign.name} »"
        )
    campaign.credits_reserved = cost
    campaign.total_recipients = len(recipients)
    return recipients, cost


def launch(campaign: Campaign, sms_cost_credits: int, scheduled_at=None):
    """Confirme un brouillon : réserve les crédits puis le planifie (ou le
    met en file tout de suite). Ne fait pas le commit du lancement Celery :
    renvoie True si l'envoi doit partir immédiatement."""
    if campaign.status != Campaign.STATUS_DRAFT:
        raise CampaignError("Cette campagne a déjà été confirmée.")
    if not get_recipients(campaign):
        raise CampaignError(
            "Aucun destinataire : ajoutez des contacts (ou choisissez un autre groupe) avant d'envoyer."
        )
    reserve_credits(campaign, sms_cost_credits)

    now = utcnow()
    if scheduled_at and scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    campaign.status = Campaign.STATUS_SCHEDULED
    campaign.scheduled_at = scheduled_at if scheduled_at and scheduled_at > now else now
    return campaign.scheduled_at <= now


def cancel(campaign: Campaign):
    """Annule une campagne planifiée non encore partie : rend les crédits."""
    if campaign.status != Campaign.STATUS_SCHEDULED:
        raise CampaignError("Seule une campagne planifiée, pas encore partie, peut être annulée.")
    Message.query.filter_by(campaign_id=campaign.id, status=Message.STATUS_PENDING).delete(
        synchronize_session=False
    )
    campaign.status = Campaign.STATUS_CANCELLED
    campaign.completed_at = utcnow()
    _refund_unused(campaign, "Annulation")


# --- Envoi ----------------------------------------------------------------------

def _claim_campaign(campaign_id: int, resume: bool) -> bool:
    """Passe atomiquement la campagne en « sending ». Un seul worker peut
    réussir ce passage : protège contre un double envoi si la campagne est
    mise en file à la fois par la route web et par Celery beat. Un
    brouillon n'est jamais envoyé : il n'a pas de crédits réservés."""
    claimable = [Campaign.STATUS_SCHEDULED]
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
    sent = messages.filter(
        Message.status.in_([Message.STATUS_SENT, Message.STATUS_DELIVERED, Message.STATUS_UNDELIVERED])
    ).count()
    failed = messages.filter(Message.status == Message.STATUS_FAILED).count()
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
        # Ce qui est rendu n'est plus réservé : une seconde annulation ou un
        # échec final ne rembourse jamais deux fois.
        campaign.credits_reserved = campaign.credits_used or 0


def execute_campaign(campaign_id: int, sender_id: str, sms_cost_credits: int, resume: bool = False):
    """Envoie les SMS « en attente » d'une campagne planifiée. Conçu pour
    une tâche Celery (ou l'exécution immédiate en test/développement).

    `resume=True` (nouvelle tentative après une erreur) reprend une campagne
    restée « sending » : seuls les messages encore en attente partent, un
    SMS déjà envoyé ne l'est jamais deux fois."""
    if not _claim_campaign(campaign_id, resume):
        return None
    campaign = db.session.get(Campaign, campaign_id)
    if campaign.started_at is None:
        campaign.started_at = utcnow()
    # Campagne planifiée avant l'introduction des listes figées (aucun
    # message préparé) : on la fige maintenant, crédits compris.
    if campaign.messages.count() == 0 and not campaign.credits_reserved:
        reserve_credits(campaign, sms_cost_credits)
    db.session.commit()

    provider = get_sms_provider()
    pending = (
        Message.query.filter_by(campaign_id=campaign.id, status=Message.STATUS_PENDING)
        .order_by(Message.id)
        .all()
    )
    for message in pending:
        contact = message.contact
        if contact is not None and contact.opted_out:
            message.status = Message.STATUS_FAILED
            message.error_message = "Désabonné (STOP) avant l'envoi"
            db.session.commit()
            continue

        message.status = Message.STATUS_QUEUED
        message.queued_at = utcnow()
        result = provider.send(message.phone_e164, message.body, sender_id)
        message.provider = result.provider
        if result.success:
            message.status = Message.STATUS_SENT
            message.provider_message_id = result.provider_message_id
            message.sent_at = utcnow()
            message.credits_used = message.credits_reserved or (
                analyze_message(message.body).segments * sms_cost_credits
            )
        else:
            message.status = Message.STATUS_FAILED
            message.error_message = (result.error or "")[:255]
        db.session.commit()

    sent, failed, _ = _recompute_totals(campaign)
    campaign.status = Campaign.STATUS_SENT if failed == 0 or sent > 0 else Campaign.STATUS_FAILED
    campaign.completed_at = utcnow()
    # Rembourse les crédits réservés mais non consommés (échecs, désabonnés).
    _refund_unused(campaign, "Remboursement SMS non envoyés")
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
    Message.query.filter(
        Message.campaign_id == campaign.id,
        Message.status.in_([Message.STATUS_PENDING, Message.STATUS_QUEUED]),
    ).update(
        {Message.status: Message.STATUS_FAILED, Message.error_message: "Envoi interrompu"},
        synchronize_session=False,
    )
    _recompute_totals(campaign)
    campaign.status = Campaign.STATUS_FAILED
    campaign.completed_at = utcnow()
    _refund_unused(campaign, "Remboursement campagne en échec")
    db.session.commit()
    return campaign
