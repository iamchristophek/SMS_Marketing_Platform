from flask import Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.contacts import contacts_bp
from app.blueprints.contacts.forms import BulkActionForm, ContactForm, GroupForm, ImportContactsForm
from app.extensions import db
from app.models.campaign import Campaign
from app.models.contact import Contact, ContactGroup
from app.services import contact_service
from app.services.phone import OPERATOR_LABELS, InvalidPhoneNumberError, normalize_phone


def _get_contact(contact_id):
    return Contact.query.filter_by(id=contact_id, business_id=current_user.business_id).first_or_404()


def _get_group(group_id):
    return ContactGroup.query.filter_by(id=group_id, business_id=current_user.business_id).first_or_404()


def _filters():
    return {
        "q": request.args.get("q", "").strip(),
        "group_id": request.args.get("group", type=int),
        "status": request.args.get("status", ""),
        "operator": request.args.get("operator", ""),
    }


def _group_choices(empty_label="Aucun groupe"):
    groups = contact_service.business_groups(current_user.business_id)
    return [(0, empty_label)] + [(g.id, g.name) for g in groups]


@contacts_bp.route("/")
@login_required
def index():
    filters = _filters()
    query = contact_service.filtered_contacts(current_user.business_id, **filters)
    pagination = query.order_by(Contact.created_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=25, error_out=False
    )
    bulk_form = BulkActionForm()
    bulk_form.group_id.choices = _group_choices("— choisir un groupe —")
    return render_template(
        "contacts/index.html",
        pagination=pagination,
        contacts=pagination.items,
        groups=contact_service.business_groups(current_user.business_id),
        filters=filters,
        status_filters=contact_service.STATUS_FILTERS,
        operator_labels=OPERATOR_LABELS,
        total=pagination.total,
        bulk_form=bulk_form,
    )


def _save_contact(form, contact=None):
    """Valide le numéro puis crée ou met à jour le contact. Renvoie le
    contact, ou None après avoir signalé l'erreur sur le formulaire."""
    try:
        phone = normalize_phone(form.phone.data)
    except InvalidPhoneNumberError as exc:
        form.phone.errors.append(str(exc))
        return None
    if contact_service.phone_in_use(current_user.business_id, phone, contact.id if contact else None):
        form.phone.errors.append("Un contact avec ce numéro existe déjà.")
        return None

    if contact is None:
        contact = Contact(business_id=current_user.business_id)
        db.session.add(contact)
    contact.first_name = form.first_name.data or None
    contact.last_name = form.last_name.data or None
    contact.phone_e164 = phone
    contact.email = form.email.data or None
    contact.set_consent(bool(form.consent_given.data))
    if contact.opted_out and form.resubscribe.data:
        contact.opted_out = False
        contact.opted_out_at = None
    contact.groups = ContactGroup.query.filter(
        ContactGroup.business_id == current_user.business_id,
        ContactGroup.id.in_(form.groups.data or []),
    ).all()
    return contact


@contacts_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = ContactForm()
    form.groups.choices = _group_choices()[1:]
    if request.method == "GET" and request.args.get("group", type=int):
        form.groups.data = [request.args.get("group", type=int)]
    if form.validate_on_submit() and _save_contact(form):
        db.session.commit()
        flash("Contact ajouté avec succès.", "success")
        return redirect(url_for("contacts.index"))
    return render_template("contacts/form.html", form=form, title="Nouveau contact", contact=None)


@contacts_bp.route("/<int:contact_id>/edit", methods=["GET", "POST"])
@login_required
def edit(contact_id):
    contact = _get_contact(contact_id)
    form = ContactForm(obj=contact)
    form.groups.choices = _group_choices()[1:]
    if request.method == "GET":
        form.phone.data = contact.phone_display
        form.groups.data = [g.id for g in contact.groups]
    if form.validate_on_submit() and _save_contact(form, contact):
        db.session.commit()
        flash("Contact mis à jour.", "success")
        return redirect(request.args.get("next") or url_for("contacts.index"))
    messages = contact.messages[-10:] if contact.messages else []
    return render_template(
        "contacts/form.html", form=form, title="Modifier le contact", contact=contact, messages=messages
    )


@contacts_bp.route("/<int:contact_id>/delete", methods=["POST"])
@login_required
def delete(contact_id):
    contact = _get_contact(contact_id)
    db.session.delete(contact)
    db.session.commit()
    flash("Contact supprimé.", "info")
    # Revenir à la liste (filtres conservés), jamais à la fiche du contact
    # qui vient d'être supprimé (404).
    back = request.referrer or ""
    if f"/contacts/{contact_id}/" in back or "/contacts/" not in back:
        back = url_for("contacts.index")
    return redirect(back)


