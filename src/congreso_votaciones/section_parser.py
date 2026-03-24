from __future__ import annotations

from congreso_votaciones.extraction_models import SectionType
from congreso_votaciones.parse_index import ascii_fold


def classify_page_text(text: str) -> SectionType:
    folded = ascii_fold(text)
    if "votacion" in folded or "resultado de votacion" in folded:
        return "vote"
    if "asistencia" in folded or "resultados de la asistencia" in folded:
        return "attendance"
    if "grupo parlamentario" in folded or "presente ausente licencia" in folded:
        return "summary"
    return "other"
