from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.campaigns import campaigns_bp
from app.blueprints.campaigns.forms import CampaignForm, ConfirmCampaignForm
from app.extensions import db
from app.models.billing import CreditTransaction
from app.models.campaign import Campaign, Message
from app.models.template import MessageTemplate
from app.services import campaign_service, contact_service
from app.services.billing_service import InsufficientCreditsError
from app.services.campaign_service import CampaignError
from app.tasks.sms_tasks import send_campaign


def _get_campaign(campaign_id):
    return Campaign.query.filter_by(id=campaign_id, business_id=current_user.business_id).first_or_404()


def _templates():
    return (
        MessageTemplate.query.filter_by(business_id=current_user.business_id)
        .order_by(MessageTemplate.name)
        .all()
    )


def _prepare_form(form):
    groups = contact_service.business_groups(current_user.business_id)
    form.group_id.choices = [(0, "Tous mes contacts")] + [
        (g.id, f"{g.name} ({g.active_contact_count})") for g in groups
    ]
    templates = _templates()
    form.template_id.choices = [(0, "— Aucun —")] + [(t.id, t.name) for t in templates]
    return templates


@campaigns_bp.route("/")
@login_required
def index():
    status = request.args.get("status", "")
    query = Campaign.query.filter_by(business_id=current_user.business_id)
    if status in Campaign.STATUS_LABELS:
        query = query.filter_by(status=status)
    pagination = query.order_by(Campaign.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False
    )
    return render_template(
        "campaigns/index.html",
        pagination=pagination,
        campaigns=pagination.items,
        status=status,
        status_labels=Campaign.STATUS_LABELS,
    )


@campaigns_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = CampaignForm()
    templates = _prepare_form(form)
    if request.method == "GET":
        template = next((t for t in templates if t.id == request.args.get("template", type=int)), None)
        if template:
            form.template_id.data = template.id
            form.message.data = template.body
            form.consent_only.data = template.category == MessageTemplate.CATEGORY_PROMOTIONAL
        form.group_id.data = request.args.get("group", 0, type=int)

    if form.validate_on_submit():
        campaign = Campaign(
            business_id=current_user.business_id,
            created_by_id=current_user.id,
            status=Campaign.STATUS_DRAFT,
        )
        _apply_form(form, campaign)
        db.session.add(campaign)
        db.session.commit()
        return redirect(url_for("campaigns.confirm", campaign_id=campaign.id))

    return render_template(
        "campaigns/form.html", form=form, title="Nouvelle campagne", templates=templates,
        templates_by_id={t.id: t.body for t in templates},
    )


@campaigns_bp.route("/<int:campaign_id>/edit", methods=["GET", "POST"])
@login_required
def edit(campaign_id):
    campaign = _get_campaign(campaign_id)
    if campaign.status != Campaign.STATUS_DRAFT:
        flash("Seul un brouillon peut être modifié.", "error")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    form = CampaignForm(obj=campaign)
    templates = _prepare_form(form)
    if request.method == "GET":
        form.message.data = campaign.message_body
        form.group_id.data = campaign.group_id or 0
    if form.validate_on_submit():
        _apply_form(form, campaign)
        db.session.commit()
        return redirect(url_for("campaigns.confirm", campaign_id=campaign.id))
    return render_template(
        "campaigns/form.html", form=form, title="Modifier la campagne", templates=templates, campaign=campaign,
        templates_by_id={t.id: t.body for t in templates},
    )


def _apply_form(form, campaign):
    group_id = form.group_id.data or None
    if group_id and group_id not in {g.id for g in contact_service.business_groups(current_user.business_id)}:
        group_id = None
    campaign.name = form.name.data
    campaign.message_body = form.message.data.strip()
    campaign.group_id = group_id
    campaign.consent_only = bool(form.consent_only.data)
    campaign.scheduled_at = form.scheduled_at.data