@contacts_bp.route("/bulk", methods=["POST"])
@login_required
def bulk():
    form = BulkActionForm()
    form.group_id.choices = _group_choices("— choisir un groupe —")
    back = request.referrer or url_for("contacts.index")
    if not form.validate_on_submit():
        flash("Action invalide.", "error")
        return redirect(back)

    ids = [int(i) for i in request.form.getlist("contact_ids") if i.isdigit()]
    contacts = Contact.query.filter(
        Contact.business_id == current_user.business_id, Contact.id.in_(ids)
    ).all()
    if not contacts:
        flash("Cochez au moins un contact.", "error")
        return redirect(back)

    action = form.action.data
    if action in ("add_to_group", "remove_from_group"):
        if not form.group_id.data:
            flash("Choisissez un groupe.", "error")
            return redirect(back)
        group = _get_group(form.group_id.data)
        for contact in contacts:
            if action == "add_to_group" and group not in contact.groups:
                contact.groups.append(group)
            elif action == "remove_from_group" and group in contact.groups:
                contact.groups.remove(group)
        verb = "ajouté(s) au" if action == "add_to_group" else "retiré(s) du"
        message = f"{len(contacts)} contact(s) {verb} groupe « {group.name} »."
    elif action == "consent":
        for contact in contacts:
            contact.set_consent(True)
        message = f"Consentement enregistré pour {len(contacts)} contact(s)."
    elif action == "delete":
        for contact in contacts:
            db.session.delete(contact)
        message = f"{len(contacts)} contact(s) supprimé(s)."
    else:
        abort(400)

    db.session.commit()
    flash(message, "success")
    return redirect(back)


@contacts_bp.route("/export.csv")
@login_required
def export():
    contacts = (
        contact_service.filtered_contacts(current_user.business_id, **_filters())
        .order_by(Contact.created_at.desc())
        .all()
    )
    return Response(
        contact_service.export_csv(contacts),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"},
    )


# --- Groupes ---------------------------------------------------------------

@contacts_bp.route("/groups")
@login_required
def groups():
    return render_template(
        "contacts/groups.html", groups=contact_service.business_groups(current_user.business_id)
    )


@contacts_bp.route("/groups/new", methods=["GET", "POST"])
@login_required
def new_group():
    return _group_form(None)


@contacts_bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id):
    return _group_form(_get_group(group_id))


def _group_form(group):
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        duplicate = ContactGroup.query.filter(
            ContactGroup.business_id == current_user.business_id,
            ContactGroup.name == form.name.data,
            ContactGroup.id != (group.id if group else 0),
        ).first()
        if duplicate:
            form.name.errors.append("Un groupe avec ce nom existe déjà.")
        else:
            if group is None:
                group = ContactGroup(business_id=current_user.business_id)
                db.session.add(group)
            group.name = form.name.data
            group.description = form.description.data or None
            db.session.commit()
            flash("Groupe enregistré.", "success")
            return redirect(url_for("contacts.group_detail", group_id=group.id))
    return render_template("contacts/group_form.html", form=form, group=group)


@contacts_bp.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    return redirect(url_for("contacts.index", group=_get_group(group_id).id))


@contacts_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
    group = _get_group(group_id)

    # Supprimer le groupe ciblé par une campagne encore à envoyer la ferait
    # basculer sur « tous les contacts » : on refuse.
    active = Campaign.query.filter(
        Campaign.group_id == group.id,
        Campaign.status.in_(Campaign.ACTIVE_STATUSES + (Campaign.STATUS_SENDING,)),
    ).count()
    if active:
        flash(
            "Ce groupe est ciblé par une campagne non encore envoyée : "
            "supprimez ou modifiez d'abord cette campagne.",
            "error",
        )
        return redirect(url_for("contacts.groups"))

    Campaign.query.filter_by(group_id=group.id).update(
        {Campaign.group_id: None}, synchronize_session=False
    )
    db.session.delete(group)
    db.session.commit()
    flash("Groupe supprimé (les contacts sont conservés).", "info")
    return redirect(url_for("contacts.groups"))


# --- Import ------------------------------------------------------------------

@contacts_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_contacts():
    form = ImportContactsForm()
    form.group_id.choices = _group_choices()

    if form.validate_on_submit():
        target_group = _get_group(form.group_id.data) if form.group_id.data else None
        created, duplicates, invalid = contact_service.import_csv(
            current_user.business_id,
            form.file.data.stream.read(),
            target_group=target_group,
            consent_all=form.consent_all.data,
        )
        db.session.commit()
        flash(
            f"Import terminé : {created} contact(s) ajouté(s), {duplicates} doublon(s) ignoré(s), "
            f"{invalid} numéro(s) invalide(s).",
            "success" if created else "info",
        )
        return redirect(url_for("contacts.index"))

    return render_template("contacts/import.html", form=form)
