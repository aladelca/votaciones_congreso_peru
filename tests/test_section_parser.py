from __future__ import annotations

from congreso_votaciones.section_parser import classify_page_text


def test_classify_page_text_detects_attendance_pages() -> None:
    text = "CONGRESO DE LA REPUBLICA DEL PERU ASISTENCIA Resultados de la ASISTENCIA"
    assert classify_page_text(text) == "attendance"


def test_classify_page_text_detects_vote_pages() -> None:
    text = "CONGRESO DE LA REPUBLICA DEL PERU VOTACION Resultado de VOTACION"
    assert classify_page_text(text) == "vote"
