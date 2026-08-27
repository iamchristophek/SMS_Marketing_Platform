from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp


class LoginForm(FlaskForm):
    username = StringField("Nom d'utilisateur", validators=[DataRequired()])
    password = PasswordField("Mot de passe", validators=[DataRequired()])
    submit = SubmitField("Se connecter")


class RegistrationForm(FlaskForm):
    business_name = StringField(
        "Nom de l'entreprise", validators=[DataRequired(), Length(min=2, max=120)]
    )
    username = StringField(
        "Nom d'utilisateur",
        validators=[
            DataRequired(),
            Length(min=4, max=30),
            Regexp(r"^[A-Za-z0-9_.-]+$", message="Lettres, chiffres, . _ - uniquement"),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField(
        "Mot de passe",
        validators=[
            DataRequired(),
            Length(min=8, message="8 caractères minimum"),
        ],
    )
    confirm_password = PasswordField(
        "Confirmer le mot de passe",
        validators=[DataRequired(), EqualTo("password", message="Les mots de passe ne correspondent pas")],
    )
    submit = SubmitField("Créer mon compte")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Mot de passe actuel", validators=[DataRequired()])
    new_password = PasswordField("Nouveau mot de passe", validators=[DataRequired(), Length(min=8)])
    confirm_new_password = PasswordField(
        "Confirmer le nouveau mot de passe",
        validators=[DataRequired(), EqualTo("new_password", message="Les mots de passe ne correspondent pas")],
    )
    submit = SubmitField("Changer le mot de passe")
