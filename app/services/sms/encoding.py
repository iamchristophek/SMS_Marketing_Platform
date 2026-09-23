"""Calcul du nombre de segments facturés pour un SMS.

Un SMS est encodé :
- en **GSM-7** (alphabet GSM 03.38) si tous ses caractères en font partie :
  160 caractères pour un SMS seul, 153 par segment au-delà. Les caractères
  de la table d'extension (€ [ ] { } ^ ~ | \\ et saut de page) comptent
  pour deux ;
- sinon en **UCS-2** : 70 caractères pour un SMS seul, 67 par segment
  au-delà. Il suffit d'un seul caractère hors alphabet GSM — en français :
  ç, â, ê, î, ô, û, ë, ï, œ, l'apostrophe typographique ’, les guillemets
  « », un emoji — pour que TOUT le message passe en UCS-2.

C'est ce calcul que les opérateurs facturent : sous-estimer les segments
revient à vendre des SMS à perte.
"""
import math
from dataclasses import dataclass

GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENSION = set("^{}\\[~]|€\f")

GSM7_SINGLE, GSM7_MULTI = 160, 153
UCS2_SINGLE, UCS2_MULTI = 70, 67

ENCODING_GSM7 = "GSM-7"
ENCODING_UCS2 = "UCS-2"


@dataclass(frozen=True)
class SmsInfo:
    encoding: str
    length: int  # en unités de l'encodage (septets GSM ou unités UTF-16)
    segments: int
    non_gsm_chars: tuple  # caractères qui forcent l'UCS-2, sans doublon

    @property
    def per_segment(self):
        if self.encoding == ENCODING_GSM7:
            return GSM7_SINGLE if self.segments <= 1 else GSM7_MULTI
        return UCS2_SINGLE if self.segments <= 1 else UCS2_MULTI


def analyze_message(text: str) -> SmsInfo:
    text = text or ""
    non_gsm = []
    for char in text:
        if char not in GSM7_BASIC and char not in GSM7_EXTENSION and char not in non_gsm:
            non_gsm.append(char)

    if not non_gsm:
        length = sum(2 if char in GSM7_EXTENSION else 1 for char in text)
        single, multi, encoding = GSM7_SINGLE, GSM7_MULTI, ENCODING_GSM7
    else:
        # UCS-2 compte en unités de 16 bits : un emoji (hors BMP) en vaut deux.
        length = len(text.encode("utf-16-le")) // 2
        single, multi, encoding = UCS2_SINGLE, UCS2_MULTI, ENCODING_UCS2

    if length == 0:
        segments = 0
    elif length <= single:
        segments = 1
    else:
        segments = math.ceil(length / multi)
    return SmsInfo(encoding=encoding, length=length, segments=segments, non_gsm_chars=tuple(non_gsm))


def compute_sms_segments(text: str) -> int:
    return analyze_message(text).segments
