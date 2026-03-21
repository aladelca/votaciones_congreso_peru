from __future__ import annotations

from dataclasses import replace

from congreso_votaciones.manifest import (
    manifest_from_discovery,
    merge_discovery_with_manifest,
    reconcile_manifest_records,
)
from congreso_votaciones.parse_index import build_record_id


def test_merge_discovery_preserves_identity(sample_record, tmp_path) -> None:  # type: ignore[no-untyped-def]
    previous = manifest_from_discovery(sample_record)
    previous.download_status = "failed"
    merged = merge_discovery_with_manifest(
        [sample_record],
        [previous],
        output_root=tmp_path / "data",
    )

    assert len(merged) == 1
    assert merged[0].record_id == sample_record.record_id
    assert merged[0].storage_relpath == previous.storage_relpath


def test_merge_discovery_keeps_undiscovered_existing_records(sample_record, tmp_path) -> None:  # type: ignore[no-untyped-def]
    extra_relative_path = "Apleno/ABC124/$FILE/Asistencia_sesion_2_1_2026.pdf"
    extra_record = replace(
        sample_record,
        record_id=build_record_id(extra_relative_path),
        pdf_relative_path=extra_relative_path,
        pdf_url=(
            "https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/"
            "Apleno/ABC124/$FILE/Asistencia_sesion_2_1_2026.pdf"
        ),
        filename_original="Asistencia_sesion_2_1_2026.pdf",
        session_date_raw="01/02/2026",
        session_date_iso="2026-01-02",
        source_title="Asistencia de la sesión del 2-1-2026",
    )

    previous = manifest_from_discovery(sample_record)
    preserved = manifest_from_discovery(extra_record)
    preserved.download_status = "failed"
    preserved.error_message = "kept"

    merged = merge_discovery_with_manifest(
        [sample_record],
        [previous, preserved],
        output_root=tmp_path / "data",
    )

    assert len(merged) == 2
    preserved_after_merge = next(
        record for record in merged if record.record_id == preserved.record_id
    )
    assert preserved_after_merge.download_status == "failed"
    assert preserved_after_merge.error_message == "kept"


def test_reconcile_manifest_marks_missing_download_as_pending(sample_record, tmp_path) -> None:  # type: ignore[no-untyped-def]
    record = manifest_from_discovery(sample_record)
    record.download_status = "downloaded"
    reconciled = reconcile_manifest_records([record], output_root=tmp_path / "data")

    assert reconciled[0].download_status == "pending"
    assert reconciled[0].error_message is not None
