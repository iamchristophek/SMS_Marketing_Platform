"""Commandes Flask CLI d'administration (en attendant un back-office web) :

    flask create-admin --username admin --email admin@ma-pme.ci --business "Ma PME"
    flask seed-packages                  # packs de crédits par défaut (production)
    flask seed-demo                      # packs + compte de démonstration (jamais en production)
    flask businesses list
    flask payments list [--all]
    flask payments approve <id>          # après réception du paiement Mobile Money
    flask payments reject <id>
    flask credits add <nom_utilisateur> <montant> --reason "Geste commercial"
    flask reset-password <nom_utilisateur>
"""
import click

from app.extensions import db
from app.services.account_service import create_business_with_owner

DEFAULT_PACKAGES = [
    # (nom, crédits, prix en F CFA, ordre d'affichage)
    ("Découverte", 100, 2000, 1),
    ("Starter", 500, 9000, 2),
    ("Business", 2000, 32000, 3),
    ("Croissance", 10000, 145000, 4),
]


def _seed_packages():
    from app.models.billing import CreditPackage

    if CreditPackage.query.first() is not None:
        return 0
    db.session.add_all(
        CreditPackage(name=name, credits=credits, price_xof=price, sort_order=order)
        for name, credits, price, order in DEFAULT_PACKAGES
    )
    return len(DEFAULT_PACKAGES)


def _find_user(username):
    from app.models.user import User

    user = User.query.filter_by(username=username).first()
    if user is None:
        raise click.ClickException(f"Aucun utilisateur « {username} ».")
    return user


