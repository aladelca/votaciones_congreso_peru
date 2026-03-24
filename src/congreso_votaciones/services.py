from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from congreso_votaciones.candidate_rows import extract_candidate_rows
from congreso_votaciones.config import Settings
from congreso_votaciones.download import download_records, select_download_candidates
from congreso_votaciones.extraction_manifest import (
    build_parse_manifest_record,
    load_parse_manifest,
    merge_parse_manifest,
    write_parse_manifest,
)
from congreso_votaciones.extraction_models import (
    DocumentExtraction,
    ExtractedTextBlock,
    ExtractionBackend,
    ExtractionServiceResult,
    ParseManifestRecord,
    PdfDocumentProfile,
    ProviderExtraction,
)
from congreso_votaciones.fetch import (
    build_client,
    build_expand_view_url,
    ensure_contains_documents,
    extract_iframe_url,
    fetch_expand_view_html,
    fetch_public_page,
    save_html_snapshot,
)
from congreso_votaciones.logging_utils import log_event
from congreso_votaciones.manifest import (
    ManifestLoadError,
    apply_download_results,
    load_manifest,
    merge_discovery_with_manifest,
    reconcile_manifest_records,
    write_manifest_csv,
    write_manifest_jsonl,
)
from congreso_votaciones.models import CommandSummary, ManifestRecord, ServiceResult
from congreso_votaciones.parse_index import parse_pleno_index
from congreso_votaciones.parse_store import persist_document_artifacts, summarize_candidate_rows
from congreso_votaciones.pdf_profile import profile_pdf
from congreso_votaciones.providers.google_document_ai import extract_text_with_google_document_ai
from congreso_votaciones.providers.native_pdf import extract_text_with_native_pdf
from congreso_votaciones.section_parser import classify_page_text


def _persist_manifest(records: list[ManifestRecord], settings: Settings) -> None:
    write_manifest_jsonl(records, settings.manifest_jsonl_path)
    write_manifest_csv(records, settings.manifest_csv_path)


def _load_manifest_records(settings: Settings, *, command: str) -> list[ManifestRecord]:
    try:
        return load_manifest(settings.manifest_jsonl_path)
    except ManifestLoadError as exc:
        log_event(
            settings,
            "manifest_load_failed",
            command=command,
            manifest_jsonl=str(settings.manifest_jsonl_path),
            error_message=str(exc),
        )
        raise


def _load_cached_html(settings: Settings) -> tuple[str, str] | None:
    if not settings.public_page_path.exists() or not settings.expanded_view_path.exists():
        return None
    public_html = settings.public_page_path.read_text(encoding="utf-8")
    expanded_html = settings.expanded_view_path.read_text(encoding="utf-8")
    if not public_html.strip() or not expanded_html.strip():
        return None
    return public_html, expanded_html


def _build_summary(
    settings: Settings,
    *,
    command: str,
    records: list[ManifestRecord],
    discovered: int = 0,
    downloaded: int = 0,
    skipped: int = 0,
    failed: int = 0,
    exit_code: int = 0,
) -> CommandSummary:
    pending = sum(1 for record in records if record.download_status == "pending")
    return CommandSummary(
        command=command,
        discovered=discovered or len(records),
        pending=pending,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        manifest_csv_path=settings.manifest_csv_path,
        manifest_jsonl_path=settings.manifest_jsonl_path,
        exit_code=exit_code,
        notes=[f"log_path={settings.log_path}"],
    )


def _load_parse_manifest_records(settings: Settings) -> list[ParseManifestRecord]:
    return load_parse_manifest(settings.parse_manifest_jsonl_path)


def _select_extraction_candidates(
    records: list[ManifestRecord],
    existing_parse_records: list[ParseManifestRecord],
    *,
    limit: int | None,
    record_id: str | None,
    force: bool,
) -> tuple[list[ManifestRecord], int]:
    parse_records_by_id = {record.record_id: record for record in existing_parse_records}
    eligible: list[ManifestRecord] = []
    skipped = 0
    for record in records:
        if record.download_status != "downloaded":
            skipped += 1
            continue
        if record_id is not None and record.record_id != record_id:
            skipped += 1
            continue
        previous_parse = parse_records_by_id.get(record.record_id)
        if (
            not force
            and previous_parse is not None
            and previous_parse.extraction_status == "extracted"
        ):
            skipped += 1
            continue
        eligible.append(record)

    if limit is not None:
        skipped += max(0, len(eligible) - limit)
        eligible = eligible[:limit]
    return eligible, skipped


