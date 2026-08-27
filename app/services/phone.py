"""Validation et normalisation des numéros de téléphone, avec un support
particulier du plan de numérotation ivoirien (+225).

Depuis 2021, la Côte d'Ivoire utilise des numéros à 10 chiffres après
l'indicatif (ex: 07 XX XX XX XX, 05 XX XX XX XX, 01 XX XX XX XX...).
On normalise systématiquement au format E.164 : +225XXXXXXXXXX.
"""
import re

CI_COUNTRY_CODE = "225"
CI_LOCAL_DIGITS = 10  # nombre de chiffres après l'indicatif pays

# Préfixes opérateurs valides sur le nouveau plan à 10 chiffres (2021+).
CI_VALID_PREFIXES = {"01", "05", "07", "21", "25", "27"}


class InvalidPhoneNumberError(ValueError):
    pass


def normalize_phone(raw_number: str, default_country_code: str = CI_COUNTRY_CODE) -> str:
    """Convertit un numéro saisi par l'utilisateur en format E.164.

    Accepte des formats variés : "07 12 34 56 78", "0712345678",
    "+2250712345678", "2250712345678", "00225 07 12 34 56 78".
    Lève InvalidPhoneNumberError si le numéro est manifestement invalide.
    """
    if not raw_number or not raw_number.strip():
        raise InvalidPhoneNumberError("Numéro de téléphone vide")

    digits = re.sub(r"[^\d+]", "", raw_number.strip())
    digits = digits.replace("00", "+", 1) if digits.startswith("00") else digits

    if digits.startswith("+"):
        digits = digits[1:]

    # Numéro local ivoirien (10 chiffres, commence par un préfixe valide)
    if len(digits) == CI_LOCAL_DIGITS and digits[:2] in CI_VALID_PREFIXES:
        return f"+{default_country_code}{digits}"

    # Déjà préfixé par l'indicatif pays
    if digits.startswith(default_country_code) and len(digits) == len(default_country_code) + CI_LOCAL_DIGITS:
        local_part = digits[len(default_country_code):]
        if local_part[:2] in CI_VALID_PREFIXES:
            return f"+{digits}"

    # Numéro international générique (autre pays) : on exige un E.164
    # plausible (8 à 15 chiffres après le +).
    if digits.startswith("+"):
        digits = digits[1:]
    if 8 <= len(digits) <= 15 and digits.isdigit():
        return f"+{digits}"

    raise InvalidPhoneNumberError(f"Numéro de téléphone invalide : {raw_number!r}")


def is_ivorian_number(e164_number: str) -> bool:
    return e164_number.startswith(f"+{CI_COUNTRY_CODE}")


def format_for_display(e164_number: str) -> str:
    """Formate +2250712345678 en 07 12 34 56 78 pour l'affichage local."""
    if is_ivorian_number(e164_number):
        local = e164_number[len(CI_COUNTRY_CODE) + 1:]
        return " ".join(local[i : i + 2] for i in range(0, len(local), 2))
    return e164_number
