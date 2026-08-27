from flask_login import current_user, login_required

from flask import render_template

from app.blueprints.dashboard import dashboard_bp
from app.models.campaign import Campaign
from app.models.contact import Contact


@dashboard_bp.route("/")
def index():
    return render_template("index.html")


@dashboard_bp.route("/dashboard")
@login_required
def home():
    business = current_user.business
    campaigns = (
        Campaign.query.filter_by(business_id=business.id)
        .order_by(Campaign.created_at.desc())
        .limit(5)
        .all()
    )
    total_campaigns = Campaign.query.filter_by(business_id=business.id).count()
    total_contacts = Contact.query.filter_by(business_id=business.id, opted_out=False).count()

    sent_campaigns = [c for c in Campaign.query.filter_by(business_id=business.id) if c.total_sent > 0]
    if sent_campaigns:
        average_open_rate = round(sum(c.open_rate for c in sent_campaigns) / len(sent_campaigns), 1)
    else:
        average_open_rate = 0

    monthly_messages = sum(c.total_sent for c in Campaign.query.filter_by(business_id=business.id))

    return render_template(
        "dashboard.html",
        business=business,
        campaigns=campaigns,
        total_campaigns=total_campaigns,
        total_contacts=total_contacts,
        monthly_messages=monthly_messages,
        average_open_rate=average_open_rate,
    )