def _select_page_extraction(
    profile: PdfDocumentProfile,
    native_result: ProviderExtraction,
    google_result: ProviderExtraction | None,
    *,
    prefer_google: bool = False,
) -> tuple[ProviderExtraction, ExtractionBackend]:
    native_pages = {page.page_number: page for page in native_result.pages}
    google_pages = {} if google_result is None else {
        page.page_number: page for page in google_result.pages
    }
    native_blocks_by_page: dict[int, list[ExtractedTextBlock]] = {}
    google_blocks_by_page: dict[int, list[ExtractedTextBlock]] = {}
    for block in native_result.blocks:
        native_blocks_by_page.setdefault(block.page_number, []).append(block)
    if google_result is not None:
        for block in google_result.blocks:
            google_blocks_by_page.setdefault(block.page_number, []).append(block)

    merged_pages = []
    merged_blocks: list[ExtractedTextBlock] = []
    page_backends: set[str] = set()
    for page_profile in profile.pages:
        page_number = page_profile.page_number
        use_google = page_number in google_pages and (
            prefer_google or page_profile.profile_class in {"image_only", "hybrid"}
        )
        selected_page = (
            google_pages.get(page_number) if use_google else native_pages.get(page_number)
        )
        selected_blocks = (
            google_blocks_by_page.get(page_number, [])
            if use_google
            else native_blocks_by_page.get(page_number, [])
        )
        if selected_page is None:
            fallback_page = native_pages.get(page_number) or google_pages.get(page_number)
            if fallback_page is None:
                continue
            selected_page = fallback_page
            selected_blocks = native_blocks_by_page.get(page_number, []) or (
                google_blocks_by_page.get(page_number, [])
            )

        section_type = classify_page_text(selected_page.text)
        merged_pages.append(
            replace(
                selected_page,
                section_type=section_type,
                block_count=len(selected_blocks),
            )
        )
        merged_blocks.extend(selected_blocks)
        page_backends.add(selected_page.source_backend)

    preferred_backend: ExtractionBackend = "native_pdf"
    if page_backends == {"google_document_ai"}:
        preferred_backend = "google_document_ai"
    elif "google_document_ai" in page_backends and "native_pdf" in page_backends:
        preferred_backend = "hybrid"

    return ProviderExtraction(
        provider_name=preferred_backend,
        pages=merged_pages,
        blocks=merged_blocks,
    ), preferred_backend


def discover_pleno(
    settings: Settings,
    *,
    limit: int | None = None,
    refresh_html: bool = False,
) -> ServiceResult:
    settings.ensure_directories()
    log_event(
        settings,
        "discover_started",
        command="discover-pleno",
        refresh_html=refresh_html,
        limit=limit,
    )

    html_source = "network"
    cached_html = None if refresh_html else _load_cached_html(settings)
    if cached_html is not None:
        public_html, expanded_html = cached_html
        iframe_url = extract_iframe_url(public_html, settings.source_page_url)
        expand_view_url = build_expand_view_url(iframe_url)
        ensure_contains_documents(expanded_html)
        html_source = "cache"
    else:
        with build_client(settings) as client:
            public_html = fetch_public_page(client, settings.source_page_url)
            iframe_url = extract_iframe_url(public_html, settings.source_page_url)
            expand_view_url = build_expand_view_url(iframe_url)
            expanded_html = fetch_expand_view_html(client, expand_view_url)

        ensure_contains_documents(expanded_html)
        save_html_snapshot(settings.public_page_path, public_html)
        save_html_snapshot(settings.expanded_view_path, expanded_html)

    discovered_records = parse_pleno_index(
        expanded_html,
        source_page_url=settings.source_page_url,
        iframe_url=iframe_url,
        expand_view_url=expand_view_url,
        limit=limit,
    )
    existing_records = _load_manifest_records(settings, command="discover-pleno")
    merged_records = merge_discovery_with_manifest(
        discovered_records,
        existing_records,
        output_root=settings.output_root,
    )
    _persist_manifest(merged_records, settings)
    summary = _build_summary(
        settings,
        command="discover-pleno",
        records=merged_records,
        discovered=len(discovered_records),
    )
    summary.notes.append(f"html_source={html_source}")
    log_event(
        settings,
        "discover_completed",
        command="discover-pleno",
        discovered=summary.discovered,
        pending=summary.pending,
        html_source=html_source,
        manifest_jsonl=str(settings.manifest_jsonl_path),
    )
    return ServiceResult(records=merged_records, summary=summary)


