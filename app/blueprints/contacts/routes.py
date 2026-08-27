import csv
import io

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.blueprints.contacts import contacts_bp
from app.blueprints.contacts.forms import ContactForm, GroupForm, ImportContactsForm
from app.extensions import db
from app.models.contact import Contact, ContactGroup
from app.services.phone import InvalidPhoneNumberError, normalize_phone


def _group_choices():
    groups = ContactGroup.query.filter_by(business_id=current_user.business_id).order_by(
        ContactGroup.name
    )
    return [(0, "Aucun groupe")] + [(g.id, g.name) for g in groups]


@contacts_bp.route("/")
@login_required
def index():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Contact.query.filter_by(business_id=current_user.business_id)
        .order_by(Contact.created_at.desc())
        .paginate(page=page, per_page=25, error_out=False)
    )
    groups = ContactGroup.query.filter_by(business_id=current_user.business_id).order_by(ContactGroup.name).all()
    return render_template("contacts/index.html", pagination=pagination, contacts=pagination.items, groups=groups)


@contacts_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    form = ContactForm()
    form.group_id.choices = _group_choices()
    if form.validate_on_submit():
        try:
            phone = normalize_phone(form.phone.data)
        except InvalidPhoneNumberError as exc:
            flash(str(exc), "error")
            return render_template("contacts/form.html", form=form, title="Nouveau contact")

        if Contact.query.filter_by(business_id=current_user.business_id, phone_e164=phone).first():
            flash("Un contact avec ce numéro existe déjà.", "error")
            return render_template("contacts/form.html", form=form, title="Nouveau contact")

        contact = Contact(
            business_id=current_user.business_id,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone_e164=phone,
            email=form.email.data,
        )
        if form.group_id.data:
            group = ContactGroup.query.filter_by(
                id=form.group_id.data, business_id=current_user.business_id
            ).first()
            if group:
                contact.groups.append(group)
        db.session.add(contact)
        db.session.commit()
        flash("Contact ajouté avec succès.", "success")
        return redirect(url_for("contacts.index"))

    return render_template("contacts/form.html", form=form, title="Nouveau contact")


@contacts_bp.route("/<int:contact_id>/delete", methods=["POST"])
@login_required
def delete(contact_id):
    contact = Contact.query.filter_by(id=contact_id, business_id=current_user.business_id).first_or_404()
    db.session.delete(contact)
    db.session.commit()
    flash("Contact supprimé.", "info")
    return redirect(url_for("contacts.index"))


@contacts_bp.route("/groups")
@login_required
def groups():
    groups_list = ContactGroup.query.filter_by(business_id=current_user.business_id).order_by(
        ContactGroup.name
    ).all()
    return render_template("contacts/groups.html", groups=groups_list)


@contacts_bp.route("/groups/new", methods=["GET", "POST"])
@login_required
def new_group():
    form = GroupForm()
    if form.validate_on_submit():
        if ContactGroup.query.filter_by(
            business_id=current_user.business_id, name=form.name.data
        ).first():
            flash("Un groupe avec ce nom existe déjà.", "error")
        else:
            group = ContactGroup(
                business_id=current_user.business_id,
                name=form.name.data,
                description=form.description.data,
            )
            db.session.add(group)
            db.session.commit()
            flash("Groupe créé.", "success")
            return redirect(url_for("contacts.groups"))
    return render_template("contacts/group_form.html", form=form)


@contacts_bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
    group = ContactGroup.query.filter_by(
        id=group_id, business_id=current_user.business_id
    ).first_or_404()
    db.session.delete(group)
    db.session.commit()
    flash("Groupe supprimé.", "info")
    return redirect(url_for("contacts.groups"))


@contacts_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_contacts():
    form = ImportContactsForm()
    form.group_id.choices = _group_choices()

    if form.validate_on_submit():
        stream = io.StringIO(form.file.data.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)

        target_group = None
        if form.group_id.data:
            target_group = ContactGroup.query.filter_by(
                id=form.group_id.data, business_id=current_user.business_id
            ).first()

        created, skipped, errors = 0, 0, 0
        existing_phones = {
            c.phone_e164
            for c in Contact.query.filter_by(business_id=current_user.business_id).all()
        }

        for row in reader:
            raw_phone = row.get("phone") or row.get("téléphone") or row.get("telephone") or ""
            try:
                phone = normalize_phone(raw_phone)
            except InvalidPhoneNumberError:
                errors += 1
                continue

            if phone in existing_phones:
                skipped += 1
                continue

            contact = Contact(
                business_id=current_user.business_id,
                first_name=(row.get("first_name") or row.get("prenom") or "").strip() or None,
                last_name=(row.get("last_name") or row.get("nom") or "").strip() or None,
                phone_e164=phone,
                email=(row.get("email") or "").strip() or None,
            )
            if target_group:
                contact.groups.append(target_group)
            db.session.add(contact)
            existing_phones.add(phone)
            created += 1

        db.session.commit()
        flash(
            f"Import terminé : {created} contact(s) ajouté(s), {skipped} doublon(s) ignoré(s), "
            f"{errors} numéro(s) invalide(s).",
            "success" if created else "info",
        )
        return redirect(url_for("contacts.index"))

    return render_template("contacts/import.html", form=form)
