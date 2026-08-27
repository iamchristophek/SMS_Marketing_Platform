from flask_wtf import FlaskForm
from wtforms import DateTimeLocalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class CampaignForm(FlaskForm):
    name = StringField("Nom de la campagne", validators=[DataRequired(), Length(min=3, max=120)])
    message = TextAreaField(
        "Message", validators=[DataRequired(), Length(max=640, message="640 caractères maximum (4 SMS)")]
    )
    group_id = SelectField("Cible", coerce=int, validators=[Optional()])
    scheduled_at = DateTimeLocalField(
        "Envoyer plus tard (laisser vide pour un envoi immédiat)",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
    )
    submit = SubmitField("Enregistrer")
