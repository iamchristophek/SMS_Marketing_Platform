from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length

from app.models.template import MessageTemplate


class MessageTemplateForm(FlaskForm):
    name = StringField("Nom du modèle", validators=[DataRequired(), Length(min=2, max=80)])
    category = SelectField("Type", choices=list(MessageTemplate.CATEGORY_LABELS.items()))
    body = TextAreaField(
        "Message", validators=[DataRequired(), Length(max=640, message="640 caractères maximum")]
    )
    submit = SubmitField("Enregistrer")
