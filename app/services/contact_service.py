"""Logique métier des contacts : recherche/filtres, import et export CSV."""
import csv
import io

from sqlalchemy import or_

from app.extensions import db
from app.models.contact import Contact, ContactGroup
from app.services.phone import (
    InvalidPhoneNumberError,
    format_for_display,
    normalize_phone,
    operator_prefixes,
    OPERATOR_OTHER,
    CI_COUNTRY_CODE,
)

STATUS_ACTIVE = "actifs"
STATUS_OPTED_OUT = "desabonnes"
STATUS_CONSENT = "consentants"
STATUS_NO_CONSENT = "sans-consentement"

STATUS_FILTERS = {
    STATUS_ACTIVE: "Actifs",
    STATUS_OPTED_OUT: "Désabonnés (STOP)",
    STATUS_CONSENT: "Avec consentement",
    STATUS_NO_CONSENT: "Sans consentement",
}

TRUTHY = {"1", "oui", "o", "yes", "y", "true", "vrai", "x"}


def filtered_contacts(business_id, q=None, group_id=None, status=None, operator=None):
    """Requête des contacts d'une entreprise selon les filtres de la liste."""
    query = Contact.query.filter(Contact.business_id == business_id)

    if q:
        term = f"%{q.strip()}%"
        digits = "".join(ch for ch in q if ch.isdigit())
        conditions = [Contact.first_name.ilike(term), Contact.last_name.ilike(term), Contact.email.ilike(term)]
        if digits:
            # « 07 12 34 » doit trouver +2250712345678 : on cherche les
            # chiffres, sans le 0 initial d'un format local éventuel.
            conditions.append(Contact.phone_e164.like(f"%{digits.lstrip('0') or digits}%"))
        query = query.filter(or_(*conditions))

    if group_id:
        query = query.filter(Contact.groups.any(ContactGroup.id == group_id))

    if status == STATUS_ACTIVE:
        query = query.filter(Contact.opted_out.is_(False))
    elif status == STATUS_OPTED_OUT:
        query = query.filter(Contact.opted_out.is_(True))
    elif status == STATUS_CONSENT:
        query = query.filter(Contact.consent_given.is_(True))
    elif status == STATUS_NO_CONSENT:
        query = query.filter(Contact.consent_given.is_(False))

    if operator == OPERATOR_OTHER:
        query = query.filter(~Contact.phone_e164.like(f"+{CI_COUNTRY_CODE}%"))
    elif operator:
        prefixes = operator_prefixes(operator)
        if prefixes:
            query = query.filter(or_(*[Contact.phone_e164.like(f"{p}%") for p in prefixes]))

    return query


def business_groups(business_id):
    return ContactGroup.query.filter_by(business_id=business_id).order_by(ContactGroup.name).all()


def phone_in_use(business_id, phone_e164, exclude_contact_id=None):
    query = Contact.query.filter_by(business_id=business_id, phone_e164=phone_e164)
    if exclude_contact_id:
        query = query.filter(Contact.id != exclude_contact_id)
    return db.session.query(query.exists()).scalar()


def import_csv(business_id, raw_bytes, target_group=None, consent_all=False):
    """Importe un CSV. Colonnes reconnues (insensibles à la casse) :
    phone/téléphone/telephone/numero (obligatoire), first_name/prenom,
    last_name/nom, email, consent/consentement (oui/1/x...).
    Le séparateur (virgule ou point-virgule, celui d'Excel en français)
    est détecté automatiquement. Retourne (créés, doublons, invalides)."""
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text.splitlines()[0] if text else "", delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text, newline=None), dialect=dialect)

    def column(row, *names):
        for name in names:
            for key, value in row.items():
                if key and key.strip().lower() == name:
                    return (value or "").strip()
        return ""

    existing = {
        phone for (phone,) in db.session.query(Contact.phone_e164).filter_by(business_id=business_id)
    }
    created = duplicates = invalid = 0
    for row in reader:
        try:
            phone = normalize_phone(column(row, "phone", "téléphone", "telephone", "numero", "numéro", "tel"))
        except InvalidPhoneNumberError:
            invalid += 1
            continue
        if phone in existing:
            duplicates += 1
            continue

        contact = Contact(
            business_id=business_id,
            # Tronqué à la taille des colonnes (PostgreSQL refuse les
            # valeurs trop longues, contrairement à SQLite).
            first_name=column(row, "first_name", "prenom", "prénom")[:80] or None,
            last_name=column(row, "last_name", "nom")[:80] or None,
            phone_e164=phone,
            email=column(row, "email", "e-mail", "mail")[:120] or None,
        )
        contact.set_consent(consent_all or column(row, "consent", "consentement").lower() in TRUTHY)
        if target_group:
            contact.groups.append(target_group)
        db.session.add(contact)
        existing.add(phone)
        created += 1
    return created, duplicates, invalid


def export_csv(contacts):
    """CSV séparé par des points-virgules (ouverture directe dans Excel FR)."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        ["prenom", "nom", "telephone", "email", "operateur", "groupes", "consentement",
         "date_consentement", "desabonne", "cree_le"]
    )
    for c in contacts:
        writer.writerow([
            c.first_name or "",
            c.last_name or "",
            format_for_display(c.phone_e164),
            c.email or "",
            c.operator_label,
            ", ".join(g.name for g in c.groups),
            "oui" if c.consent_given else "non",
            c.consent_given_at.strftime("%d/%m/%Y") if c.consent_given_at else "",
            "oui" if c.opted_out else "non",
            c.created_at.strftime("%d/%m/%Y"),
        ])
    # BOM UTF-8 : Excel affiche correctement les accents.
    return "﻿" + output.getvalue()
