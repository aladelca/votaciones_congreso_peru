from __future__ import annotations

from pathlib import Path

import pytest

from congreso_votaciones.models import PlenoPdfRecord
from congreso_votaciones.parse_index import build_record_id

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def pleno_public_page_html() -> str:
    return (FIXTURES_DIR / "pleno_public_page.html").read_text(encoding="utf-8")


@pytest.fixture
def pleno_index_expanded_html() -> str:
    return (FIXTURES_DIR / "pleno_index_expanded.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_record() -> PlenoPdfRecord:
    relative_path = "Apleno/ABC123/$FILE/Asistencia_sesion_1_1_2026.pdf"
    return PlenoPdfRecord(
        record_id=build_record_id(relative_path),
        source_page_url="https://www.congreso.gob.pe/pleno",
        iframe_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion",
        expand_view_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion?OpenForm&ExpandView&Seq=1",
        periodo_parlamentario="Congreso de la República - Periodo Parlamentario 2021 - 2026",
        periodo_anual="Período Anual de Sesiones 2025 - 2026",
        legislatura="Segunda Legislatura Ordinaria",
        session_date_raw="01/01/2026",
        session_date_iso="2026-01-01",
        source_title="Asistencia de la sesión del 1-1-2026",
        document_type="asistencia",
        session_type="ordinaria",
        is_provisional=False,
        is_official=False,
        pdf_relative_path=relative_path,
        pdf_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/Apleno/ABC123/$FILE/Asistencia_sesion_1_1_2026.pdf",
        filename_original="Asistencia_sesion_1_1_2026.pdf",
    )
