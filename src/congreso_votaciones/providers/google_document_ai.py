from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf

from congreso_votaciones.config import Settings
from congreso_votaciones.extraction_models import (
    ExtractedPage,
    ExtractedTextBlock,
    ProviderExtraction,
)
from congreso_votaciones.parse_index import normalize_space

GoogleClientOptions: Any | None
documentai_module: Any | None

try:
    from google.api_core.client_options import ClientOptions as GoogleClientOptions
    from google.cloud import documentai_v1 as documentai_module
except ImportError:  # pragma: no cover - exercised indirectly in runtime environments
    GoogleClientOptions = None
    documentai_module = None


def _require_documentai() -> tuple[Any, Any]:
    if GoogleClientOptions is None or documentai_module is None:
        raise ImportError(
            "google-cloud-documentai no esta instalado. "
            "Ejecuta `uv sync` antes de usar extract-pleno."
        )
    return GoogleClientOptions, documentai_module


def _get_text_from_anchor(layout: Any, document_text: str) -> str:
    text_anchor = getattr(layout, "text_anchor", None)
    if text_anchor is None or not text_anchor.text_segments:
        return ""

    parts: list[str] = []
    for segment in text_anchor.text_segments:
        start = int(segment.start_index or 0)
        end = int(segment.end_index)
        parts.append(document_text[start:end])
    return normalize_space("".join(parts))


def _extract_bbox(layout: Any) -> tuple[float | None, float | None, float | None, float | None]:
    bounding_poly = getattr(layout, "bounding_poly", None)
    if bounding_poly is None:
        return None, None, None, None

    vertices = list(getattr(bounding_poly, "normalized_vertices", [])) or list(
        getattr(bounding_poly, "vertices", [])
    )
    if not vertices:
        return None, None, None, None

    xs = [float(vertex.x) for vertex in vertices]
    ys = [float(vertex.y) for vertex in vertices]
    return min(xs), min(ys), max(xs), max(ys)


def _iter_pdf_chunks(pdf_path: Path, *, max_pages: int) -> list[tuple[int, bytes]]:
    if max_pages < 1:
        raise ValueError("DOCUMENTAI_MAX_PAGES_PER_REQUEST debe ser mayor que cero.")

    document: Any = pymupdf.open(pdf_path)  # type: ignore[no-untyped-call]
    chunks: list[tuple[int, bytes]] = []
    try:
        page_count = int(document.page_count)
        for start_index in range(0, page_count, max_pages):
            end_index = min(page_count, start_index + max_pages)
            chunk_document: Any = pymupdf.open()  # type: ignore[no-untyped-call]
            try:
                chunk_document.insert_pdf(
                    document,
                    from_page=start_index,
                    to_page=end_index - 1,
                )
                chunks.append((start_index, chunk_document.tobytes()))
            finally:
                chunk_document.close()
    finally:
        document.close()
    return chunks


def extract_text_with_google_document_ai(
    settings: Settings,
    pdf_path: Path,
    *,
    record_id: str,
) -> ProviderExtraction:
    if not settings.documentai_is_configured:
        raise ValueError(
            "Document AI no esta configurado. Define GOOGLE_CLOUD_PROJECT, "
            "GOOGLE_CLOUD_LOCATION y DOCUMENTAI_PROCESSOR_ID."
        )

    client_options_cls, documentai_module = _require_documentai()
    client = documentai_module.DocumentProcessorServiceClient(
        client_options=client_options_cls(api_endpoint=settings.documentai_endpoint)
    )
    processor_name = client.processor_path(
        settings.google_cloud_project,
        settings.google_cloud_location,
        settings.documentai_processor_id,
    )
    pages: list[ExtractedPage] = []
    blocks: list[ExtractedTextBlock] = []
    for page_offset, pdf_bytes in _iter_pdf_chunks(
        pdf_path,
        max_pages=settings.documentai_max_pages_per_request,
    ):
        raw_document = documentai_module.RawDocument(
            content=pdf_bytes,
            mime_type="application/pdf",
        )
        request = documentai_module.ProcessRequest(name=processor_name, raw_document=raw_document)
        result = client.process_document(request=request)
        document = result.document

        for page_index, page in enumerate(document.pages, start=1):
            page_number = page_offset + page_index
            page_text = _get_text_from_anchor(page.layout, document.text)
            line_count = 0
            for line_index, line in enumerate(page.lines, start=1):
                line_text = _get_text_from_anchor(line.layout, document.text)
                if not line_text:
                    continue
                line_count += 1
                x0, y0, x1, y1 = _extract_bbox(line.layout)
                blocks.append(
                    ExtractedTextBlock(
                        block_id=f"{record_id}-gdoc-{page_number}-{line_index}",
                        page_number=page_number,
                        text=line_text,
                        source_backend="google_document_ai",
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                    )
                )

            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=page_text,
                    source_backend="google_document_ai",
                    block_count=line_count,
                )
            )

    return ProviderExtraction(provider_name="google_document_ai", pages=pages, blocks=blocks)
