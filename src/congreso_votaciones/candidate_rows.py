from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from congreso_votaciones.extraction_models import (
    CandidateRow,
    CandidateRowKind,
    EvidenceBackend,
    ExtractedPage,
    ExtractedTextBlock,
)
from congreso_votaciones.parse_index import normalize_space

ATTENDANCE_VALUES = {
    "PRE": "presente",
    "AUS": "ausente",
    "LIC": "licencia",
    "LE": "licencia",
    "CO": "comision_oficial",
    "COM": "comision_oficial",
    "SUS": "suspendido",
    "F": "fallecido",
}
VOTE_VALUES = {
    "SI +++": "si",
    "SI+++": "si",
    "SI": "si",
    "SÍ +++": "si",
    "SÍ+++": "si",
    "SÍ": "si",
    "NO ---": "no",
    "NO---": "no",
    "NO": "no",
    "SINRES": "sin_respuesta",
    "SIN RES": "sin_respuesta",
    "ABS": "abstencion",
    "ABS.": "abstencion",
    "ABST": "abstencion",
    "ABST.": "abstencion",
    "AUS": "ausente",
    "LO": "licencia_oficial",
    "LIC": "licencia",
    "LE": "licencia_enfermedad",
    "LP": "licencia_personal",
    "L25A": "licencia_sin_goce",
    "PRE": "preside",
}
PARTY_TOKEN_RE = re.compile(r"^[A-Z0-9\-]{1,8}$")
KNOWN_PARTY_CODES = {
    "APP",
    "FP",
    "PP",
    "PL",
    "RP",
    "JPP-VP",
    "SP",
    "AP",
    "AP-PIS",
    "BS",
    "HYD",
    "BDP",
    "NA",
}
ROW_BAND_Y_GAP = 0.0065
NOISE_MARKERS = (
    "congreso de la república",
    "sesión del",
    "asistencia:",
    "votación:",
    "votacion:",
    "fecha:",
    "hora:",
    "grupo parlamentario",
    "resultados de",
    "quórum",
    "quorum",
    "presentes",
    "ausentes",
    "con licencia",
    "suspendidos",
    "fallecidos",
    "copia informativa",
    "información provisional",
    "informacion provisional",
    "sin los votos orales",
    "*** presidente",
    "asunto:",
)
TokenType = Literal["party", "name", "value"]
ATTENDANCE_VALUE_PATTERNS = [
    (re.compile(r"^(L25A)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_sin_goce"),
    (re.compile(r"^(PRE)(?:\s+|$)(.*)$", re.IGNORECASE), "presente"),
    (re.compile(r"^(AUS)(?:\s+|$)(.*)$", re.IGNORECASE), "ausente"),
    (re.compile(r"^(LO)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_oficial"),
    (re.compile(r"^(LE)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_enfermedad"),
    (re.compile(r"^(LP)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_personal"),
    (re.compile(r"^(CO|COM)(?:\s+|$)(.*)$", re.IGNORECASE), "comision_oficial"),
    (re.compile(r"^(SUS)(?:\s+|$)(.*)$", re.IGNORECASE), "suspendido"),
    (re.compile(r"^(F)(?:\s+|$)(.*)$", re.IGNORECASE), "fallecido"),
]
VOTE_VALUE_PATTERNS = [
    (re.compile(r"^(S[IÍ]\s*\+\+\+)(?:\s+|$)(.*)$", re.IGNORECASE), "si"),
    (re.compile(r"^(NO\s*---)(?:\s+|$)(.*)$", re.IGNORECASE), "no"),
    (re.compile(r"^(SIN\s*RES)(?:\s+|$)(.*)$", re.IGNORECASE), "sin_respuesta"),
    (re.compile(r"^(ABST\.?|ABS\.?)(?:\s+|$)(.*)$", re.IGNORECASE), "abstencion"),
    (re.compile(r"^(AUS)(?:\s+|$)(.*)$", re.IGNORECASE), "ausente"),
    (re.compile(r"^(LO)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_oficial"),
    (re.compile(r"^(LE)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_enfermedad"),
    (re.compile(r"^(LP)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_personal"),
    (re.compile(r"^(L25A)(?:\s+|$)(.*)$", re.IGNORECASE), "licencia_sin_goce"),
    (re.compile(r"^(PRE)(?:\s+|$)(.*)$", re.IGNORECASE), "preside"),
    (re.compile(r"^(S[IÍ])(?:\s+|$)(.*)$", re.IGNORECASE), "si"),
    (re.compile(r"^(NO)(?:\s+|$)(.*)$", re.IGNORECASE), "no"),
]


@dataclass(slots=True, frozen=True)
class RowToken:
    token_type: TokenType
    raw_text: str
    normalized_value: str | None = None


def _candidate_row_id(record_id: str, kind: str, page_number: int, raw_text: str) -> str:
    payload = f"{record_id}|{kind}|{page_number}|{raw_text}".encode()
    digest = hashlib.sha1(payload).hexdigest()
    return digest[:16]


def _consume_leading_value(
    text: str,
    *,
    kind: CandidateRowKind,
) -> tuple[str, str, str] | None:
    patterns = ATTENDANCE_VALUE_PATTERNS if kind == "attendance" else VOTE_VALUE_PATTERNS
    for pattern, normalized_value in patterns:
        match = pattern.match(text)
        if match is None:
            continue
        raw_value = normalize_space(match.group(1))
        remainder = normalize_space(match.group(2))
        return raw_value, normalized_value, remainder
    return None


def _split_party_and_name(text: str) -> tuple[str, str] | None:
    parts = text.split(maxsplit=1)
    if not parts:
        return None
    party_raw = parts[0].upper()
    if not PARTY_TOKEN_RE.match(party_raw) or party_raw not in KNOWN_PARTY_CODES:
        return None
    remainder = normalize_space(parts[1]) if len(parts) > 1 else ""
    return party_raw, remainder


def _tokenize_positioned_block(text: str, *, kind: CandidateRowKind) -> list[RowToken]:
    normalized_text = normalize_space(text)
    if not normalized_text:
        return []

    tokens: list[RowToken] = []
    remaining = normalized_text
    leading_value = _consume_leading_value(remaining, kind=kind)
    if leading_value is not None:
        raw_value, normalized_value, remaining = leading_value
        tokens.append(
            RowToken(
                token_type="value",
                raw_text=raw_value,
                normalized_value=normalized_value,
            )
        )
        if not remaining:
            return tokens

    party_and_name = _split_party_and_name(remaining)
    if party_and_name is not None:
        party_raw, remainder = party_and_name
        tokens.append(RowToken(token_type="party", raw_text=party_raw))
        if remainder:
            tokens.append(RowToken(token_type="name", raw_text=remainder))
        return tokens

    tokens.append(RowToken(token_type="name", raw_text=remaining))
    return tokens


def _extract_row_parts(
    text: str,
    *,
    value_map: dict[str, str],
) -> tuple[str | None, str | None, str | None, str | None]:
    tokens = text.split()
    if len(tokens) < 3:
        return None, None, None, None

    value_index = -1
    normalized_value: str | None = None
    raw_value: str | None = None
    lower_bound = max(0, len(tokens) - 3)
    for index in range(len(tokens) - 1, lower_bound - 1, -1):
        token = tokens[index].upper().rstrip(".*-")
        if token in value_map:
            value_index = index
            raw_value = tokens[index]
            normalized_value = value_map[token]
            break

    if value_index < 0 or raw_value is None:
        return None, None, None, None

    party_raw: str | None = None
    name_start_index = 0
    leading_token = tokens[0].upper()
    if PARTY_TOKEN_RE.match(leading_token) and leading_token in KNOWN_PARTY_CODES:
        party_raw = tokens[0]
        name_start_index = 1

    name_tokens = tokens[name_start_index:value_index]
    if not name_tokens:
        return None, None, None, None

    legislator_name = normalize_space(" ".join(name_tokens))
    if len(legislator_name) < 5:
        return None, None, None, None

    return party_raw, legislator_name, raw_value, normalized_value


def _is_positioned_block(block: ExtractedTextBlock) -> bool:
    return block.x0 is not None and block.y0 is not None


def _group_blocks_by_row(page_blocks: list[ExtractedTextBlock]) -> list[list[ExtractedTextBlock]]:
    ordered_blocks = sorted(
        page_blocks,
        key=lambda item: (
            ((item.y0 or 0.0) + (item.y1 or item.y0 or 0.0)) / 2,
            item.x0 or 0.0,
        ),
    )
    grouped: list[list[ExtractedTextBlock]] = []
    row_centers: list[float] = []
    for block in ordered_blocks:
        y_center = ((block.y0 or 0.0) + (block.y1 or block.y0 or 0.0)) / 2
        if not grouped or abs(y_center - row_centers[-1]) > ROW_BAND_Y_GAP:
            grouped.append([block])
            row_centers.append(y_center)
            continue
        grouped[-1].append(block)
        row_centers[-1] = (row_centers[-1] + y_center) / 2
    return grouped


def _is_noise_row(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in NOISE_MARKERS)


def _build_candidate_row(
    record_id: str,
    *,
    kind: CandidateRowKind,
    page_number: int,
    party_raw: str | None,
    legislator_name: str,
    raw_value: str,
    normalized_value: str,
    source_backend: EvidenceBackend,
    confidence: float,
) -> CandidateRow | None:
    normalized_name = normalize_space(legislator_name)
    if len(normalized_name) < 5:
        return None
    if _is_noise_row(normalized_name):
        return None

    raw_text = normalize_space(
        " ".join(part for part in (party_raw, normalized_name, raw_value) if part)
    )
    return CandidateRow(
        row_id=_candidate_row_id(record_id, kind, page_number, raw_text),
        record_id=record_id,
        kind=kind,
        page_number=page_number,
        raw_text=raw_text,
        legislator_name_raw=normalized_name,
        party_raw=party_raw,
        value_raw=raw_value,
        normalized_value=normalized_value,
        source_backend=source_backend,
        confidence=confidence,
    )


def _extract_positioned_candidate_rows(
    record_id: str,
    *,
    kind: CandidateRowKind,
    page_number: int,
    page_blocks: list[ExtractedTextBlock],
) -> list[CandidateRow]:
    candidate_rows: list[CandidateRow] = []
    for row_blocks in _group_blocks_by_row(page_blocks):
        ordered_blocks = sorted(row_blocks, key=lambda item: (item.x0 or 0.0, item.text))
        row_text = normalize_space(" ".join(block.text for block in ordered_blocks))
        if _is_noise_row(row_text):
            continue

        row_tokens: list[RowToken] = []
        for block in ordered_blocks:
            row_tokens.extend(_tokenize_positioned_block(block.text, kind=kind))

        if not any(token.token_type == "value" for token in row_tokens):
            continue

        current_party: str | None = None
        current_name_parts: list[str] = []
        for token in row_tokens:
            if token.token_type == "party":
                if current_name_parts:
                    current_party = token.raw_text
                    current_name_parts = []
                    continue
                current_party = token.raw_text
                continue
            if token.token_type == "name":
                current_name_parts.append(token.raw_text)
                continue

            if not current_name_parts or token.normalized_value is None:
                continue
            candidate_row = _build_candidate_row(
                record_id,
                kind=kind,
                page_number=page_number,
                party_raw=current_party,
                legislator_name=" ".join(current_name_parts),
                raw_value=token.raw_text,
                normalized_value=token.normalized_value,
                source_backend=ordered_blocks[0].source_backend,
                confidence=0.9 if current_party is not None else 0.8,
            )
            if candidate_row is not None:
                candidate_rows.append(candidate_row)
            current_party = None
            current_name_parts = []
    return candidate_rows


def _extract_line_candidate_rows(
    record_id: str,
    *,
    kind: CandidateRowKind,
    page_number: int,
    page_blocks: list[ExtractedTextBlock],
) -> list[CandidateRow]:
    value_map = ATTENDANCE_VALUES if kind == "attendance" else VOTE_VALUES
    extracted: list[CandidateRow] = []
    for block in sorted(
        page_blocks, key=lambda item: (item.y0 or 0.0, item.x0 or 0.0, item.text)
    ):
        raw_text = normalize_space(block.text)
        if not raw_text or raw_text.startswith("***"):
            continue
        if _is_noise_row(raw_text):
            continue

        party_raw, legislator_name, raw_value, normalized_value = _extract_row_parts(
            raw_text,
            value_map=value_map,
        )
        if legislator_name is None or normalized_value is None or raw_value is None:
            continue

        candidate_row = _build_candidate_row(
            record_id,
            kind=kind,
            page_number=page_number,
            party_raw=party_raw,
            legislator_name=legislator_name,
            raw_value=raw_value,
            normalized_value=normalized_value,
            source_backend=block.source_backend,
            confidence=0.7 if party_raw is not None else 0.5,
        )
        if candidate_row is not None:
            extracted.append(candidate_row)
    return extracted


def extract_candidate_rows(
    record_id: str,
    pages: list[ExtractedPage],
    blocks: list[ExtractedTextBlock],
) -> list[CandidateRow]:
    pages_by_number = {page.page_number: page for page in pages}
    blocks_by_page: dict[int, list[ExtractedTextBlock]] = defaultdict(list)
    for block in blocks:
        blocks_by_page[block.page_number].append(block)

    extracted: list[CandidateRow] = []
    for page_number, page_blocks in blocks_by_page.items():
        page = pages_by_number.get(page_number)
        if page is None or page.section_type not in {"attendance", "vote"}:
            continue

        kind: CandidateRowKind = (
            "attendance" if page.section_type == "attendance" else "vote"
        )
        if page_blocks and all(_is_positioned_block(block) for block in page_blocks):
            positioned_rows = _extract_positioned_candidate_rows(
                record_id,
                kind=kind,
                page_number=page_number,
                page_blocks=page_blocks,
            )
            if positioned_rows:
                extracted.extend(positioned_rows)
                continue

        extracted.extend(
            _extract_line_candidate_rows(
                record_id,
                kind=kind,
                page_number=page_number,
                page_blocks=page_blocks,
            )
        )

    deduped: dict[str, CandidateRow] = {}
    for row in extracted:
        deduped[row.row_id] = row
    return list(deduped.values())
