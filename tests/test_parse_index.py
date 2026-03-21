from __future__ import annotations

from congreso_votaciones.parse_index import (
    build_record_id,
    classify_document_type,
    classify_session_type,
    parse_pleno_index,
)


def test_parse_pleno_index_full_fixture(pleno_index_expanded_html: str) -> None:
    records = parse_pleno_index(
        pleno_index_expanded_html,
        source_page_url="https://www.congreso.gob.pe/pleno",
        iframe_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion",
        expand_view_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion?OpenForm&ExpandView&Seq=1",
    )

    assert len(records) == 933
    assert records[0].session_date_iso == "2026-03-19"
    assert records[0].is_provisional is True
    assert records[0].periodo_parlamentario.endswith("2021 - 2026")
    assert "Segunda Legislatura Ordinaria" in records[0].legislatura


def test_parse_pleno_index_keeps_distinct_documents_same_date(
    pleno_index_expanded_html: str,
) -> None:
    records = parse_pleno_index(
        pleno_index_expanded_html,
        source_page_url="https://www.congreso.gob.pe/pleno",
        iframe_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion",
        expand_view_url="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion?OpenForm&ExpandView&Seq=1",
    )

    same_day = [record for record in records if record.session_date_iso == "2025-10-09"]
    assert len(same_day) == 2
    assert {record.record_id for record in same_day} == {
        build_record_id(record.pdf_relative_path) for record in same_day
    }


def test_classify_helpers() -> None:
    assert (
        classify_document_type("Asistencias y votaciones de la sesión") == "asistencia_y_votaciones"
    )
    assert classify_document_type("Asistencia de la sesión") == "asistencia"
    assert classify_session_type("Asistencia de la sesión solemne") == "solemne"
    assert classify_session_type("Asistencia de la sesión extraordinaria") == "extraordinaria"
    assert classify_session_type("Asistencia de la sesión nocturna") == "vespertina"