def _download_from_records(
    records: list[ManifestRecord],
    *,
    settings: Settings,
    command: str,
    limit: int | None = None,
    retry_failed: bool = False,
    max_concurrency: int | None = None,
) -> ServiceResult:
    log_event(
        settings,
        "download_started",
        command=command,
        limit=limit,
        retry_failed=retry_failed,
        max_concurrency=max_concurrency or settings.max_concurrency,
    )
    reconciled = reconcile_manifest_records(records, output_root=settings.output_root)
    candidates = select_download_candidates(reconciled, retry_failed=retry_failed, limit=limit)
    skipped = len(reconciled) - len(candidates)

    results = download_records(
        candidates,
        settings=settings,
        max_concurrency=max_concurrency,
    )
    updated_records = apply_download_results(reconciled, results)
    _persist_manifest(updated_records, settings)

    downloaded = sum(1 for result in results if result.download_status == "downloaded")
    failed = sum(1 for result in results if result.download_status == "failed")
    summary = _build_summary(
        settings,
        command=command,
        records=updated_records,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        exit_code=1 if failed else 0,
    )
    summary.notes.append(f"download_candidates={len(candidates)}")
    for result in results:
        if result.download_status == "failed":
            log_event(
                settings,
                "download_failed_record",
                command=command,
                record_id=result.record_id,
                error_message=result.error_message,
            )
    log_event(
        settings,
        "download_completed",
        command=command,
        downloaded=downloaded,
        skipped=skipped,
        failed=failed,
        manifest_jsonl=str(settings.manifest_jsonl_path),
    )
    return ServiceResult(records=updated_records, summary=summary)


def download_pleno(
    settings: Settings,
    *,
    limit: int | None = None,
    retry_failed: bool = False,
    max_concurrency: int | None = None,
) -> ServiceResult:
    settings.ensure_directories()
    records = _load_manifest_records(settings, command="download-pleno")
    if not records:
        log_event(
            settings,
            "download_missing_manifest",
            command="download-pleno",
            manifest_jsonl=str(settings.manifest_jsonl_path),
        )
        raise FileNotFoundError(
            "No existe manifiesto en "
            f"{settings.manifest_jsonl_path}. Ejecuta discover-pleno primero."
        )
    return _download_from_records(
        records,
        settings=settings,
        command="download-pleno",
        limit=limit,
        retry_failed=retry_failed,
        max_concurrency=max_concurrency,
    )


def sync_pleno(
    settings: Settings,
    *,
    limit: int | None = None,
    retry_failed: bool = False,
    max_concurrency: int | None = None,
    refresh_html: bool = False,
) -> ServiceResult:
    discovery = discover_pleno(settings, limit=limit, refresh_html=refresh_html)
    download = _download_from_records(
        discovery.records,
        settings=settings,
        command="sync-pleno",
        limit=limit,
        retry_failed=retry_failed,
        max_concurrency=max_concurrency,
    )
    download.summary = CommandSummary(
        command="sync-pleno",
        discovered=discovery.summary.discovered,
        pending=download.summary.pending,
        downloaded=download.summary.downloaded,
        skipped=download.summary.skipped,
        failed=download.summary.failed,
        manifest_csv_path=settings.manifest_csv_path,
        manifest_jsonl_path=settings.manifest_jsonl_path,
        exit_code=download.summary.exit_code,
        notes=discovery.summary.notes + download.summary.notes,
    )
    return download


