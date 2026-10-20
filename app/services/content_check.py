"""Contrôle anti-fraude des messages avant envoi.

L'arnaque par SMS (faux Orange Money / Wave, demande de code, faux gain)
est très répandue en Côte d'Ivoire : un expéditeur partagé utilisé une
seule fois pour ça peut être bloqué par les opérateurs. On bloque les
motifs sans ambiguïté et on avertit pour les motifs douteux."""
import re
import unicodedata
from dataclasses import dataclass, field

LEVEL_BLOCK = "block"
LEVEL_WARN = "warn"


def _normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


# (motif, niveau, explication). Les motifs portent sur le texte sans accents.
RULES = [
    (r"\b(code|mot de passe|pin|otp|code secret)\b.{0,40}\b(envoie|envoyez|communique|transmet|donne|renvoie)",
     LEVEL_BLOCK, "Demande de code secret, PIN ou mot de passe"),
    (r"\b(envoie|envoyez|communique|transmet|donne|renvoie)\w*\b.{0,40}\b(code|mot de passe|pin|otp)\b",
     LEVEL_BLOCK, "Demande de code secret, PIN ou mot de passe"),
    (r"[#*]1[0-9]{2}[*#]",
     LEVEL_BLOCK, "Code USSD de transfert d'argent"),
    (r"\b(compte|sim|ligne|carte)\b.{0,30}\b(bloque|suspendu|desactive)",
     LEVEL_BLOCK, "Menace de blocage de compte (hameçonnage)"),
    (r"\b(orange money|mtn momo|momo|moov money|wave|flooz)\b",
     LEVEL_WARN, "Mention d'un service Mobile Money : vérifiez que vous ne vous faites pas passer pour l'opérateur"),
    (r"\b(gagne|gagnant|felicitations).{0,40}\b(\d[\d .]*\s?(f|fcfa|francs)|million|lot)",
     LEVEL_WARN, "Annonce de gain : les faux jeux concours sont signalés comme arnaque"),
    (r"(bit\.ly|tinyurl|t\.co/|cutt\.ly|is\.gd|shorturl)",
     LEVEL_WARN, "Lien raccourci : les destinataires ne savent pas où il mène"),
    (r"\b(banque|ministere|gouvernement|police|douane|impots|cnps)\b",
     LEVEL_WARN, "Mention d'une institution : ne vous présentez pas en son nom"),
]
_COMPILED = [(re.compile(p), level, reason) for p, level, reason in RULES]


@dataclass
class CheckResult:
    blocked: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.blocked


def check_message(text):
    result = CheckResult()
    normalized = _normalize(text)
    for pattern, level, reason in _COMPILED:
        if pattern.search(normalized):
            target = result.blocked if level == LEVEL_BLOCK else result.warnings
            if reason not in target:
                target.append(reason)
    return result
