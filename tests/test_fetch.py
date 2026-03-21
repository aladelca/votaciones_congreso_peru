from __future__ import annotations

import pytest

from congreso_votaciones.fetch import build_expand_view_url, extract_iframe_url


def test_extract_iframe_url(pleno_public_page_html: str) -> None:
    iframe_url = extract_iframe_url(
        pleno_public_page_html,
        "https://www.congreso.gob.pe/labor-legislativa/asistencias-votaciones-y-descuentos-por-inasistencias/asistencia-y-votaciones-a-las-sesiones-del-pleno/",
    )
    assert iframe_url.endswith(".nsf/new_asistenciavotacion")


def test_build_expand_view_url() -> None:
    iframe_url = "https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion"
    assert build_expand_view_url(iframe_url) == f"{iframe_url}?OpenForm&ExpandView&Seq=1"


def test_extract_iframe_url_raises_without_iframe() -> None:
    with pytest.raises(ValueError):
        extract_iframe_url("<html><body>sin iframe</body></html>", "https://example.com")
