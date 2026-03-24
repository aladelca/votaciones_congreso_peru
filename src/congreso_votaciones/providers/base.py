from __future__ import annotations

from pathlib import Path
from typing import Protocol

from congreso_votaciones.extraction_models import ProviderExtraction


class DocumentTextProvider(Protocol):
    def extract(self, pdf_path: Path, *, record_id: str) -> ProviderExtraction: ...
