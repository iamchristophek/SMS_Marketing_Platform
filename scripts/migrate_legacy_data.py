"""Migre les données de l'ancien prototype (SQLite brut, sms_platform.py)
vers le nouveau schéma SQLAlchemy multi-tenant (app/models/).

Hypothèses validées avec l'utilisateur avant l'écriture de ce script :
  - 1 FCFA de l'ancien solde = 1 crédit dans le nouveau système.
  - Le consentement marketing (consent_given/consent_date) est préservé
    (nouvelles colonnes ajoutées à Contact : consent_given, consent_given_at).
  - En cas d'incohérence entre les lignes user_balances et la somme des
    transactions, la valeur retenue comme solde de départ est la DERNIÈRE
    ligne user_balances (la plus récente par last_updated), pas la somme
    des transactions.

Chaque utilisateur legacy devient une Business distincte (le prototype
était mono-tenant : un "user" possédait déjà directement toutes ses
ressources, donc Business == User d'origine, avec le User migré comme
propriétaire "owner" de cette Business).

Usage :
    python scripts/migrate_legacy_data.py --legacy-db ../SMS_Marketing_Platform/sms_marketing.db [--dry-run] [--apply]

Par défaut le script tourne en dry-run (aucune écriture). Passer --apply
pour écrire réellement dans la base configurée par DATABASE_URL / la config
Flask active (FLASK_ENV).
"""
import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models.billing import CreditTransaction
from app.models.contact import Contact
from app.models.user import Business, User
from app.services.phone import InvalidPhoneNumberError, normalize_phone

FREE_TRIAL_CREDITS_UNUSED = 0  # les entreprises migrées ne reçoivent pas de crédit d'essai en plus de leur solde repris


