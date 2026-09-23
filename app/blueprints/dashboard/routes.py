from flask import current_app, render_template
from flask_login import current_user, login_required

from app.blueprints.dashboard import dashboard_bp
from app.models.campaign import Campaign
from app.models.contact import Contact
from app.services import stats_service


@dashboard_bp.route("/")
def index():
    return render_template("index.html")


@dashboard_bp.route("/dashboard")
@login_required
def home():
    business = current_user.business
    campaigns = Campaign.query.filter_by(business_id=business.id)
    recent = (
        campaigns.filter(Campaign.status != Campaign.STATUS_DRAFT)
        .order_by(Campaign.created_at.desc())
        .limit(5)
        .all()
    )
    drafts = campaigns.filter_by(status=Campaign.STATUS_DRAFT).order_by(Campaign.created_at.desc()).all()
    upcoming = (
        campaigns.filter_by(status=Campaign.STATUS_SCHEDULED).order_by(Campaign.scheduled_at).limit(5).all()
    )
    stats = stats_service.dashboard_stats(business.id)
    has_contacts = Contact.query.filter_by(business_id=business.id).first() is not None

    return render_template(
        "dashboard.html",
        business=business,
        stats=stats,
        ticks=stats_service.nice_ticks(stats.daily_max),
        recent=recent,
        drafts=drafts,
        upcoming=upcoming,
        has_contacts=has_contacts,
        has_campaigns=bool(recent or drafts or upcoming),
        low_balance=business.credit_balance < current_app.config["LOW_BALANCE_THRESHOLD"],
    )
