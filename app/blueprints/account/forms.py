from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional


class BusinessForm(FlaskForm):
    name = StringField("Nom de l'entreprise", validators=[DataRequired(), Length(min=2, max=120)])
    sector = StringField("Secteur d'activité", validators=[Optional(), Length(max=80)])
    city = StringField("Ville", validators=[Optional(), Length(max=80)])
    phone = StringField("Téléphone de l'entreprise", validators=[Optional(), Length(max=20)])
    submit = SubmitField("Enregistrer")


class ProfileForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(message="Adresse email invalide"), Length(max=120)])
    submit = SubmitField("Enregistrer")


class ApiKeyForm(FlaskForm):
    key_name = StringField("Nom de la clé", validators=[DataRequired(), Length(max=80)],
                           description="Ex. : Site e-commerce, ERP")
    create = SubmitField("Créer une clé")
