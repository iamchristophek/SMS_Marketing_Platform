"""Assistant de rédaction : propose 3 SMS courts via l'API Claude."""
import json

from flask import current_app

from app.services.sms.encoding import analyze_message

SYSTEM_PROMPT = """Tu rédiges des SMS marketing pour des petits commerces et PME de Côte d'Ivoire.
Règles :
- Français simple et chaleureux, adapté au public ivoirien.
- 160 caractères maximum par SMS, mention de désabonnement comprise.
- Uniquement l'alphabet GSM : pas d'émojis, pas de guillemets typographiques ni de caractères spéciaux (ils doublent le coût).
- Chaque SMS se termine par « STOP au <numéro> » si un numéro de désabonnement est fourni, sinon par « Rep STOP pour arreter ».
- Tu peux utiliser {prenom} pour personnaliser.
- Aucune fausse promesse, aucun contenu trompeur, aucune usurpation d'identité (banque, opérateur, État).
Propose 3 variantes au ton différent."""

SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}


class AIWriterError(Exception):
    pass


def _client():
    import anthropic

    key = current_app.config.get("ANTHROPIC_API_KEY")
    if not key:
        raise AIWriterError("L'assistant IA n'est pas configuré.")
    return anthropic.Anthropic(api_key=key, timeout=30.0, max_retries=1)


def suggest_messages(brief: str, business_name: str):
    """Renvoie une liste de dicts {text, segments, encoding}."""
    import anthropic

    brief = (brief or "").strip()[:500]
    if len(brief) < 5:
        raise AIWriterError("Décrivez votre offre en quelques mots.")
    try:
        response = _client().messages.create(
            model=current_app.config["AI_MODEL"],
            max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Entreprise : {business_name}\nOffre : {brief}"}],
        )
    except anthropic.APIError as exc:
        current_app.logger.warning("Assistant IA indisponible : %s", exc)
        raise AIWriterError("L'assistant IA est momentanément indisponible.") from exc

    if response.stop_reason != "end_turn":
        raise AIWriterError("Aucune proposition possible pour cette demande.")
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    try:
        suggestions = json.loads(text).get("suggestions", [])
    except ValueError as exc:
        raise AIWriterError("Réponse inattendue de l'assistant.") from exc

    results = []
    for s in suggestions[:3]:
        s = str(s).strip()
        if s:
            info = analyze_message(s)
            results.append({"text": s, "segments": info.segments, "encoding": info.encoding})
    if not results:
        raise AIWriterError("Aucune proposition possible pour cette demande.")
    return results
