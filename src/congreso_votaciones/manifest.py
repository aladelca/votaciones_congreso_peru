from __future__ import annotations

import csv
import json
import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from congreso_votaciones.download import build_storage_relpath, is_valid_pdf_file
from congreso_votaciones.models import DownloadResult, ManifestRecord, PlenoPdfRecord

MANIFEST_FIELDS = [
    "record_id",
    "source_page_url",
    "iframe_url",
    "expand_view_url",
    "periodo_parlamentario",
    "periodo_anual",
    "legislatura",
    "session_date_raw",
    "session_date_iso",
    "source_title",
    "document_type",
    "session_type",
    "is_provisional",
    "is_official",
    "pdf_relative_path",
    "pdf_url",
    "filename_original",
    "storage_relpath",
    "download_status",
    "http_status",
    "content_type",
    "content_length",
    "sha256",
    "downloaded_at",
    "error_message",
]


class ManifestLoadError(ValueError):
    def __init__(
        self,
        *,
        path: Path,
        detail: str,
        line_number: int | None = None,
    ) -> None:
        self.path = path
        self.detail = detail
        self.line_number = line_number
        self.recovery_hint = (
            "El JSONL es el manifiesto canonico; corrige o reemplaza este archivo y "
            "vuelve a ejecutar discover-pleno para regenerar el CSV derivado."
        )
        location = str(path)
        if line_number is not None:
            location = f"{location}:{line_number}"
        super().__init__(f"Manifiesto JSONL invalido en {location}: {detail}. {self.recovery_hint}")


