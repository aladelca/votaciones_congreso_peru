from __future__ import annotations

from congreso_votaciones.config import Settings
from congreso_votaciones.download import download_records, is_valid_pdf_file
from congreso_votaciones.manifest import manifest_from_discovery


def test_download_records_writes_valid_pdf(monkeypatch, sample_record, tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    manifest_record = manifest_from_discovery(sample_record)

    def fake_download_pdf_bytes(client, pdf_url, *, timeout):  # type: ignore[no-untyped-def]
        del client, pdf_url, timeout
        return (b"%PDF-1.7\ncontenido", 200, "application/pdf")

    monkeypatch.setattr("congreso_votaciones.download.download_pdf_bytes", fake_download_pdf_bytes)
    results = download_records([manifest_record], settings=settings, max_concurrency=1)

    destination = settings.output_root / manifest_record.storage_relpath
    assert results[0].download_status == "downloaded"
    assert destination.exists()
    assert is_valid_pdf_file(destination) is True


def test_download_records_marks_invalid_bytes_as_failed(
    monkeypatch,
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    manifest_record = manifest_from_discovery(sample_record)

    def fake_download_pdf_bytes(client, pdf_url, *, timeout):  # type: ignore[no-untyped-def]
        del client, pdf_url, timeout
        return (b"no-pdf", 200, "text/plain")

    monkeypatch.setattr("congreso_votaciones.download.download_pdf_bytes", fake_download_pdf_bytes)
    results = download_records([manifest_record], settings=settings, max_concurrency=1)

    assert results[0].download_status == "failed"
    assert results[0].error_message is not None
