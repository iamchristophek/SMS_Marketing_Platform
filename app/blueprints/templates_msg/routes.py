from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.blueprints.templates_msg import templates_bp
from app.blueprints.templates_msg.forms import MessageTemplateForm
from app.extensions import db
from app.models.template import MessageTemplate


def _get_template(template_id):
    return MessageTemplate.query.filter_by(
        id=template_id, business_id=current_user.business_id
    ).first_or_404()


@templates_bp.route("/")
@login_required
def index():
    templates = (
        MessageTemplate.query.filter_by(business_id=current_user.business_id)
        .order_by(MessageTemplate.category, MessageTemplate.name)
        .all()
    )
    return render_template("message_templates/index.html", templates=templates)


@templates_bp.route("/new", methods=["GET", "POST"])
@login_required
def new():
    return _form(None)


@templates_bp.route("/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
def edit(template_id):
    return _form(_get_template(template_id))


def _form(template):
    form = MessageTemplateForm(obj=template)
    if form.validate_on_submit():
        duplicate = MessageTemplate.query.filter(
            MessageTemplate.business_id == current_user.business_id,
            MessageTemplate.name == form.name.data,
            MessageTemplate.id != (template.id if template else 0),
        ).first()
        if duplicate:
            form.name.errors.append("Un modèle avec ce nom existe déjà.")
        else:
            if template is None:
                template = MessageTemplate(business_id=current_user.business_id)
                db.session.add(template)
            form.populate_obj(template)
            db.session.commit()
            flash("Modèle enregistré.", "success")
            return redirect(url_for("templates_msg.index"))
    title = "Modifier le modèle" if template else "Nouveau modèle"
    return render_template("message_templates/form.html", form=form, title=title, template=template)


@templates_bp.route("/<int:template_id>/delete", methods=["POST"])
@login_required
def delete(template_id):
    db.session.delete(_get_template(template_id))
    db.session.commit()
    flash("Modèle supprimé.", "info")
    return redirect(url_for("templates_msg.index"))