class ManifestPersistError(OSError):
    def __init__(self, *, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(f"No se pudo persistir el manifiesto en {path}: {detail}")


class _WritableTextFile(Protocol):
    def write(self, content: str) -> int: ...

    def flush(self) -> None: ...

    def fileno(self) -> int: ...


def manifest_from_discovery(
    record: PlenoPdfRecord,
    *,
    storage_relpath: str | None = None,
) -> ManifestRecord:
    return ManifestRecord(
        record_id=record.record_id,
        source_page_url=record.source_page_url,
        iframe_url=record.iframe_url,
        expand_view_url=record.expand_view_url,
        periodo_parlamentario=record.periodo_parlamentario,
        periodo_anual=record.periodo_anual,
        legislatura=record.legislatura,
        session_date_raw=record.session_date_raw,
        session_date_iso=record.session_date_iso,
        source_title=record.source_title,
        document_type=record.document_type,
        session_type=record.session_type,
        is_provisional=record.is_provisional,
        is_official=record.is_official,
        pdf_relative_path=record.pdf_relative_path,
        pdf_url=record.pdf_url,
        filename_original=record.filename_original,
        storage_relpath=storage_relpath or build_storage_relpath(record),
    )


def load_manifest(path: Path) -> list[ManifestRecord]:
    if not path.exists():
        return []

    records: list[ManifestRecord] = []
    saw_record = False
    with path.open(encoding="utf-8") as file_handle:
        for line_number, line in enumerate(file_handle, start=1):
            if not line.strip():
                continue
            saw_record = True
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                detail = f"JSON invalido en columna {exc.colno}: {exc.msg}"
                raise ManifestLoadError(
                    path=path,
                    line_number=line_number,
                    detail=detail,
                ) from exc
            records.append(
                _manifest_record_from_payload(
                    payload,
                    path=path,
                    line_number=line_number,
                )
            )
    if not saw_record:
        raise ManifestLoadError(
            path=path,
            detail="el archivo esta vacio o solo contiene espacios en blanco",
        )
    return records


def _manifest_record_from_payload(
    payload: Any,
    *,
    path: Path,
    line_number: int,
) -> ManifestRecord:
    if not isinstance(payload, dict):
        raise ManifestLoadError(
            path=path,
            line_number=line_number,
            detail=f"se esperaba un objeto JSON y se recibio {type(payload).__name__}",
        )
    try:
        return ManifestRecord(**payload)
    except TypeError as exc:
        raise ManifestLoadError(
            path=path,
            line_number=line_number,
            detail=f"payload invalido para ManifestRecord ({exc})",
        ) from exc


def reconcile_manifest_records(
    records: list[ManifestRecord],
    *,
    output_root: Path,
) -> list[ManifestRecord]:
    for record in records:
        destination = output_root / record.storage_relpath
        if record.download_status == "downloaded" and not is_valid_pdf_file(destination):
            record.download_status = "pending"
            record.error_message = "El archivo local no existe o fallo la validacion PDF."
            record.http_status = None
            record.content_type = None
            record.content_length = None
            record.sha256 = None
            record.downloaded_at = None
    return records


def _restore_manifest_state(
    current: ManifestRecord,
    previous: ManifestRecord,
) -> ManifestRecord:
    current.storage_relpath = previous.storage_relpath or current.storage_relpath
    current.download_status = previous.download_status
    current.http_status = previous.http_status
    current.content_type = previous.content_type
    current.content_length = previous.content_length
    current.sha256 = previous.sha256
    current.downloaded_at = previous.downloaded_at
    current.error_message = previous.error_message
    return current


def _clone_manifest_record(record: ManifestRecord) -> ManifestRecord:
    return ManifestRecord(
        record_id=record.record_id,
        source_page_url=record.source_page_url,
        iframe_url=record.iframe_url,
        expand_view_url=record.expand_view_url,
        periodo_parlamentario=record.periodo_parlamentario,
        periodo_anual=record.periodo_anual,
        legislatura=record.legislatura,
        session_date_raw=record.session_date_raw,
        session_date_iso=record.session_date_iso,
        source_title=record.source_title,
        document_type=record.document_type,
        session_type=record.session_type,
        is_provisional=record.is_provisional,
        is_official=record.is_official,
        pdf_relative_path=record.pdf_relative_path,
        pdf_url=record.pdf_url,
        filename_original=record.filename_original,
        storage_relpath=record.storage_relpath,
        download_status=record.download_status,
        http_status=record.http_status,
        content_type=record.content_type,
        content_length=record.content_length,
        sha256=record.sha256,
        downloaded_at=record.downloaded_at,
        error_message=record.error_message,
    )


def merge_discovery_with_manifest(
    discovered: list[PlenoPdfRecord],
    existing: list[ManifestRecord],
    *,
    output_root: Path,
) -> list[ManifestRecord]:
    existing_by_id = {record.record_id: record for record in existing}
    merged: list[ManifestRecord] = []
    discovered_ids: set[str] = set()

    for record in discovered:
        current = manifest_from_discovery(record)
        previous = existing_by_id.get(record.record_id)
        if previous is not None:
            current = _restore_manifest_state(current, previous)
        merged.append(current)
        discovered_ids.add(record.record_id)

    for previous in existing:
        if previous.record_id in discovered_ids:
            continue
        merged.append(_clone_manifest_record(previous))

    return reconcile_manifest_records(merged, output_root=output_root)


def apply_download_results(
    records: list[ManifestRecord],
    results: list[DownloadResult],
) -> list[ManifestRecord]:
    results_by_id = {result.record_id: result for result in results}
    for record in records:
        result = results_by_id.get(record.record_id)
        if result is None:
            continue
        record.download_status = result.download_status
        record.http_status = result.http_status
        record.content_type = result.content_type
        record.content_length = result.content_length
        record.sha256 = result.sha256
        record.downloaded_at = result.downloaded_at
        record.error_message = result.error_message
    return records


def _cleanup_staging_file(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return


def _write_manifest_atomic(
    path: Path,
    *,
    newline: str | None,
    write_contents: Callable[[_WritableTextFile], None],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline=newline,
            dir=path.parent,
            prefix=f".{path.name}.tmp-",
            delete=False,
        ) as file_handle:
            staging_path = Path(file_handle.name)
            write_contents(file_handle)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(staging_path, path)
    except OSError as exc:
        _cleanup_staging_file(staging_path)
        raise ManifestPersistError(path=path, detail=str(exc)) from exc
    except Exception:
        _cleanup_staging_file(staging_path)
        raise


def write_manifest_csv(records: list[ManifestRecord], path: Path) -> None:
    def write_contents(file_handle: _WritableTextFile) -> None:
        writer = csv.DictWriter(file_handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.to_dict())

    _write_manifest_atomic(path, newline="", write_contents=write_contents)


def write_manifest_jsonl(records: list[ManifestRecord], path: Path) -> None:
    def write_contents(file_handle: _WritableTextFile) -> None:
        for record in records:
            file_handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
            file_handle.write("\n")

    _write_manifest_atomic(path, newline=None, write_contents=write_contents)