def parse_dt(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def load_legacy(legacy_db_path):
    conn = sqlite3.connect(legacy_db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def fetch(table):
        cur.execute(f"SELECT * FROM {table}")
        return [dict(row) for row in cur.fetchall()]

    data = {
        "users": fetch("users"),
        "clients": fetch("clients"),
        "contacts": fetch("contacts"),
        "user_balances": fetch("user_balances"),
        "transactions": fetch("transactions"),
        "message_templates": fetch("message_templates"),
    }
    conn.close()
    return data


def latest_balance_row(balance_rows, user_id):
    rows = [r for r in balance_rows if r["user_id"] == user_id]
    if not rows:
        return None
    return max(rows, key=lambda r: r["last_updated"] or "")


TRANSACTION_TYPE_MAP = {
    "BALANCE_ADDED": CreditTransaction.TYPE_PURCHASE,
    "CAMPAIGN_SENT": CreditTransaction.TYPE_CONSUMPTION,
    "REFUND": CreditTransaction.TYPE_REFUND,
}


def migrate_contact(business, raw, source, warnings, seen_phones):
    """Convertit une ligne `contacts` ou `clients` legacy en Contact.
    Retourne None (et logue un warning) si le numéro est invalide.
    """
    raw_phone = raw.get("phone") or ""
    try:
        phone_e164 = normalize_phone(raw_phone)
    except InvalidPhoneNumberError as exc:
        warnings.append(f"[{source} id={raw['id']}] numéro ignoré : {exc}")
        return None

    key = (business.name, phone_e164)
    name = (raw.get("name") or "").strip()
    parts = name.split(" ", 1)
    first_name = parts[0] if parts else None
    last_name = parts[1] if len(parts) > 1 else None

    if key in seen_phones:
        # Doublon (même numéro déjà migré pour cette entreprise, ex. le
        # contact a été ré-ajouté après un opt-out) : on fusionne — le
        # contact existant l'emporte, mais un opt-out sur l'une des lignes
        # rend le contact opted_out dans tous les cas (principe de
        # précaution réglementaire).
        existing = seen_phones[key]
        if raw.get("opt_out"):
            existing.opted_out = True
            existing.opted_out_at = existing.opted_out_at or parse_dt(raw.get("opt_out_date"))
        if raw.get("consent_given") and not existing.consent_given:
            existing.consent_given = True
            existing.consent_given_at = parse_dt(raw.get("consent_date"))
        warnings.append(
            f"[{source} id={raw['id']}] doublon fusionné avec le contact {phone_e164} déjà migré"
        )
        return None

    contact = Contact(
        business=business,
        first_name=first_name,
        last_name=last_name,
        phone_e164=phone_e164,
        email=raw.get("email"),
        opted_out=bool(raw.get("opt_out", 0)),
        opted_out_at=parse_dt(raw.get("opt_out_date")),
        consent_given=bool(raw.get("consent_given", 0)),
        consent_given_at=parse_dt(raw.get("consent_date")),
    )
    seen_phones[key] = contact
    return contact


def run_migration(legacy_data, dry_run, unmatched_templates_out):
    warnings = []
    created_businesses = 0
    created_contacts = 0
    skipped_contacts = 0

    for legacy_user in legacy_data["users"]:
        username = legacy_user["username"]
        email = legacy_user["email"]

        if User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            warnings.append(f"Utilisateur '{username}' déjà présent dans la cible, ignoré.")
            continue

        balance_row = latest_balance_row(legacy_data["user_balances"], legacy_user["id"])
        starting_credits = int(balance_row["balance"]) if balance_row else 0

        business = Business(
            name=f"Entreprise de {username}",
            credit_balance=starting_credits,
        )
        db.session.add(business)
        db.session.flush()  # obtenir business.id sans commit
        created_businesses += 1

        user = User(
            username=username,
            email=email,
            password_hash=legacy_user["password_hash"],  # même algo (werkzeug pbkdf2), copie directe
            role=User.ROLE_OWNER,
            business_id=business.id,
        )
        db.session.add(user)

        if starting_credits:
            db.session.add(
                CreditTransaction(
                    business=business,
                    type=CreditTransaction.TYPE_PURCHASE,
                    amount=starting_credits,
                    balance_after=starting_credits,
                    description="Solde repris lors de la migration depuis l'ancien système",
                )
            )

        seen_phones = {}
        for raw_contact in legacy_data["contacts"]:
            if raw_contact["user_id"] != legacy_user["id"]:
                continue
            contact = migrate_contact(business, raw_contact, "contacts", warnings, seen_phones)
            if contact:
                db.session.add(contact)
                created_contacts += 1
            else:
                skipped_contacts += 1

        for raw_client in legacy_data["clients"]:
            if raw_client["user_id"] != legacy_user["id"]:
                continue
            # Table `clients` legacy : jamais utilisée par l'app (code mort,
            # cf. app.py ligne 40), sans info de consentement -> migrée par
            # précaution mais consent_given=False (aucune preuve disponible).
            contact = migrate_contact(business, raw_client, "clients", warnings, seen_phones)
            if contact:
                db.session.add(contact)
                created_contacts += 1
            else:
                skipped_contacts += 1

        user_templates = [
            t for t in legacy_data["message_templates"] if t["user_id"] == legacy_user["id"]
        ]
        if user_templates:
            unmatched_templates_out.extend(
                {**t, "legacy_username": username} for t in user_templates
            )

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()

    return {
        "created_businesses": created_businesses,
        "created_contacts": created_contacts,
        "skipped_contacts": skipped_contacts,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-db", required=True, help="Chemin vers l'ancien sms_marketing.db")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Écrit réellement les données (par défaut : dry-run, aucune écriture)",
    )
    parser.add_argument(
        "--env", default="development", help="Profil Flask à utiliser (development/production/testing)"
    )
    parser.add_argument(
        "--templates-out",
        default="legacy_message_templates.json",
        help="Fichier où sauvegarder les message_templates legacy (aucune table équivalente dans le nouveau schéma)",
    )
    args = parser.parse_args()

    legacy_path = Path(args.legacy_db)
    if not legacy_path.exists():
        print(f"Base legacy introuvable : {legacy_path}", file=sys.stderr)
        sys.exit(1)

    app = create_app(args.env)
    unmatched_templates = []

    with app.app_context():
        db.create_all()
        legacy_data = load_legacy(legacy_path)
        result = run_migration(legacy_data, dry_run=not args.apply, unmatched_templates_out=unmatched_templates)

    mode = "APPLIQUÉ" if args.apply else "DRY-RUN (rien écrit)"
    print(f"\n=== Migration {mode} ===")
    print(f"Entreprises créées : {result['created_businesses']}")
    print(f"Contacts migrés    : {result['created_contacts']}")
    print(f"Contacts ignorés   : {result['skipped_contacts']}")
    if result["warnings"]:
        print("\nAvertissements :")
        for w in result["warnings"]:
            print(f"  - {w}")

    if unmatched_templates:
        Path(args.templates_out).write_text(
            json.dumps(unmatched_templates, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(
            f"\n{len(unmatched_templates)} template(s) de message sans équivalent dans le nouveau"
            f" schéma sauvegardé(s) dans {args.templates_out} (à réimporter manuellement si la"
            f" fonctionnalité est réintroduite)."
        )


if __name__ == "__main__":
    main()
