from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from congreso_votaciones import cli
from congreso_votaciones.manifest import ManifestLoadError
from congreso_votaciones.models import CommandSummary, ServiceResult

runner = CliRunner()


def test_discover_cli_invokes_service(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def fake_discover(settings, *, limit, refresh_html):  # type: ignore[no-untyped-def]
        captured["output_root"] = settings.output_root
        captured["limit"] = limit
        captured["refresh_html"] = refresh_html
        return ServiceResult(
            records=[],
            summary=CommandSummary(
                command="discover-pleno",
                discovered=3,
                manifest_csv_path=Path("data/manifests/pleno_pdfs_index.csv"),
                manifest_jsonl_path=Path("data/manifests/pleno_pdfs_index.jsonl"),
            ),
        )

    monkeypatch.setattr(cli, "discover_pleno", fake_discover)
    result = runner.invoke(
        cli.app,
        [
            "discover-pleno",
            "--output-root",
            str(tmp_path / "data"),
            "--limit",
            "3",
            "--refresh-html",
        ],
    )

    assert result.exit_code == 0
    assert captured["limit"] == 3
    assert captured["refresh_html"] is True
    assert "command: discover-pleno" in result.stdout


def test_download_cli_returns_configuration_error(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    def fake_download(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise FileNotFoundError("missing manifest")

    monkeypatch.setattr(cli, "download_pleno", fake_download)
    result = runner.invoke(cli.app, ["download-pleno", "--output-root", str(tmp_path / "data")])

    assert result.exit_code == 2
    assert "configuration-error:" in result.stderr


def test_download_cli_surfaces_manifest_load_error(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    def fake_download(*args, **kwargs):  # type: ignore[no-untyped-def]
        del args, kwargs
        raise ManifestLoadError(
            path=tmp_path / "data" / "manifests" / "pleno_pdfs_index.jsonl",
            detail="payload invalido para ManifestRecord",
            line_number=3,
        )

    monkeypatch.setattr(cli, "download_pleno", fake_download)
    result = runner.invoke(cli.app, ["download-pleno", "--output-root", str(tmp_path / "data")])

    assert result.exit_code == 1
    assert "error: Manifiesto JSONL invalido" in result.stderr
    assert "manifiesto canonico" in result.stderr


def test_sync_cli_propagates_service_exit_code(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    def fake_sync(settings, *, limit, retry_failed, max_concurrency, refresh_html):  # type: ignore[no-untyped-def]
        del settings, limit, retry_failed, max_concurrency, refresh_html
        return ServiceResult(
            records=[],
            summary=CommandSummary(command="sync-pleno", downloaded=1, failed=1, exit_code=1),
        )

    monkeypatch.setattr(cli, "sync_pleno", fake_sync)
    result = runner.invoke(cli.app, ["sync-pleno", "--output-root", str(tmp_path / "data")])

    assert result.exit_code == 1
    assert "command: sync-pleno" in result.stdout