@campaigns_bp.route("/<int:campaign_id>/confirm", methods=["GET", "POST"])
@login_required
def confirm(campaign_id):
    """Aperçu avant envoi (repris de l'écran de confirmation du prototype) :
    destinataires, encodage, coût exact, solde après envoi."""
    campaign = _get_campaign(campaign_id)
    if campaign.status != Campaign.STATUS_DRAFT:
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    sms_cost = current_app.config["SMS_COST_CREDITS"]
    form = ConfirmCampaignForm()
    if form.validate_on_submit():
        try:
            send_now = campaign_service.launch(campaign, sms_cost, scheduled_at=campaign.scheduled_at)
        except (CampaignError, InsufficientCreditsError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("campaigns.confirm", campaign_id=campaign.id))
        db.session.commit()
        if send_now:
            send_campaign.delay(campaign.id)
            flash("Campagne confirmée : l'envoi est en cours.", "success")
        else:
            flash(f"Campagne planifiée pour le {campaign.scheduled_at:%d/%m/%Y à %H:%M}.", "success")
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    estimate = campaign_service.estimate(campaign, sms_cost)
    balance = current_user.business.credit_balance
    return render_template(
        "campaigns/confirm.html",
        campaign=campaign,
        estimate=estimate,
        balance=balance,
        balance_after=balance - estimate.credits,
        form=form,
    )


@campaigns_bp.route("/<int:campaign_id>")
@login_required
def detail(campaign_id):
    campaign = _get_campaign(campaign_id)
    if campaign.status == Campaign.STATUS_DRAFT:
        return redirect(url_for("campaigns.confirm", campaign_id=campaign.id))

    status = request.args.get("status", "")
    messages = campaign.messages
    if status in Message.STATUS_LABELS:
        messages = messages.filter_by(status=status)
    pagination = messages.order_by(Message.id).paginate(
        page=request.args.get("page", 1, type=int), per_page=50, error_out=False
    )
    counts = dict(
        db.session.query(Message.status, db.func.count(Message.id))
        .filter(Message.campaign_id == campaign.id)
        .group_by(Message.status)
        .all()
    )
    return render_template(
        "campaigns/detail.html",
        campaign=campaign,
        pagination=pagination,
        messages=pagination.items,
        status=status,
        counts=counts,
        message_labels=Message.STATUS_LABELS,
        has_delivery_reports=bool(counts.get(Message.STATUS_DELIVERED) or counts.get(Message.STATUS_UNDELIVERED)),
    )


@campaigns_bp.route("/<int:campaign_id>/cancel", methods=["POST"])
@login_required
def cancel(campaign_id):
    campaign = _get_campaign(campaign_id)
    try:
        campaign_service.cancel(campaign)
    except CampaignError as exc:
        flash(str(exc), "error")
    else:
        db.session.commit()
        flash("Campagne annulée : les crédits réservés vous ont été rendus.", "info")
    return redirect(url_for("campaigns.detail", campaign_id=campaign.id))


@campaigns_bp.route("/<int:campaign_id>/duplicate", methods=["POST"])
@login_required
def duplicate(campaign_id):
    source = _get_campaign(campaign_id)
    copy = Campaign(
        business_id=current_user.business_id,
        created_by_id=current_user.id,
        name=f"{source.name} (copie)"[:120],
        message_body=source.message_body,
        group_id=source.group_id,
        consent_only=source.consent_only,
        status=Campaign.STATUS_DRAFT,
    )
    db.session.add(copy)
    db.session.commit()
    flash("Campagne dupliquée : vérifiez-la puis confirmez l'envoi.", "success")
    return redirect(url_for("campaigns.edit", campaign_id=copy.id))


@campaigns_bp.route("/<int:campaign_id>/delete", methods=["POST"])
@login_required
def delete(campaign_id):
    campaign = _get_campaign(campaign_id)
    if campaign.status not in (Campaign.STATUS_DRAFT, Campaign.STATUS_CANCELLED):
        flash(
            "Seuls les brouillons et les campagnes annulées peuvent être supprimés "
            "(annulez d'abord une campagne planifiée).",
            "error",
        )
        return redirect(url_for("campaigns.detail", campaign_id=campaign.id))

    # Le journal des crédits est conservé (source de vérité comptable) :
    # on détache les transactions de la campagne avant de la supprimer.
    CreditTransaction.query.filter_by(campaign_id=campaign.id).update(
        {CreditTransaction.campaign_id: None}, synchronize_session=False
    )
    db.session.delete(campaign)
    db.session.commit()
    flash("Campagne supprimée.", "info")
    return redirect(url_for("campaigns.index"))
