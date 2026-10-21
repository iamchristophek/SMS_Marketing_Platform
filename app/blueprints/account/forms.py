from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, SubmitField, TextAreaField
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


class FeedbackForm(FlaskForm):
    rating = SelectField(
        "Votre note",
        choices=[(5, "5 — Excellent"), (4, "4 — Bien"), (3, "3 — Moyen"), (2, "2 — Décevant"), (1, "1 — Mauvais")],
        coerce=int,
        default=5,
    )
    message = TextAreaField(
        "Votre avis ou suggestion", validators=[DataRequired(message="Écrivez quelques mots"), Length(max=2000)]
    )
    submit = SubmitField("Envoyer")
