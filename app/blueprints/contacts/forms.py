from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class ContactForm(FlaskForm):
    first_name = StringField("Prénom", validators=[Optional(), Length(max=80)])
    last_name = StringField("Nom", validators=[Optional(), Length(max=80)])
    phone = StringField("Téléphone", validators=[DataRequired(), Length(max=30)])
    email = StringField("Email", validators=[Optional(), Length(max=120)])
    group_id = SelectField("Groupe", coerce=int, validators=[Optional()])
    submit = SubmitField("Enregistrer")


class GroupForm(FlaskForm):
    name = StringField("Nom du groupe", validators=[DataRequired(), Length(min=2, max=80)])
    description = StringField("Description", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Enregistrer")


class ImportContactsForm(FlaskForm):
    file = FileField(
        "Fichier CSV",
        validators=[FileRequired(), FileAllowed(["csv"], "Fichier CSV uniquement")],
    )
    group_id = SelectField("Ajouter au groupe (optionnel)", coerce=int, validators=[Optional()])
    submit = SubmitField("Importer")
