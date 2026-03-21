from __future__ import annotations

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
            self.manifest_csv_path.parent,
            self.log_path.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)
