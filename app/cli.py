"""Commandes Flask CLI pour l'administration en ligne de commande :

    flask create-admin --username admin --email admin@ma-pme.ci --business "Ma PME"
    flask seed-demo
"""
import click

from app.extensions import db


def register_cli_commands(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--business", prompt="Nom de l'entreprise")
    def create_admin(username, email, password, business):
        """Crée un compte propriétaire (owner) et son entreprise."""
        from app.models.user import Business, User

        if User.query.filter((User.username == username) | (User.email == email)).first():
            click.echo("Un utilisateur avec ce nom ou cet email existe déjà.")
            return

        biz = Business(name=business, credit_balance=app.config["FREE_TRIAL_CREDITS"])
        db.session.add(biz)
        db.session.flush()

        user = User(username=username, email=email, role=User.ROLE_OWNER, business_id=biz.id)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Compte administrateur '{username}' créé pour l'entreprise '{business}'.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Insère des données de démonstration : packs de crédits + un
        compte de test avec quelques contacts."""
        from app.models.billing import CreditPackage
        from app.models.user import Business, User

        if CreditPackage.query.first() is None:
            packages = [
                CreditPackage(name="Découverte", credits=100, price_xof=2000, sort_order=1),
                CreditPackage(name="Starter", credits=500, price_xof=9000, sort_order=2),
                CreditPackage(name="Business", credits=2000, price_xof=32000, sort_order=3),
                CreditPackage(name="Croissance", credits=10000, price_xof=145000, sort_order=4),
            ]
            db.session.add_all(packages)
            click.echo("Packs de crédits créés.")

        if not User.query.filter_by(username="demo").first():
            biz = Business(name="PME Démo", sector="Commerce", city="Abidjan", credit_balance=100)
            db.session.add(biz)
            db.session.flush()
            user = User(username="demo", email="demo@pmesms.ci", role=User.ROLE_OWNER, business_id=biz.id)
            user.set_password("Demo1234!")
            db.session.add(user)
            click.echo("Utilisateur de démonstration créé : demo / Demo1234!")

        db.session.commit()
        click.echo("Données de démonstration insérées.")
