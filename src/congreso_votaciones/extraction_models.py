from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from congreso_votaciones.models import CommandSummary

PageProfileClass = Literal["native_text", "image_only", "hybrid", "blank_or_noise"]
DocumentProfileClass = Literal["native_text", "image_only", "hybrid", "blank_or_noise"]
SectionType = Literal["attendance", "vote", "summary", "other"]
ExtractionBackend = Literal["native_pdf", "google_document_ai", "hybrid", "unassigned"]
EvidenceBackend = Literal["native_pdf", "google_document_ai"]
ExtractionStatus = Literal["pending", "extracted", "failed"]
CandidateRowKind = Literal["attendance", "vote"]


@dataclass(slots=True, frozen=True)
class PdfPageProfile:
    page_number: int
    native_text_length: int
    native_word_count: int
    image_count: int
    profile_class: PageProfileClass

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class PdfDocumentProfile:
    record_id: str
    page_count: int
    profile_class: DocumentProfileClass
    pages: list[PdfPageProfile]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ExtractedTextBlock:
    block_id: str
    page_number: int
    text: str
    source_backend: EvidenceBackend
    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None

    def to_dict(self) -> dict[str, object | None]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    source_backend: EvidenceBackend
    section_type: SectionType = "other"
    block_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ProviderExtraction:
    provider_name: ExtractionBackend
    pages: list[ExtractedPage]
    blocks: list[ExtractedTextBlock]


@dataclass(slots=True, frozen=True)
class CandidateRow:
    row_id: str
    record_id: str
    kind: CandidateRowKind
    page_number: int
    raw_text: str
    legislator_name_raw: str
    party_raw: str | None
    value_raw: str
    normalized_value: str | None
    source_backend: EvidenceBackend
    confidence: float

    def to_dict(self) -> dict[str, object | None]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class DocumentExtraction:
    record_id: str
    profile: PdfDocumentProfile
    preferred_backend: ExtractionBackend
    pages: list[ExtractedPage]
    blocks: list[ExtractedTextBlock]
    candidate_rows: list[CandidateRow]

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "profile": self.profile.to_dict(),
            "preferred_backend": self.preferred_backend,
            "pages": [page.to_dict() for page in self.pages],
            "blocks": [block.to_dict() for block in self.blocks],
            "candidate_rows": [row.to_dict() for row in self.candidate_rows],
        }


@dataclass(slots=True)
class ParseManifestRecord:
    record_id: str
    storage_relpath: str
    session_date_iso: str
    document_type: str
    profile_class: DocumentProfileClass | None = None
    preferred_backend: ExtractionBackend = "unassigned"
    extraction_status: ExtractionStatus = "pending"
    page_count: int | None = None
    extracted_at: str | None = None
    attempt_count: int = 0
    error_message: str | None = None
    output_relpath: str | None = None

    def to_dict(self) -> dict[str, object | None]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ExtractionServiceResult:
    records: list[ParseManifestRecord]
    summary: CommandSummary
    extracted_documents: list[DocumentExtraction] = field(default_factory=list)
