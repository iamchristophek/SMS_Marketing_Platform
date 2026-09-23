"""Chiffres du tableau de bord client. Les agrégations restent portables
SQLite (développement, tests) / PostgreSQL (production)."""
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from app.extensions import db
from app.models.billing import CreditTransaction
from app.models.campaign import Campaign, Message
from app.models.contact import Contact
from app.services.phone import OPERATOR_LABELS, detect_operator

SENT_STATUSES = (Message.STATUS_SENT, Message.STATUS_DELIVERED, Message.STATUS_UNDELIVERED)


def _as_utc(value: datetime) -> datetime:
    # SQLite rend des dates sans fuseau ; elles sont stockées en UTC.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def month_start(today: date | None = None) -> datetime:
    today = today or datetime.now(timezone.utc).date()
    return datetime.combine(today.replace(day=1), time.min, tzinfo=timezone.utc)


@dataclass
class DashboardStats:
    sms_sent_month: int = 0
    credits_used_month: int = 0
    campaigns_month: int = 0
    active_contacts: int = 0
    consenting_contacts: int = 0
    opted_out_contacts: int = 0
    delivered: int = 0
    undelivered: int = 0
    daily: list = field(default_factory=list)  # [(date, nombre de SMS)]
    operators: list = field(default_factory=list)  # [(libellé, nombre, pourcentage)]

    @property
    def delivery_rate(self):
        """Taux de livraison, seulement s'il existe des accusés de livraison
        (sinon None : afficher 0 % serait faux)."""
        total = self.delivered + self.undelivered
        return round(self.delivered * 100 / total, 1) if total else None

    @property
    def daily_max(self):
        return max((n for _, n in self.daily), default=0)


def daily_sent(business_id, days=30, today: date | None = None):
    today = today or datetime.now(timezone.utc).date()
    first_day = today - timedelta(days=days - 1)
    since = datetime.combine(first_day, time.min, tzinfo=timezone.utc)
    rows = (
        db.session.query(Message.sent_at)
        .filter(
            Message.business_id == business_id,
            Message.status.in_(SENT_STATUSES),
            Message.sent_at >= since,
        )
        .all()
    )
    counts = Counter(_as_utc(sent_at).date() for (sent_at,) in rows if sent_at)
    return [(first_day + timedelta(days=i), counts.get(first_day + timedelta(days=i), 0)) for i in range(days)]


def operator_breakdown(business_id):
    phones = db.session.query(Contact.phone_e164).filter(
        Contact.business_id == business_id, Contact.opted_out.is_(False)
    )
    counts = Counter(detect_operator(phone) for (phone,) in phones)
    total = sum(counts.values())
    return [
        (OPERATOR_LABELS[op], counts[op], round(counts[op] * 100 / total) if total else 0)
        for op in OPERATOR_LABELS
        if counts.get(op)
    ]


def dashboard_stats(business_id) -> DashboardStats:
    start = month_start()
    stats = DashboardStats()

    stats.sms_sent_month = Message.query.filter(
        Message.business_id == business_id,
        Message.status.in_(SENT_STATUSES),
        Message.sent_at >= start,
    ).count()

    # Crédits réellement consommés ce mois : débits moins remboursements
    # (une réservation rendue après annulation ne compte pas).
    net = (
        db.session.query(db.func.coalesce(db.func.sum(CreditTransaction.amount), 0))
        .filter(
            CreditTransaction.business_id == business_id,
            CreditTransaction.type.in_([CreditTransaction.TYPE_CONSUMPTION, CreditTransaction.TYPE_REFUND]),
            CreditTransaction.created_at >= start,
        )
        .scalar()
    )
    stats.credits_used_month = max(0, -int(net))

    stats.campaigns_month = Campaign.query.filter(
        Campaign.business_id == business_id,
        Campaign.status.in_([Campaign.STATUS_SENT, Campaign.STATUS_SENDING, Campaign.STATUS_FAILED]),
        Campaign.started_at >= start,
    ).count()

    contacts = Contact.query.filter_by(business_id=business_id)
    stats.active_contacts = contacts.filter(Contact.opted_out.is_(False)).count()
    stats.opted_out_contacts = contacts.filter(Contact.opted_out.is_(True)).count()
    stats.consenting_contacts = contacts.filter(
        Contact.opted_out.is_(False), Contact.consent_given.is_(True)
    ).count()

    by_status = dict(
        db.session.query(Message.status, db.func.count(Message.id))
        .filter(Message.business_id == business_id)
        .group_by(Message.status)
        .all()
    )
    stats.delivered = by_status.get(Message.STATUS_DELIVERED, 0)
    stats.undelivered = by_status.get(Message.STATUS_UNDELIVERED, 0)

    stats.daily = daily_sent(business_id)
    stats.operators = operator_breakdown(business_id)
    return stats


def nice_ticks(maximum: int, count: int = 4):
    """Graduations rondes (0, 5, 10… / 0, 250, 500…) pour l'axe vertical."""
    if maximum <= 0:
        return [0, 1]
    raw = maximum / count
    magnitude = 10 ** (len(str(int(raw))) - 1)
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    step = max(1, int(step)) if step >= 1 else 1
    top = step * -(-maximum // step)
    return list(range(0, int(top) + 1, int(step)))
