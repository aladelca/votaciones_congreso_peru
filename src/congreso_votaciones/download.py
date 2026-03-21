from __future__ import annotations

import hashlib
import os
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import httpx

from congreso_votaciones.config import Settings
from congreso_votaciones.fetch import download_pdf_bytes
from congreso_votaciones.models import DownloadResult, ManifestRecord


class DownloadCallable(Protocol):
    def __call__(
        self,
        client: httpx.Client,
        pdf_url: str,
        *,
        timeout: float,
    ) -> tuple[bytes, int, str | None]: ...


class StorageRecord(Protocol):
    @property
    def periodo_parlamentario(self) -> str: ...

    @property
    def session_date_iso(self) -> str: ...

    @property
    def record_id(self) -> str: ...


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in ascii_only)
    compact = "-".join(part for part in cleaned.split("-") if part)
    return compact or "desconocido"


def build_storage_relpath(record: StorageRecord) -> str:
    periodo = record.periodo_parlamentario
    date_iso = record.session_date_iso
    record_id = record.record_id
    return str(
        Path("raw") / "pleno" / "pdfs" / slugify(str(periodo)) / f"{date_iso}__{record_id}.pdf"
    )


def is_valid_pdf_bytes(content: bytes) -> bool:
    return content.startswith(b"%PDF") and len(content) > 4


def is_valid_pdf_file(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with path.open("rb") as file_handle:
        return file_handle.read(4) == b"%PDF"


def select_download_candidates(
    records: list[ManifestRecord],
    *,
    retry_failed: bool,
    limit: int | None,
) -> list[ManifestRecord]:
    eligible: list[ManifestRecord] = []
    for record in records:
        if record.download_status == "pending":
            eligible.append(record)
        elif retry_failed and record.download_status == "failed":
            eligible.append(record)
    if limit is None:
        return eligible
    return eligible[:limit]


def _download_once(
    record: ManifestRecord,
    *,
    settings: Settings,
    fetch_pdf: DownloadCallable | None = None,
) -> DownloadResult:
    fetch_pdf_impl = fetch_pdf or download_pdf_bytes
    destination = settings.output_root / record.storage_relpath
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(f"{destination.suffix}.part")
    last_error = "No se pudo descargar el PDF."

    for attempt in range(settings.retries):
        try:
            with httpx.Client(
                headers=settings.default_headers(),
                follow_redirects=True,
                timeout=settings.pdf_timeout,
            ) as client:
                content, http_status, content_type = fetch_pdf_impl(
                    client,
                    record.pdf_url,
                    timeout=settings.pdf_timeout,
                )
            if not is_valid_pdf_bytes(content):
                raise ValueError("El contenido descargado no tiene firma PDF valida.")

            temp_path.write_bytes(content)
            os.replace(temp_path, destination)

            return DownloadResult(
                record_id=record.record_id,
                download_status="downloaded",
                http_status=http_status,
                content_type=content_type,
                content_length=destination.stat().st_size,
                sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                downloaded_at=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            temp_path.unlink(missing_ok=True)
            if attempt + 1 < settings.retries:
                time.sleep(min(2**attempt, 4))

    return DownloadResult(
        record_id=record.record_id,
        download_status="failed",
        error_message=last_error,
    )


def download_records(
    records: list[ManifestRecord],
    *,
    settings: Settings,
    max_concurrency: int | None = None,
) -> list[DownloadResult]:
    if not records:
        return []

    worker_count = max(1, max_concurrency or settings.max_concurrency)
    results: list[DownloadResult] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_download_once, record, settings=settings): record.record_id
            for record in records
        }
        for future in as_completed(futures):
            results.append(future.result())
    return results
