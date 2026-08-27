from datetime import datetime, timezone

from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.campaigns import campaigns_bp
from app.blueprints.campaigns.forms import CampaignForm
from app.extensions import db
from app.models.campaign import Campaign
from app.models.contact import ContactGroup
from app.services import campaign_service
from app.services.billing_service import InsufficientCreditsError
from app.tasks.sms_tasks import send_campaign


def _group_choices():
    groups = ContactGroup.query.filter_by(business_id=current_user.business_id).order_by(
        ContactGroup.name
    )
    return [(0, "Tous les contacts")] + [(g.id, g.name) for g in groups]


@campaigns_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Campaign.query.filter_by(business_id=current_user.business_id)
        .order_by(Campaign.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template("campaigns/index.html", pagination=pagination, campaigns=pagination.items)


@campaigns_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = CampaignForm()
    form.group_id.choices = _group_choices()

    if form.validate_on_submit():
        campaign = Campaign(
            business_id=current_user.business_id,
            created_by_id=current_user.id,
            name=form.name.data,
            message_body=form.message.data,
            group_id=form.group_id.data or None,
            status=Campaign.STATUS_DRAFT,
        )
        db.session.add(campaign)
        db.session.flush()

        now = datetime.now(timezone.utc)
        scheduled_at = form.scheduled_at.data
        if scheduled_at and scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        is_future = bool(scheduled_at and scheduled_at > now)

        try:
            campaign_service.reserve_credits(campaign, current_app.config["SMS_COST_CREDITS"])
        except InsufficientCreditsError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_template("campaigns/form.html", form=form, title="Nouvelle campagne")

        if is_future:
            campaign.status = Campaign.STATUS_SCHEDULED
            campaign.scheduled_at = scheduled_at
            db.session.commit()
            flash(f"Campagne planifiée pour le {scheduled_at:%d/%m/%Y à %H:%M}.", "success")
        else:
            campaign.status = Campaign.STATUS_SCHEDULED
            campaign.scheduled_at = now
            db.session.commit()
            send_campaign.delay(campaign.id)
            flash("Campagne en cours d'envoi.", "success")

        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    return render_template("campaigns/form.html", form=form, title="Nouvelle campagne")


@campaigns_bp.route("/<int:campaign_id>")
@login_required
def detail(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, business_id=current_user.business_id
    ).first_or_404()
    return render_template("campaigns/detail.html", campaign=campaign)


@campaigns_bp.route("/<int:campaign_id>/delete", methods=["POST"])
@login_required
def delete(campaign_id):
    campaign = Campaign.query.filter_by(
        id=campaign_id, business_id=current_user.business_id
    ).first_or_404()
    if not campaign.is_editable():
        flash("Seules les campagnes brouillon ou planifiées peuvent être supprimées.", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    from app.services import billing_service

    if campaign.credits_reserved:
        billing_service.refund_for_campaign(
            campaign.business,
            campaign.credits_reserved,
            campaign.id,
            f"Annulation campagne « {campaign.name} »",
        )
    db.session.delete(campaign)
    db.session.commit()
    flash("Campagne supprimée avec succès.", "info")
    return redirect(url_for("campaigns.index"))
