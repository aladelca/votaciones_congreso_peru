from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from congreso_votaciones.extraction_models import ParseManifestRecord
from congreso_votaciones.models import ManifestRecord


def build_parse_manifest_record(record: ManifestRecord) -> ParseManifestRecord:
    return ParseManifestRecord(
        record_id=record.record_id,
        storage_relpath=record.storage_relpath,
        session_date_iso=record.session_date_iso,
        document_type=record.document_type,
    )


def load_parse_manifest(path: Path) -> list[ParseManifestRecord]:
    if not path.exists():
        return []

    records: list[ParseManifestRecord] = []
    with path.open(encoding="utf-8") as file_handle:
        for line in file_handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            records.append(ParseManifestRecord(**payload))
    return records


def merge_parse_manifest(
    existing: list[ParseManifestRecord],
    updates: list[ParseManifestRecord],
) -> list[ParseManifestRecord]:
    merged = {record.record_id: record for record in existing}
    for record in updates:
        merged[record.record_id] = record
    return list(merged.values())


def write_parse_manifest(path: Path, records: list[ParseManifestRecord]) -> None:
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
            for record in records:
                file_handle.write(json.dumps(record.to_dict(), ensure_ascii=False))
                file_handle.write("\n")
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(staging_path, path)
    finally:
        if staging_path is not None and staging_path.exists():
            staging_path.unlink(missing_ok=True)
