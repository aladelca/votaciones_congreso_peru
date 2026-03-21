from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

DownloadStatus = Literal["pending", "downloaded", "failed"]


@dataclass(slots=True, frozen=True)
class PlenoPdfRecord:
    record_id: str
    source_page_url: str
    iframe_url: str
    expand_view_url: str
    periodo_parlamentario: str
    periodo_anual: str
    legislatura: str
    session_date_raw: str
    session_date_iso: str
    source_title: str
    document_type: str
    session_type: str
    is_provisional: bool
    is_official: bool
    pdf_relative_path: str
    pdf_url: str
    filename_original: str


@dataclass(slots=True)
class ManifestRecord:
    record_id: str
    source_page_url: str
    iframe_url: str
    expand_view_url: str
    periodo_parlamentario: str
    periodo_anual: str
    legislatura: str
    session_date_raw: str
    session_date_iso: str
    source_title: str
    document_type: str
    session_type: str
    is_provisional: bool
    is_official: bool
    pdf_relative_path: str
    pdf_url: str
    filename_original: str
    storage_relpath: str
    download_status: DownloadStatus = "pending"
    http_status: int | None = None
    content_type: str | None = None
    content_length: int | None = None
    sha256: str | None = None
    downloaded_at: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object | None]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class DownloadResult:
    record_id: str
    download_status: DownloadStatus
    http_status: int | None = None
    content_type: str | None = None
    content_length: int | None = None
    sha256: str | None = None
    downloaded_at: str | None = None
    error_message: str | None = None


@dataclass(slots=True, frozen=True)
class CommandSummary:
    command: str
    discovered: int = 0
    pending: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    manifest_csv_path: Path | None = None
    manifest_jsonl_path: Path | None = None
    exit_code: int = 0
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ServiceResult:
    records: list[ManifestRecord]
    summary: CommandSummary
