from __future__ import annotations

from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from congreso_votaciones.config import Settings


def build_client(settings: Settings) -> httpx.Client:
    return httpx.Client(
        headers=settings.default_headers(),
        follow_redirects=True,
        timeout=settings.html_timeout,
    )


def fetch_public_page(client: httpx.Client, source_page_url: str) -> str:
    response = client.get(source_page_url)
    response.raise_for_status()
    return response.text


def extract_iframe_url(html: str, source_page_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.find("iframe")
    if iframe is None:
        raise ValueError("No se encontro iframe en la pagina publica del Pleno.")
    src = iframe.get("src")
    if not isinstance(src, str) or not src.strip():
        raise ValueError("El iframe no contiene un src valido.")
    return urljoin(source_page_url, src.strip())


def build_expand_view_url(iframe_url: str) -> str:
    base_url = iframe_url.split("?", maxsplit=1)[0]
    return f"{base_url}?OpenForm&ExpandView&Seq=1"


def fetch_expand_view_html(client: httpx.Client, expand_view_url: str) -> str:
    response = client.get(expand_view_url)
    response.raise_for_status()
    return response.text


def ensure_contains_documents(expanded_html: str) -> None:
    if "openWindow(" not in expanded_html:
        raise ValueError("La vista expandida no contiene enlaces a documentos PDF.")


def save_html_snapshot(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def nsf_base_url(iframe_url: str) -> str:
    marker = ".nsf"
    lower_url = iframe_url.lower()
    index = lower_url.find(marker)
    if index == -1:
        raise ValueError(f"No se pudo resolver la base NSF desde {iframe_url!r}.")
    return f"{iframe_url[: index + len(marker)]}/"


def resolve_pdf_url(iframe_url: str, pdf_relative_path: str) -> str:
    return urljoin(nsf_base_url(iframe_url), pdf_relative_path)


def download_pdf_bytes(
    client: httpx.Client,
    pdf_url: str,
    *,
    timeout: float,
) -> tuple[bytes, int, str | None]:
    response = client.get(pdf_url, timeout=timeout)
    response.raise_for_status()
    return response.content, response.status_code, response.headers.get("content-type")