def register_cli_commands(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--business", prompt="Nom de l'entreprise")
    def create_admin(username, email, password, business):
        """Crée un compte propriétaire (owner) et son entreprise."""
        from app.models.user import User

        if User.query.filter((User.username == username) | (User.email == email)).first():
            raise click.ClickException("Un utilisateur avec ce nom ou cet email existe déjà.")
        create_business_with_owner(
            business, username, email, password, app.config["FREE_TRIAL_CREDITS"]
        )
        db.session.commit()
        click.echo(f"Compte '{username}' créé pour l'entreprise '{business}'.")

    @app.cli.command("seed-packages")
    def seed_packages():
        """Crée les packs de crédits par défaut s'il n'en existe aucun."""
        created = _seed_packages()
        db.session.commit()
        click.echo(f"{created} pack(s) créé(s)." if created else "Des packs existent déjà : rien à faire.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Données de démonstration : packs de crédits, un compte « demo »
        (mot de passe public Demo1234!) et quelques contacts. Refusé en
        production, où ce compte serait une porte d'entrée connue."""
        from app.models.contact import Contact, ContactGroup
        from app.models.user import User

        if app.config.get("ENV") == "production":
            raise click.ClickException(
                "seed-demo est interdit en production (compte au mot de passe public). "
                "Utilisez « flask seed-packages » pour créer les packs de crédits."
            )

        if _seed_packages():
            click.echo("Packs de crédits créés.")

        if not User.query.filter_by(username="demo").first():
            business, _ = create_business_with_owner(
                "PME Démo", "demo", "demo@baoryx.ci", "Demo1234!", 100,
                sector="Commerce", city="Abidjan",
            )
            group = ContactGroup(business_id=business.id, name="Clients fidèles")
            db.session.add(group)
            demo_contacts = [("Koffi", "+2250701020304"), ("Aya", "+2250501020304"), ("Yao", "+2250101020304")]
            for first_name, phone in demo_contacts:
                contact = Contact(
                    business_id=business.id, first_name=first_name, phone_e164=phone, consent_given=True
                )
                contact.groups.append(group)
                db.session.add(contact)
            click.echo("Utilisateur de démonstration créé : demo / Demo1234! (3 contacts)")

        db.session.commit()
        click.echo("Données de démonstration insérées.")

    @app.cli.group("businesses")
    def businesses():
        """Entreprises clientes."""

    @businesses.command("list")
    def businesses_list():
        from app.models.user import Business

        for b in Business.query.order_by(Business.id).all():
            owners = ", ".join(u.username for u in b.users)
            click.echo(f"#{b.id:<4} {b.name:<30} {b.credit_balance:>8} crédits  ({owners})")

    @app.cli.group("payments")
    def payments():
        """Demandes d'achat de crédits."""

    @payments.command("list")
    @click.option("--all", "show_all", is_flag=True, help="Inclure les paiements traités.")
    def payments_list(show_all):
        from app.models.billing import Payment

        query = Payment.query.order_by(Payment.created_at.desc())
        if not show_all:
            query = query.filter_by(status=Payment.STATUS_PENDING)
        rows = query.all()
        if not rows:
            click.echo("Aucun paiement." if show_all else "Aucun paiement en attente.")
        for p in rows:
            click.echo(
                f"#{p.id:<4} {p.created_at:%d/%m/%Y %H:%M}  {p.status:<8} {p.provider:<9} "
                f"réf {p.provider_reference:<14} {p.amount_xof:>8} F  {p.credits:>6} crédits  "
                f"{p.business.name}"
            )

    def _get_payment(payment_id):
        from app.models.billing import Payment

        payment = db.session.get(Payment, payment_id)
        if payment is None:
            raise click.ClickException(f"Paiement #{payment_id} introuvable.")
        return payment

    @payments.command("approve")
    @click.argument("payment_id", type=int)
    def payments_approve(payment_id):
        """Valide un paiement reçu hors plateforme et crédite l'entreprise."""
        from app.services import billing_service

        payment = _get_payment(payment_id)
        if not billing_service.complete_payment(
            payment, f"Achat pack « {payment.package.name} » (réf. {payment.provider_reference})"
        ):
            raise click.ClickException(f"Paiement #{payment_id} déjà traité ({payment.status}).")
        db.session.commit()
        click.echo(
            f"Paiement #{payment_id} validé : {payment.credits} crédits ajoutés à {payment.business.name} "
            f"(solde {payment.business.credit_balance})."
        )

    @payments.command("reject")
    @click.argument("payment_id", type=int)
    def payments_reject(payment_id):
        """Refuse une demande d'achat (paiement jamais reçu)."""
        from app.services import billing_service

        payment = _get_payment(payment_id)
        if not billing_service.fail_payment(payment):
            raise click.ClickException(f"Paiement #{payment_id} déjà traité ({payment.status}).")
        db.session.commit()
        click.echo(f"Paiement #{payment_id} refusé.")

    @app.cli.group("credits")
    def credits():
        """Mouvements de crédits manuels."""

    @credits.command("add")
    @click.argument("username")
    @click.argument("amount", type=int)
    @click.option("--reason", required=True, help="Motif inscrit au journal comptable.")
    def credits_add(username, amount, reason):
        """Ajoute (ou retire, avec un montant négatif) des crédits à
        l'entreprise d'un utilisateur, avec un motif journalisé."""
        from app.models.billing import CreditTransaction
        from app.services import billing_service
        from app.services.billing_service import InsufficientCreditsError

        business = _find_user(username).business
        type_ = CreditTransaction.TYPE_BONUS if amount > 0 else CreditTransaction.TYPE_REFUND
        try:
            billing_service.adjust_credits(business, amount, type_, reason)
        except InsufficientCreditsError as exc:
            raise click.ClickException(str(exc)) from exc
        db.session.commit()
        click.echo(f"{business.name} : {amount:+} crédits, nouveau solde {business.credit_balance}.")

    @app.cli.command("reset-password")
    @click.argument("username")
    @click.option("--password", prompt="Nouveau mot de passe", hide_input=True, confirmation_prompt=True)
    def reset_password(username, password):
        """Définit un nouveau mot de passe pour un utilisateur (mot de passe
        oublié, en attendant la récupération par email)."""
        if len(password) < 8:
            raise click.ClickException("Le mot de passe doit contenir au moins 8 caractères.")
        user = _find_user(username)
        user.set_password(password)
        db.session.commit()
        click.echo(f"Mot de passe de « {username} » réinitialisé.")
