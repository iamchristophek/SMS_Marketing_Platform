from flask_wtf import FlaskForm
from wtforms import BooleanField, DateTimeLocalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class CampaignForm(FlaskForm):
    name = StringField("Nom de la campagne", validators=[DataRequired(), Length(min=3, max=120)])
    template_id = SelectField("Partir d'un modèle", coerce=int, validators=[Optional()])
    message = TextAreaField(
        "Message", validators=[DataRequired(), Length(max=640, message="640 caractères maximum")]
    )
    group_id = SelectField("Destinataires", coerce=int, validators=[Optional()])
    consent_only = BooleanField(
        "Uniquement les contacts ayant donné leur consentement (recommandé pour les promotions)"
    )
    scheduled_at = DateTimeLocalField(
        "Date d'envoi (heure d'Abidjan) — laisser vide pour envoyer dès la confirmation",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )
    submit = SubmitField("Continuer vers l'aperçu")


class ConfirmCampaignForm(FlaskForm):
    submit = SubmitField("Confirmer")
