from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from congreso_votaciones.config import Settings
from congreso_votaciones.extraction_models import CandidateRow, DocumentExtraction
from congreso_votaciones.models import ManifestRecord


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_path: Path | None = None
    try:
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp-",
            delete=False,
        ) as file_handle:
            staging_path = Path(file_handle.name)
            file_handle.write(content)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(staging_path, path)
    finally:
        if staging_path is not None and staging_path.exists():
            staging_path.unlink(missing_ok=True)


def _document_output_dir(settings: Settings, record_id: str) -> Path:
    return settings.processed_intermediate_root / record_id


def persist_document_artifacts(
    settings: Settings,
    record: ManifestRecord,
    extraction: DocumentExtraction,
) -> Path:
    output_dir = _document_output_dir(settings, record.record_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = output_dir / "profile.json"
    pages_path = output_dir / "pages.jsonl"
    blocks_path = output_dir / "blocks.jsonl"
    candidates_path = output_dir / "candidate_rows.jsonl"
    summary_path = output_dir / "summary.json"

    _write_atomic(
        profile_path,
        json.dumps(extraction.profile.to_dict(), ensure_ascii=False, indent=2),
    )
    _write_atomic(
        pages_path,
        "".join(f"{json.dumps(page.to_dict(), ensure_ascii=False)}\n" for page in extraction.pages),
    )
    _write_atomic(
        blocks_path,
        "".join(
            f"{json.dumps(block.to_dict(), ensure_ascii=False)}\n" for block in extraction.blocks
        ),
    )
    _write_atomic(
        candidates_path,
        "".join(
            f"{json.dumps(candidate.to_dict(), ensure_ascii=False)}\n"
            for candidate in extraction.candidate_rows
        ),
    )
    summary_payload = {
        "record_id": record.record_id,
        "storage_relpath": record.storage_relpath,
        "profile_class": extraction.profile.profile_class,
        "preferred_backend": extraction.preferred_backend,
        "page_count": extraction.profile.page_count,
        "attendance_pages": sum(
            1
            for page in extraction.pages
            if page.section_type == "attendance"
        ),
        "vote_pages": sum(1 for page in extraction.pages if page.section_type == "vote"),
        "candidate_row_count": len(extraction.candidate_rows),
    }
    _write_atomic(summary_path, json.dumps(summary_payload, ensure_ascii=False, indent=2))
    return output_dir.relative_to(settings.output_root)


def summarize_candidate_rows(candidate_rows: list[CandidateRow]) -> dict[str, int]:
    summary = {"attendance": 0, "vote": 0}
    for row in candidate_rows:
        summary[row.kind] += 1
    return summary
