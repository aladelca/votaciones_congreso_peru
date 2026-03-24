from __future__ import annotations

from pathlib import Path

from congreso_votaciones.config import Settings
from congreso_votaciones.extraction_manifest import write_parse_manifest
from congreso_votaciones.extraction_models import (
    ExtractedPage,
    ExtractedTextBlock,
    ParseManifestRecord,
    PdfDocumentProfile,
    PdfPageProfile,
    ProviderExtraction,
)
from congreso_votaciones.manifest import manifest_from_discovery, write_manifest_jsonl
from congreso_votaciones.services import extract_pleno


def test_extract_pleno_processes_limited_documents_with_google_fallback(
    monkeypatch,
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    settings.google_cloud_project = "demo-project"
    settings.google_cloud_location = "us"
    settings.documentai_processor_id = "processor-123"

    manifest_record = manifest_from_discovery(sample_record)
    manifest_record.download_status = "downloaded"
    write_manifest_jsonl([manifest_record], settings.manifest_jsonl_path)

    def fake_profile(pdf_path: Path, *, record_id: str) -> PdfDocumentProfile:
        del pdf_path
        return PdfDocumentProfile(
            record_id=record_id,
            page_count=2,
            profile_class="hybrid",
            pages=[
                PdfPageProfile(1, 120, 20, 0, "native_text"),
                PdfPageProfile(2, 0, 0, 1, "image_only"),
            ],
        )

    def fake_native(pdf_path: Path, *, record_id: str) -> ProviderExtraction:
        del pdf_path
        return ProviderExtraction(
            provider_name="native_pdf",
            pages=[
                ExtractedPage(page_number=1, text="ASISTENCIA", source_backend="native_pdf"),
                ExtractedPage(page_number=2, text="", source_backend="native_pdf"),
            ],
            blocks=[
                ExtractedTextBlock(
                    block_id=f"{record_id}-n-1",
                    page_number=1,
                    text="APP ACUÑA PERALTA, MARIA GRIMANESA PRE",
                    source_backend="native_pdf",
                )
            ],
        )

    def fake_google(settings_arg, pdf_path: Path, *, record_id: str) -> ProviderExtraction:  # type: ignore[no-untyped-def]
        del settings_arg, pdf_path
        return ProviderExtraction(
            provider_name="google_document_ai",
            pages=[
                ExtractedPage(
                    page_number=1, text="ASISTENCIA", source_backend="google_document_ai"
                ),
                ExtractedPage(page_number=2, text="VOTACION", source_backend="google_document_ai"),
            ],
            blocks=[
                ExtractedTextBlock(
                    block_id=f"{record_id}-g-2",
                    page_number=2,
                    text="FP FLORES RUIZ, VICTOR SEFERINO SI",
                    source_backend="google_document_ai",
                    x0=0.1,
                    y0=0.1,
                    x1=0.9,
                    y1=0.2,
                )
            ],
        )

    monkeypatch.setattr("congreso_votaciones.services.profile_pdf", fake_profile)
    monkeypatch.setattr(
        "congreso_votaciones.services.extract_text_with_native_pdf",
        fake_native,
    )
    monkeypatch.setattr(
        "congreso_votaciones.services.extract_text_with_google_document_ai",
        fake_google,
    )

    result = extract_pleno(settings, limit=1, use_google=True)

    assert result.summary.processed == 1
    assert result.summary.succeeded == 1
    assert result.summary.failed == 0
    assert result.records[0].extraction_status == "extracted"
    assert result.records[0].preferred_backend == "hybrid"
    output_dir = (
        settings.output_root / "processed" / "pleno" / "intermediate" / manifest_record.record_id
    )
    assert (output_dir / "profile.json").exists()
    assert (output_dir / "candidate_rows.jsonl").exists()


def test_extract_pleno_force_google_uses_google_for_native_text_profiles(
    monkeypatch,
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()
    settings.google_cloud_project = "demo-project"
    settings.google_cloud_location = "us"
    settings.documentai_processor_id = "processor-123"

    manifest_record = manifest_from_discovery(sample_record)
    manifest_record.download_status = "downloaded"
    write_manifest_jsonl([manifest_record], settings.manifest_jsonl_path)

    def fake_profile(pdf_path: Path, *, record_id: str) -> PdfDocumentProfile:
        del pdf_path
        return PdfDocumentProfile(
            record_id=record_id,
            page_count=1,
            profile_class="native_text",
            pages=[
                PdfPageProfile(1, 120, 20, 0, "native_text"),
            ],
        )

    def fake_native(pdf_path: Path, *, record_id: str) -> ProviderExtraction:
        del pdf_path
        return ProviderExtraction(
            provider_name="native_pdf",
            pages=[
                ExtractedPage(page_number=1, text="ASISTENCIA", source_backend="native_pdf"),
            ],
            blocks=[],
        )

    def fake_google(settings_arg, pdf_path: Path, *, record_id: str) -> ProviderExtraction:  # type: ignore[no-untyped-def]
        del settings_arg, pdf_path
        return ProviderExtraction(
            provider_name="google_document_ai",
            pages=[
                ExtractedPage(
                    page_number=1,
                    text="VOTACION",
                    source_backend="google_document_ai",
                ),
            ],
            blocks=[
                ExtractedTextBlock(
                    block_id=f"{record_id}-g-1",
                    page_number=1,
                    text="FP FLORES RUIZ, VICTOR SEFERINO SI",
                    source_backend="google_document_ai",
                )
            ],
        )

    monkeypatch.setattr("congreso_votaciones.services.profile_pdf", fake_profile)
    monkeypatch.setattr(
        "congreso_votaciones.services.extract_text_with_native_pdf",
        fake_native,
    )
    monkeypatch.setattr(
        "congreso_votaciones.services.extract_text_with_google_document_ai",
        fake_google,
    )

    result = extract_pleno(settings, limit=1, use_google=True, force_google=True)

    assert result.summary.processed == 1
    assert result.summary.succeeded == 1
    assert result.records[0].preferred_backend == "google_document_ai"
    assert result.extracted_documents[0].pages[0].source_backend == "google_document_ai"


def test_extract_pleno_skips_records_already_extracted_without_force(
    sample_record,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    settings = Settings.from_root(tmp_path, output_root=tmp_path / "data")
    settings.ensure_directories()

    manifest_record = manifest_from_discovery(sample_record)
    manifest_record.download_status = "downloaded"
    write_manifest_jsonl([manifest_record], settings.manifest_jsonl_path)
    write_parse_manifest(
        settings.parse_manifest_jsonl_path,
        [
            ParseManifestRecord(
                record_id=manifest_record.record_id,
                storage_relpath=manifest_record.storage_relpath,
                session_date_iso=manifest_record.session_date_iso,
                document_type=manifest_record.document_type,
                extraction_status="extracted",
            )
        ],
    )

    result = extract_pleno(settings, limit=1, use_google=False)

    assert result.summary.processed == 0
    assert result.summary.skipped == 1
