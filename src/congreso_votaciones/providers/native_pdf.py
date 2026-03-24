from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf

from congreso_votaciones.extraction_models import (
    ExtractedPage,
    ExtractedTextBlock,
    ProviderExtraction,
)
from congreso_votaciones.parse_index import normalize_space


def extract_text_with_native_pdf(pdf_path: Path, *, record_id: str) -> ProviderExtraction:
    document: Any = pymupdf.open(pdf_path)  # type: ignore[no-untyped-call]
    pages: list[ExtractedPage] = []
    blocks: list[ExtractedTextBlock] = []

    try:
        for page_index in range(int(document.page_count)):
            page: Any = document.load_page(page_index)
            text = page.get_text("text")
            normalized_text = normalize_space(text)
            line_count = 0
            for line_index, raw_line in enumerate(text.splitlines(), start=1):
                line_text = normalize_space(raw_line)
                if not line_text:
                    continue
                line_count += 1
                blocks.append(
                    ExtractedTextBlock(
                        block_id=f"{record_id}-native-{page_index}-{line_index}",
                        page_number=page_index,
                        text=line_text,
                        source_backend="native_pdf",
                    )
                )

            pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text=normalized_text,
                    source_backend="native_pdf",
                    block_count=line_count,
                )
            )
    finally:
        document.close()

    return ProviderExtraction(provider_name="native_pdf", pages=pages, blocks=blocks)
