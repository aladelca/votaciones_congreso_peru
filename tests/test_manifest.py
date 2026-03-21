from __future__ import annotations

from dataclasses import replace

import pytest

from congreso_votaciones.manifest import (
    ManifestLoadError,
    ManifestPersistError,
    load_manifest,
    manifest_from_discovery,
    merge_discovery_with_manifest,
    reconcile_manifest_records,
    write_manifest_csv,
    write_manifest_jsonl,
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


def test_load_manifest_fails_fast_on_malformed_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "pleno_pdfs_index.jsonl"
    manifest_path.write_text('{"record_id": "abc"\n', encoding="utf-8")

    with pytest.raises(ManifestLoadError) as exc_info:
        load_manifest(manifest_path)

    message = str(exc_info.value)
    assert str(manifest_path) in message
    assert ":1" in message
    assert "JSON invalido" in message
    assert "manifiesto canonico" in message


def test_load_manifest_fails_fast_on_invalid_manifest_payload(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "pleno_pdfs_index.jsonl"
    manifest_path.write_text('{"record_id": "abc"}\n', encoding="utf-8")

    with pytest.raises(ManifestLoadError) as exc_info:
        load_manifest(manifest_path)

    message = str(exc_info.value)
    assert str(manifest_path) in message
    assert ":1" in message
    assert "payload invalido" in message
    assert "ManifestRecord" in message


def test_load_manifest_rejects_blank_existing_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "pleno_pdfs_index.jsonl"
    manifest_path.write_text("\n \n", encoding="utf-8")

    with pytest.raises(ManifestLoadError) as exc_info:
        load_manifest(manifest_path)

    assert "vacio" in str(exc_info.value)


def test_write_manifest_jsonl_is_atomic_on_replace_failure(
    monkeypatch,
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "pleno_pdfs_index.jsonl"
    manifest_path.write_text('{"stale": true}\n', encoding="utf-8")
    manifest_record = manifest_from_discovery(sample_record)

    def fail_replace(source, destination):  # type: ignore[no-untyped-def]
        del source, destination
        raise OSError("simulated replace failure")

    monkeypatch.setattr("congreso_votaciones.manifest.os.replace", fail_replace)

    with pytest.raises(ManifestPersistError) as exc_info:
        write_manifest_jsonl([manifest_record], manifest_path)

    assert str(manifest_path) in str(exc_info.value)
    assert manifest_path.read_text(encoding="utf-8") == '{"stale": true}\n'
    assert list(manifest_path.parent.glob(f".{manifest_path.name}.tmp-*")) == []


def test_write_manifest_csv_is_atomic_on_replace_failure(
    monkeypatch,
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    manifest_path = tmp_path / "pleno_pdfs_index.csv"
    manifest_path.write_text("stale,csv\n", encoding="utf-8")
    manifest_record = manifest_from_discovery(sample_record)

    def fail_replace(source, destination):  # type: ignore[no-untyped-def]
        del source, destination
        raise OSError("simulated replace failure")

    monkeypatch.setattr("congreso_votaciones.manifest.os.replace", fail_replace)

    with pytest.raises(ManifestPersistError) as exc_info:
        write_manifest_csv([manifest_record], manifest_path)

    assert str(manifest_path) in str(exc_info.value)
    assert manifest_path.read_text(encoding="utf-8") == "stale,csv\n"
    assert list(manifest_path.parent.glob(f".{manifest_path.name}.tmp-*")) == []
