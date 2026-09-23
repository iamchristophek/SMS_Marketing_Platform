from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.account import account_bp
from app.blueprints.account.forms import ApiKeyForm, BusinessForm, ProfileForm
from app.extensions import db
from app.models.api_key import ApiKey
from app.models.user import User
from app.services.phone import InvalidPhoneNumberError, format_for_display, normalize_phone


def _render(business_form=None, profile_form=None, api_key_form=None, new_key=None):
    business = current_user.business
    if business_form is None:
        # formdata=None : pendant un POST vers un autre formulaire, ne pas
        # recopier les champs soumis dans celui-ci.
        business_form = BusinessForm(formdata=None, obj=business)
        if business.phone:
            business_form.phone.data = format_for_display(business.phone)
    keys = ApiKey.query.filter_by(business_id=business.id).order_by(ApiKey.created_at.desc()).all()
    return render_template(
        "account/index.html",
        business=business,
        business_form=business_form,
        profile_form=profile_form or ProfileForm(formdata=None, obj=current_user),
        api_key_form=api_key_form or ApiKeyForm(formdata=None),
        api_keys=keys,
        new_key=new_key,
    )


@account_bp.route("/")
@login_required
def index():
    return _render()


@account_bp.route("/entreprise", methods=["POST"])
@login_required
def update_business():
    form = BusinessForm()
    if form.validate_on_submit():
        phone = None
        if form.phone.data:
            try:
                phone = normalize_phone(form.phone.data)
            except InvalidPhoneNumberError as exc:
                form.phone.errors.append(str(exc))
                return _render(business_form=form)
        business = current_user.business
        business.name = form.name.data
        business.sector = form.sector.data or None
        business.city = form.city.data or None
        business.phone = phone
        db.session.commit()
        flash("Informations de l'entreprise enregistrées.", "success")
        return redirect(url_for("account.index"))
    return _render(business_form=form)


@account_bp.route("/profil", methods=["POST"])
@login_required
def update_profile():
    form = ProfileForm()
    if form.validate_on_submit():
        taken = User.query.filter(User.email == form.email.data, User.id != current_user.id).first()
        if taken:
            form.email.errors.append("Cette adresse email est déjà utilisée.")
            return _render(profile_form=form)
        current_user.email = form.email.data
        db.session.commit()
        flash("Profil enregistré.", "success")
        return redirect(url_for("account.index"))
    return _render(profile_form=form)


@account_bp.route("/cles-api", methods=["POST"])
@login_required
def create_api_key():
    form = ApiKeyForm()
    if not form.validate_on_submit():
        return _render(api_key_form=form)
    api_key, raw_key = ApiKey.generate(current_user.business_id, form.key_name.data.strip())
    db.session.add(api_key)
    db.session.commit()
    # La clé en clair est affichée une seule fois, dans cette réponse
    # (jamais dans un message flash, qui transiterait par le cookie).
    return _render(new_key=raw_key)


@account_bp.route("/cles-api/<int:key_id>/revoquer", methods=["POST"])
@login_required
def revoke_api_key(key_id):
    api_key = ApiKey.query.filter_by(id=key_id, business_id=current_user.business_id).first_or_404()
    api_key.revoked = True
    db.session.commit()
    flash(f"Clé « {api_key.name} » révoquée : elle ne fonctionne plus.", "info")
    return redirect(url_for("account.index"))
