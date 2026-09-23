from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import BooleanField, SelectField, SelectMultipleField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional
from wtforms.widgets import CheckboxInput, ListWidget


class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class ContactForm(FlaskForm):
    first_name = StringField("Prénom", validators=[Optional(), Length(max=80)])
    last_name = StringField("Nom", validators=[Optional(), Length(max=80)])
    phone = StringField("Téléphone", validators=[DataRequired(), Length(max=30)])
    email = StringField("Email", validators=[Optional(), Email(message="Adresse email invalide"), Length(max=120)])
    groups = MultiCheckboxField("Groupes", coerce=int, validators=[Optional()])
    consent_given = BooleanField("Ce contact a accepté de recevoir mes SMS marketing")
    resubscribe = BooleanField(
        "Réabonner ce contact (uniquement s'il vous l'a demandé après avoir envoyé STOP)"
    )
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
    consent_all = BooleanField(
        "Tous les contacts de ce fichier ont accepté de recevoir mes SMS marketing"
    )
    submit = SubmitField("Importer")


class BulkActionForm(FlaskForm):
    """Actions groupées sur les contacts cochés dans la liste. Les
    identifiants cochés arrivent dans le champ multiple `contact_ids`, lu
    directement depuis request.form (leur liste dépend de la page)."""

    action = SelectField(
        "Action",
        choices=[
            ("add_to_group", "Ajouter au groupe"),
            ("remove_from_group", "Retirer du groupe"),
            ("consent", "Marquer « consentement donné »"),
            ("delete", "Supprimer"),
        ],
    )
    group_id = SelectField("Groupe", coerce=int, validators=[Optional()])
    submit = SubmitField("Appliquer")
