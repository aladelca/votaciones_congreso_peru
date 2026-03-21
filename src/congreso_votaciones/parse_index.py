from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime

from bs4 import BeautifulSoup

from congreso_votaciones.fetch import resolve_pdf_url
from congreso_votaciones.models import PlenoPdfRecord

OPEN_WINDOW_RE = re.compile(r"openWindow\('([^']+\.pdf)'\)", re.IGNORECASE)
DATE_RE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def build_record_id(pdf_relative_path: str) -> str:
    digest = hashlib.sha1(pdf_relative_path.lower().encode("utf-8")).hexdigest()
    return digest[:16]


def normalize_date(date_raw: str) -> str:
    return datetime.strptime(date_raw, "%m/%d/%Y").date().isoformat()


def classify_document_type(title: str) -> str:
    folded = ascii_fold(title)
    if "votacion" in folded or "votaciones" in folded:
        return "asistencia_y_votaciones"
    return "asistencia"


def classify_session_type(title: str) -> str:
    folded = ascii_fold(title)
    if "extraordinaria" in folded:
        return "extraordinaria"
    if "solemne" in folded:
        return "solemne"
    if "vespertina" in folded or "nocturna" in folded:
        return "vespertina"
    return "ordinaria"


def is_provisional(title: str, filename_original: str) -> bool:
    folded = f"{ascii_fold(title)} {ascii_fold(filename_original)}"
    return "provisional" in folded


def is_official(title: str, filename_original: str) -> bool:
    folded = f"{ascii_fold(title)} {ascii_fold(filename_original)}"
    return "oficial" in folded


def _extract_title(tr: object) -> str:
    if not hasattr(tr, "find_all"):
        return ""
    links = tr.find_all("a")
    texts = [normalize_space(link.get_text(" ", strip=True)) for link in links]
    texts = [text for text in texts if text]
    if texts:
        return max(texts, key=len)
    return ""


def parse_pleno_index(
    expanded_html: str,
    *,
    source_page_url: str,
    iframe_url: str,
    expand_view_url: str,
    limit: int | None = None,
) -> list[PlenoPdfRecord]:
    soup = BeautifulSoup(expanded_html, "html.parser")
    periodo_parlamentario = ""
    periodo_anual = ""
    legislatura = ""
    records: list[PlenoPdfRecord] = []

    for tr in soup.find_all("tr"):
        if tr.find("tr") is not None:
            continue
        row_html = str(tr)
        row_text = normalize_space(tr.get_text(" ", strip=True))
        if not row_text:
            continue

        folded = ascii_fold(row_text)
        if "periodo parlamentario" in folded:
            periodo_parlamentario = row_text
            periodo_anual = ""
            legislatura = ""
            continue
        if "periodo anual de sesiones" in folded:
            periodo_anual = row_text
            legislatura = ""
            continue
        if "legislatura" in folded:
            legislatura = row_text
            continue

        match = OPEN_WINDOW_RE.search(row_html)
        if match is None:
            continue

        date_match = DATE_RE.search(row_text)
        if date_match is None:
            continue

        pdf_relative_path = html.unescape(match.group(1))
        filename_original = pdf_relative_path.rsplit("/", maxsplit=1)[-1]
        title = _extract_title(tr) or row_text
        session_date_raw = date_match.group(0)

        record = PlenoPdfRecord(
            record_id=build_record_id(pdf_relative_path),
            source_page_url=source_page_url,
            iframe_url=iframe_url,
            expand_view_url=expand_view_url,
            periodo_parlamentario=periodo_parlamentario,
            periodo_anual=periodo_anual,
            legislatura=legislatura,
            session_date_raw=session_date_raw,
            session_date_iso=normalize_date(session_date_raw),
            source_title=title,
            document_type=classify_document_type(title),
            session_type=classify_session_type(title),
            is_provisional=is_provisional(title, filename_original),
            is_official=is_official(title, filename_original),
            pdf_relative_path=pdf_relative_path,
            pdf_url=resolve_pdf_url(iframe_url, pdf_relative_path),
            filename_original=filename_original,
        )
        records.append(record)
        if limit is not None and len(records) >= limit:
            break

    return records
