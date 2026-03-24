from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SOURCE_PAGE_URL = (
    "https://www.congreso.gob.pe/labor-legislativa/"
    "asistencias-votaciones-y-descuentos-por-inasistencias/"
    "asistencia-y-votaciones-a-las-sesiones-del-pleno/"
)


@dataclass(slots=True)
class Settings:
    project_root: Path
    output_root: Path
    source_page_url: str = DEFAULT_SOURCE_PAGE_URL
    html_timeout: float = 20.0
    pdf_timeout: float = 60.0
    retries: int = 3
    max_concurrency: int = 4
    user_agent: str = "congreso-votaciones/0.1 (+https://github.com/)"
    accept_header: str = "text/html,application/pdf,*/*"
    google_cloud_project: str | None = None
    google_cloud_location: str | None = None
    documentai_processor_id: str | None = None
    documentai_max_pages_per_request: int = 15

    @classmethod
    def from_root(
        cls,
        project_root: Path,
        *,
        output_root: Path | None = None,
        max_concurrency: int | None = None,
    ) -> Settings:
        resolved_root = project_root.resolve()
        resolved_output = (output_root or resolved_root / "data").resolve()
        return cls(
            project_root=resolved_root,
            output_root=resolved_output,
            max_concurrency=max_concurrency or 4,
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION"),
            documentai_processor_id=os.getenv("DOCUMENTAI_PROCESSOR_ID"),
            documentai_max_pages_per_request=int(
                os.getenv("DOCUMENTAI_MAX_PAGES_PER_REQUEST", "15")
            ),
        )

    @property
    def public_page_path(self) -> Path:
        return self.output_root / "raw" / "pleno" / "html" / "public_page.html"

    @property
    def expanded_view_path(self) -> Path:
        return self.output_root / "raw" / "pleno" / "html" / "expanded_view.html"

    @property
    def pdf_root(self) -> Path:
        return self.output_root / "raw" / "pleno" / "pdfs"

    @property
    def manifest_csv_path(self) -> Path:
        return self.output_root / "manifests" / "pleno_pdfs_index.csv"

    @property
    def manifest_jsonl_path(self) -> Path:
        return self.output_root / "manifests" / "pleno_pdfs_index.jsonl"

    @property
    def log_path(self) -> Path:
        return self.output_root / "logs" / "pleno_sync.log"

    @property
    def processed_pleno_root(self) -> Path:
        return self.output_root / "processed" / "pleno"

    @property
    def processed_intermediate_root(self) -> Path:
        return self.processed_pleno_root / "intermediate"

    @property
    def processed_parsed_root(self) -> Path:
        return self.processed_pleno_root / "parsed"

    @property
    def parse_manifest_jsonl_path(self) -> Path:
        return self.output_root / "manifests" / "pleno_parse_manifest.jsonl"

    @property
    def reference_pleno_root(self) -> Path:
        return self.output_root / "reference" / "pleno"

    @property
    def documentai_is_configured(self) -> bool:
        return all(
            (
                self.google_cloud_project,
                self.google_cloud_location,
                self.documentai_processor_id,
            )
        )

    @property
    def documentai_endpoint(self) -> str:
        if self.google_cloud_location is None:
            raise ValueError("GOOGLE_CLOUD_LOCATION no esta configurado.")
        return f"{self.google_cloud_location}-documentai.googleapis.com"

    def default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": self.accept_header,
        }

    def ensure_directories(self) -> None:
        for path in (
            self.public_page_path.parent,
            self.expanded_view_path.parent,
            self.pdf_root,
            self.processed_intermediate_root,
            self.processed_parsed_root,
            self.manifest_csv_path.parent,
            self.parse_manifest_jsonl_path.parent,
            self.log_path.parent,
            self.reference_pleno_root,
        ):
            path.mkdir(parents=True, exist_ok=True)
