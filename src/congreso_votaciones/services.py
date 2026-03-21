from __future__ import annotations

from congreso_votaciones.config import Settings
from congreso_votaciones.download import download_records, select_download_candidates
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
    apply_download_results,
    load_manifest,
    merge_discovery_with_manifest,
    reconcile_manifest_records,
    write_manifest_csv,
    write_manifest_jsonl,
)
from congreso_votaciones.models import CommandSummary, ManifestRecord, ServiceResult
from congreso_votaciones.parse_index import parse_pleno_index


def _persist_manifest(records: list[ManifestRecord], settings: Settings) -> None:
    write_manifest_csv(records, settings.manifest_csv_path)
    write_manifest_jsonl(records, settings.manifest_jsonl_path)


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
    existing_records = load_manifest(settings.manifest_jsonl_path)
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
    records = load_manifest(settings.manifest_jsonl_path)
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
