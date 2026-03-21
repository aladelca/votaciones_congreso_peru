from __future__ import annotations

import json
from hashlib import sha256

import pytest

from congreso_votaciones import services
from congreso_votaciones.config import Settings
from congreso_votaciones.manifest import (
    ManifestLoadError,
    load_manifest,
    manifest_from_discovery,
    write_manifest_jsonl,
)
from congreso_votaciones.models import DownloadResult
from congreso_votaciones.services import discover_pleno, download_pleno


def test_discover_pleno_uses_cached_html_and_logs(
    monkeypatch,
    pleno_public_page_html: str,
    pleno_index_expanded_html: str,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    settings.public_page_path.write_text(pleno_public_page_html, encoding="utf-8")
    settings.expanded_view_path.write_text(pleno_index_expanded_html, encoding="utf-8")

    def fail_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise AssertionError("No deberia consultar la red cuando existe cache HTML.")

    monkeypatch.setattr("congreso_votaciones.services.fetch_public_page", fail_fetch)
    monkeypatch.setattr("congreso_votaciones.services.fetch_expand_view_html", fail_fetch)

    result = discover_pleno(settings, limit=2, refresh_html=False)

    assert result.summary.discovered == 2
    assert "html_source=cache" in result.summary.notes
    log_entries = [
        json.loads(line) for line in settings.log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert log_entries[-1]["event"] == "discover_completed"
    assert log_entries[-1]["html_source"] == "cache"


def test_download_pleno_logs_summary(monkeypatch, sample_record, tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    manifest_record = manifest_from_discovery(sample_record)
    write_manifest_jsonl([manifest_record], settings.manifest_jsonl_path)

    def fake_download_records(records, *, settings, max_concurrency):  # type: ignore[no-untyped-def]
        del settings, max_concurrency
        return [
            DownloadResult(
                record_id=records[0].record_id,
                download_status="downloaded",
                http_status=200,
                content_type="application/pdf",
                content_length=12,
                sha256="abc",
                downloaded_at="2026-03-20T00:00:00+00:00",
            )
        ]

    monkeypatch.setattr("congreso_votaciones.services.download_records", fake_download_records)
    result = download_pleno(settings, limit=1, retry_failed=False, max_concurrency=1)

    assert result.summary.downloaded == 1
    assert "download_candidates=1" in result.summary.notes
    log_entries = [
        json.loads(line) for line in settings.log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert log_entries[-1]["event"] == "download_completed"
    assert log_entries[-1]["downloaded"] == 1


def test_discover_pleno_limit_preserves_existing_manifest_records(
    pleno_public_page_html: str,
    pleno_index_expanded_html: str,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    settings.public_page_path.write_text(pleno_public_page_html, encoding="utf-8")
    settings.expanded_view_path.write_text(pleno_index_expanded_html, encoding="utf-8")

    initial_result = discover_pleno(settings, limit=5, refresh_html=False)
    assert initial_result.summary.discovered == 5

    manifest_records = load_manifest(settings.manifest_jsonl_path)
    preserved_record = manifest_records[-1]
    preserved_bytes = b"%PDF-1.7\npreserved"
    preserved_destination = settings.output_root / preserved_record.storage_relpath
    preserved_destination.parent.mkdir(parents=True, exist_ok=True)
    preserved_destination.write_bytes(preserved_bytes)
    preserved_record.download_status = "downloaded"
    preserved_record.http_status = 200
    preserved_record.content_type = "application/pdf"
    preserved_record.content_length = len(preserved_bytes)
    preserved_record.sha256 = sha256(preserved_bytes).hexdigest()
    preserved_record.downloaded_at = "2026-03-20T00:00:00+00:00"
    write_manifest_jsonl(manifest_records, settings.manifest_jsonl_path)

    limited_result = discover_pleno(settings, limit=2, refresh_html=False)
    reloaded_manifest = load_manifest(settings.manifest_jsonl_path)

    assert limited_result.summary.discovered == 2
    assert len(limited_result.records) == 5
    assert len(reloaded_manifest) == 5
    preserved_after_limit = next(
        record for record in reloaded_manifest if record.record_id == preserved_record.record_id
    )
    assert preserved_after_limit.download_status == "downloaded"
    assert preserved_after_limit.sha256 == sha256(preserved_bytes).hexdigest()


def test_download_pleno_logs_manifest_load_failure(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    settings.manifest_jsonl_path.write_text('{"record_id": "abc"}\n', encoding="utf-8")

    with pytest.raises(ManifestLoadError) as exc_info:
        download_pleno(settings)

    assert str(settings.manifest_jsonl_path) in str(exc_info.value)
    log_entries = [
        json.loads(line) for line in settings.log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert log_entries[-1]["event"] == "manifest_load_failed"
    assert log_entries[-1]["command"] == "download-pleno"
    assert log_entries[-1]["manifest_jsonl"] == str(settings.manifest_jsonl_path)


def test_persist_manifest_prioritizes_jsonl_before_csv(
    monkeypatch,
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    settings.manifest_csv_path.write_text("stale,csv\n", encoding="utf-8")
    manifest_record = manifest_from_discovery(sample_record)
    call_order: list[str] = []
    original_write_manifest_jsonl = services.write_manifest_jsonl

    def tracked_write_manifest_jsonl(records, path):  # type: ignore[no-untyped-def]
        call_order.append("jsonl")
        return original_write_manifest_jsonl(records, path)

    def fail_write_manifest_csv(records, path):  # type: ignore[no-untyped-def]
        del records
        call_order.append("csv")
        raise OSError(f"simulated csv failure for {path}")

    monkeypatch.setattr(services, "write_manifest_jsonl", tracked_write_manifest_jsonl)
    monkeypatch.setattr(services, "write_manifest_csv", fail_write_manifest_csv)

    with pytest.raises(OSError) as exc_info:
        services._persist_manifest([manifest_record], settings)

    assert call_order == ["jsonl", "csv"]
    assert str(settings.manifest_csv_path) in str(exc_info.value)
    reloaded_manifest = load_manifest(settings.manifest_jsonl_path)
    assert [record.record_id for record in reloaded_manifest] == [manifest_record.record_id]
    assert settings.manifest_csv_path.read_text(encoding="utf-8") == "stale,csv\n"