def extract_pleno(
    settings: Settings,
    *,
    limit: int | None = None,
    record_id: str | None = None,
    force: bool = False,
    use_google: bool = True,
    force_google: bool = False,
) -> ExtractionServiceResult:
    settings.ensure_directories()
    log_event(
        settings,
        "extract_started",
        command="extract-pleno",
        limit=limit,
        record_id=record_id,
        force=force,
        use_google=use_google,
        force_google=force_google,
    )

    manifest_records = _load_manifest_records(settings, command="extract-pleno")
    if not manifest_records:
        raise FileNotFoundError(
            "No existe manifiesto en "
            f"{settings.manifest_jsonl_path}. Ejecuta discover-pleno y download-pleno primero."
        )

    parse_records = _load_parse_manifest_records(settings)
    candidates, skipped = _select_extraction_candidates(
        manifest_records,
        parse_records,
        limit=limit,
        record_id=record_id,
        force=force,
    )

    extracted_documents: list[DocumentExtraction] = []
    updated_parse_records: list[ParseManifestRecord] = []
    succeeded = 0
    failed = 0

    for record in candidates:
        parse_record = next(
            (candidate for candidate in parse_records if candidate.record_id == record.record_id),
            build_parse_manifest_record(record),
        )
        parse_record.attempt_count += 1
        pdf_path = settings.output_root / record.storage_relpath
        try:
            profile = profile_pdf(pdf_path, record_id=record.record_id)
            native_result = extract_text_with_native_pdf(pdf_path, record_id=record.record_id)
            google_result = None
            should_call_google = use_google and (
                force_google
                or any(page.profile_class in {"image_only", "hybrid"} for page in profile.pages)
            )
            if should_call_google:
                google_result = extract_text_with_google_document_ai(
                    settings,
                    pdf_path,
                    record_id=record.record_id,
                )

            merged_result, preferred_backend = _select_page_extraction(
                profile,
                native_result,
                google_result,
                prefer_google=force_google,
            )
            candidate_rows = extract_candidate_rows(
                record.record_id,
                merged_result.pages,
                merged_result.blocks,
            )
            extraction = DocumentExtraction(
                record_id=record.record_id,
                profile=profile,
                preferred_backend=preferred_backend,
                pages=merged_result.pages,
                blocks=merged_result.blocks,
                candidate_rows=candidate_rows,
            )
            output_relpath = persist_document_artifacts(settings, record, extraction)
            parse_record.profile_class = profile.profile_class
            parse_record.preferred_backend = preferred_backend
            parse_record.extraction_status = "extracted"
            parse_record.page_count = profile.page_count
            parse_record.extracted_at = datetime.now(UTC).isoformat()
            parse_record.error_message = None
            parse_record.output_relpath = str(output_relpath)
            extracted_documents.append(extraction)
            updated_parse_records.append(parse_record)
            succeeded += 1
            log_event(
                settings,
                "extract_document_completed",
                command="extract-pleno",
                record_id=record.record_id,
                preferred_backend=preferred_backend,
                profile_class=profile.profile_class,
                candidate_rows=summarize_candidate_rows(candidate_rows),
                output_relpath=str(output_relpath),
            )
        except Exception as exc:  # noqa: BLE001
            parse_record.extraction_status = "failed"
            parse_record.error_message = str(exc)
            updated_parse_records.append(parse_record)
            failed += 1
            log_event(
                settings,
                "extract_document_failed",
                command="extract-pleno",
                record_id=record.record_id,
                error_message=str(exc),
            )

    merged_parse_manifest = merge_parse_manifest(parse_records, updated_parse_records)
    write_parse_manifest(settings.parse_manifest_jsonl_path, merged_parse_manifest)
    summary = CommandSummary(
        command="extract-pleno",
        processed=len(candidates),
        succeeded=succeeded,
        skipped=skipped,
        failed=failed,
        manifest_jsonl_path=settings.parse_manifest_jsonl_path,
        exit_code=1 if failed else 0,
        notes=[
            f"processed_root={settings.processed_pleno_root}",
            f"documentai_configured={settings.documentai_is_configured}",
        ],
    )
    log_event(
        settings,
        "extract_completed",
        command="extract-pleno",
        processed=summary.processed,
        succeeded=summary.succeeded,
        skipped=summary.skipped,
        failed=summary.failed,
        parse_manifest_jsonl=str(settings.parse_manifest_jsonl_path),
    )
    return ExtractionServiceResult(
        records=merged_parse_manifest,
        summary=summary,
        extracted_documents=extracted_documents,
    )
