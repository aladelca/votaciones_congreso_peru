from __future__ import annotations

from congreso_votaciones.extraction_models import PdfPageProfile
from congreso_votaciones.pdf_profile import classify_document_profile, classify_page_profile


def test_classify_page_profile_marks_hybrid_when_text_and_images_exist() -> None:
    assert classify_page_profile(native_text_length=150, image_count=1) == "hybrid"


def test_classify_page_profile_marks_image_only_when_no_text_exists() -> None:
    assert classify_page_profile(native_text_length=0, image_count=2) == "image_only"


def test_classify_document_profile_returns_hybrid_for_mixed_pages() -> None:
    pages = [
        PdfPageProfile(
            page_number=1,
            native_text_length=200,
            native_word_count=30,
            image_count=0,
            profile_class="native_text",
        ),
        PdfPageProfile(
            page_number=2,
            native_text_length=0,
            native_word_count=0,
            image_count=1,
            profile_class="image_only",
        ),
    ]

    assert classify_document_profile(pages) == "hybrid"
