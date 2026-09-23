from datetime import datetime, timezone

from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import ChangePasswordForm, LoginForm, RegistrationForm
from app.extensions import db, limiter
from app.models.user import User
from app.services.account_service import create_business_with_owner


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash("Ce nom d'utilisateur est déjà utilisé.", "error")
        elif User.query.filter_by(email=form.email.data).first():
            flash("Cette adresse email est déjà utilisée.", "error")
        else:
            create_business_with_owner(
                form.business_name.data,
                form.username.data,
                form.email.data,
                form.password.data,
                current_app.config["FREE_TRIAL_CREDITS"],
            )
            db.session.commit()

            flash(
                f"Compte créé avec succès ! Vous bénéficiez de "
                f"{current_app.config['FREE_TRIAL_CREDITS']} crédits SMS gratuits.",
                "success",
            )
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.is_active_account and user.check_password(form.password.data):
            login_user(user)
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            flash("Connexion réussie !", "success")
            return redirect(url_for("dashboard.home"))
        flash("Nom d'utilisateur ou mot de passe incorrect.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Déconnexion réussie.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if current_user.check_password(form.current_password.data):
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Mot de passe modifié avec succès.", "success")
            return redirect(url_for("dashboard.home"))
        flash("Le mot de passe actuel est incorrect.", "error")
    return render_template("auth/change_password.html", form=form)
