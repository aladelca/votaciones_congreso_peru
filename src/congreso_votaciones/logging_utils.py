from __future__ import annotations

import json
from datetime import UTC, datetime

from congreso_votaciones.config import Settings


def log_event(settings: Settings, event: str, **payload: object) -> None:
    settings.log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": event,
        **payload,
    }
    with settings.log_path.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True))
        file_handle.write("\n")
