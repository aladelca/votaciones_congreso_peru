from __future__ import annotations

from pathlib import Path
from typing import Any

import pymupdf

from congreso_votaciones.extraction_models import (
    DocumentProfileClass,
    PageProfileClass,
    PdfDocumentProfile,
    PdfPageProfile,
)


def classify_page_profile(
    *,
    native_text_length: int,
    image_count: int,
) -> PageProfileClass:
    if native_text_length > 0 and image_count > 0:
        return "hybrid"
    if native_text_length > 0:
        return "native_text"
    if image_count > 0:
        return "image_only"
    return "blank_or_noise"


def classify_document_profile(page_profiles: list[PdfPageProfile]) -> DocumentProfileClass:
    page_classes = {page.profile_class for page in page_profiles}
    if not page_classes:
        return "blank_or_noise"
    if page_classes == {"native_text"}:
        return "native_text"
    if page_classes.issubset({"image_only", "blank_or_noise"}):
        return "image_only"
    if page_classes == {"blank_or_noise"}:
        return "blank_or_noise"
    return "hybrid"


def profile_pdf(pdf_path: Path, *, record_id: str) -> PdfDocumentProfile:
    document: Any = pymupdf.open(pdf_path)  # type: ignore[no-untyped-call]
    page_profiles: list[PdfPageProfile] = []

    try:
        for page_index in range(int(document.page_count)):
            page: Any = document.load_page(page_index)
            text = page.get_text("text").strip()
            words = page.get_text("words")
            image_count = len(page.get_images(full=True))
            page_profiles.append(
                PdfPageProfile(
                    page_number=page_index + 1,
                    native_text_length=len(text),
                    native_word_count=len(words),
                    image_count=image_count,
                    profile_class=classify_page_profile(
                        native_text_length=len(text),
                        image_count=image_count,
                    ),
                )
            )
    finally:
        document.close()

    return PdfDocumentProfile(
        record_id=record_id,
        page_count=len(page_profiles),
        profile_class=classify_document_profile(page_profiles),
        pages=page_profiles,
    )
