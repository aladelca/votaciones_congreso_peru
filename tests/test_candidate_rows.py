from __future__ import annotations

from congreso_votaciones.candidate_rows import extract_candidate_rows
from congreso_votaciones.extraction_models import ExtractedPage, ExtractedTextBlock


def test_extract_candidate_rows_from_attendance_blocks() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="ASISTENCIA",
            source_backend="google_document_ai",
            section_type="attendance",
            block_count=1,
        )
    ]
    blocks = [
        ExtractedTextBlock(
            block_id="b1",
            page_number=1,
            text="APP ACUÑA PERALTA, MARIA GRIMANESA PRE",
            source_backend="google_document_ai",
            x0=0.1,
            y0=0.1,
            x1=0.8,
            y1=0.2,
        )
    ]

    rows = extract_candidate_rows("abc123", pages, blocks)

    assert len(rows) == 1
    assert rows[0].kind == "attendance"
    assert rows[0].party_raw == "APP"
    assert rows[0].normalized_value == "presente"


def test_extract_candidate_rows_from_vote_blocks() -> None:
    pages = [
        ExtractedPage(
            page_number=2,
            text="VOTACION",
            source_backend="google_document_ai",
            section_type="vote",
            block_count=1,
        )
    ]
    blocks = [
        ExtractedTextBlock(
            block_id="b2",
            page_number=2,
            text="FP FLORES RUIZ, VICTOR SEFERINO SI",
            source_backend="google_document_ai",
            x0=0.1,
            y0=0.1,
            x1=0.8,
            y1=0.2,
        )
    ]

    rows = extract_candidate_rows("abc123", pages, blocks)

    assert len(rows) == 1
    assert rows[0].kind == "vote"
    assert rows[0].normalized_value == "si"


def test_extract_candidate_rows_from_positioned_attendance_band() -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="ASISTENCIA",
            source_backend="google_document_ai",
            section_type="attendance",
            block_count=8,
        )
    ]
    blocks = [
        ExtractedTextBlock(
            "b1",
            1,
            "APP",
            "google_document_ai",
            x0=0.03,
            y0=0.095,
            x1=0.05,
            y1=0.10,
        ),
        ExtractedTextBlock(
            "b2",
            1,
            "ACUÑA PERALTA, MARÍA GRIMANEZA",
            "google_document_ai",
            x0=0.08,
            y0=0.094,
            x1=0.26,
            y1=0.101,
        ),
        ExtractedTextBlock(
            "b3",
            1,
            "PRE",
            "google_document_ai",
            x0=0.29,
            y0=0.095,
            x1=0.31,
            y1=0.10,
        ),
        ExtractedTextBlock(
            "b4",
            1,
            "BS",
            "google_document_ai",
            x0=0.34,
            y0=0.095,
            x1=0.35,
            y1=0.10,
        ),
        ExtractedTextBlock(
            "b5",
            1,
            "FLORES RAMÍREZ, ALEX RANDU",
            "google_document_ai",
            x0=0.39,
            y0=0.094,
            x1=0.55,
            y1=0.101,
        ),
        ExtractedTextBlock(
            "b6",
            1,
            "PRE",
            "google_document_ai",
            x0=0.60,
            y0=0.095,
            x1=0.62,
            y1=0.10,
        ),
        ExtractedTextBlock(
            "b7",
            1,
            "AP-PIS PAREDES FONSECA, KAROL IVETT",
            "google_document_ai",
            x0=0.64,
            y0=0.095,
            x1=0.86,
            y1=0.101,
        ),
        ExtractedTextBlock(
            "b8",
            1,
            "LP",
            "google_document_ai",
            x0=0.91,
            y0=0.095,
            x1=0.92,
            y1=0.10,
        ),
    ]

    rows = extract_candidate_rows("abc123", pages, blocks)

    assert len(rows) == 3
    assert [row.party_raw for row in rows] == ["APP", "BS", "AP-PIS"]
    assert [row.normalized_value for row in rows] == [
        "presente",
        "presente",
        "licencia_personal",
    ]


def test_extract_candidate_rows_from_positioned_vote_band() -> None:
    pages = [
        ExtractedPage(
            page_number=3,
            text="VOTACION",
            source_backend="google_document_ai",
            section_type="vote",
            block_count=8,
        )
    ]
    blocks = [
        ExtractedTextBlock(
            "b1",
            3,
            "APP",
            "google_document_ai",
            x0=0.03,
            y0=0.128,
            x1=0.05,
            y1=0.133,
        ),
        ExtractedTextBlock(
            "b2",
            3,
            "ACUÑA PERALTA, MARÍA GRIMANEZA",
            "google_document_ai",
            x0=0.08,
            y0=0.127,
            x1=0.26,
            y1=0.134,
        ),
        ExtractedTextBlock(
            "b3",
            3,
            "SI +++ BS",
            "google_document_ai",
            x0=0.29,
            y0=0.128,
            x1=0.35,
            y1=0.133,
        ),
        ExtractedTextBlock(
            "b4",
            3,
            "FLORES RAMÍREZ, ALEX RANDU",
            "google_document_ai",
            x0=0.39,
            y0=0.127,
            x1=0.55,
            y1=0.134,
        ),
        ExtractedTextBlock(
            "b5",
            3,
            "SI +++ AP-PIS PAREDES FONSECA, KAROL IVETT",
            "google_document_ai",
            x0=0.60,
            y0=0.128,
            x1=0.86,
            y1=0.134,
        ),
        ExtractedTextBlock(
            "b6",
            3,
            "LP",
            "google_document_ai",
            x0=0.91,
            y0=0.128,
            x1=0.92,
            y1=0.133,
        ),
    ]

    rows = extract_candidate_rows("abc123", pages, blocks)

    assert len(rows) == 3
    assert [row.party_raw for row in rows] == ["APP", "BS", "AP-PIS"]
    assert [row.normalized_value for row in rows] == [
        "si",
        "si",
        "licencia_personal",
    ]
