from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from congreso_votaciones.config import Settings
from congreso_votaciones.manifest import ManifestLoadError
from congreso_votaciones.models import CommandSummary
from congreso_votaciones.services import discover_pleno, download_pleno, sync_pleno

app = typer.Typer(no_args_is_help=True)
OUTPUT_ROOT_OPTION = typer.Option(help="Directorio raiz de data.")
LIMIT_OPTION = typer.Option(min=1, help="Limita el numero de registros.")
DOWNLOAD_LIMIT_OPTION = typer.Option(min=1, help="Limita la cantidad de descargas.")
SYNC_LIMIT_OPTION = typer.Option(min=1, help="Limita discovery y descarga.")
REFRESH_OPTION = typer.Option(help="Reserva para futuras politicas de cache.")
RETRY_FAILED_OPTION = typer.Option(help="Reintenta registros fallidos.")
RETRY_FAILED_DOWNLOAD_OPTION = typer.Option(
    help="Reintenta registros en estado failed.",
)
MAX_CONCURRENCY_OPTION = typer.Option(min=1, help="Maximo de descargas paralelas.")
DISCOVER_CONCURRENCY_OPTION = typer.Option(
    min=1,
    help="Compatibilidad de flags CLI.",
)


def build_settings(output_root: Path | None, max_concurrency: int | None) -> Settings:
    return Settings.from_root(
        Path.cwd(),
        output_root=output_root,
        max_concurrency=max_concurrency,
    )


def render_summary(summary: CommandSummary) -> None:
    typer.echo(f"command: {summary.command}")
    typer.echo(f"discovered: {summary.discovered}")
    typer.echo(f"pending: {summary.pending}")
    typer.echo(f"downloaded: {summary.downloaded}")
    typer.echo(f"skipped: {summary.skipped}")
    typer.echo(f"failed: {summary.failed}")
    if summary.manifest_csv_path is not None:
        typer.echo(f"manifest_csv: {summary.manifest_csv_path}")
    if summary.manifest_jsonl_path is not None:
        typer.echo(f"manifest_jsonl: {summary.manifest_jsonl_path}")
    for note in summary.notes:
        typer.echo(f"note: {note}")


@app.command("discover-pleno")
def discover_pleno_command(
    output_root: Annotated[Path | None, OUTPUT_ROOT_OPTION] = None,
    limit: Annotated[int | None, LIMIT_OPTION] = None,
    refresh_html: Annotated[bool, REFRESH_OPTION] = False,
    max_concurrency: Annotated[int | None, DISCOVER_CONCURRENCY_OPTION] = None,
) -> None:
    settings = build_settings(output_root, max_concurrency)
    try:
        result = discover_pleno(settings, limit=limit, refresh_html=refresh_html)
    except ManifestLoadError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(f"configuration-error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    render_summary(result.summary)
    raise typer.Exit(code=result.summary.exit_code)


@app.command("download-pleno")
def download_pleno_command(
    output_root: Annotated[Path | None, OUTPUT_ROOT_OPTION] = None,
    limit: Annotated[int | None, DOWNLOAD_LIMIT_OPTION] = None,
    retry_failed: Annotated[bool, RETRY_FAILED_DOWNLOAD_OPTION] = False,
    max_concurrency: Annotated[int | None, MAX_CONCURRENCY_OPTION] = None,
) -> None:
    settings = build_settings(output_root, max_concurrency)
    try:
        result = download_pleno(
            settings,
            limit=limit,
            retry_failed=retry_failed,
            max_concurrency=max_concurrency,
        )
    except ManifestLoadError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except FileNotFoundError as exc:
        typer.echo(f"configuration-error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    render_summary(result.summary)
    raise typer.Exit(code=result.summary.exit_code)


@app.command("sync-pleno")
def sync_pleno_command(
    output_root: Annotated[Path | None, OUTPUT_ROOT_OPTION] = None,
    limit: Annotated[int | None, SYNC_LIMIT_OPTION] = None,
    retry_failed: Annotated[bool, RETRY_FAILED_OPTION] = False,
    max_concurrency: Annotated[int | None, MAX_CONCURRENCY_OPTION] = None,
    refresh_html: Annotated[bool, REFRESH_OPTION] = False,
) -> None:
    settings = build_settings(output_root, max_concurrency)
    try:
        result = sync_pleno(
            settings,
            limit=limit,
            retry_failed=retry_failed,
            max_concurrency=max_concurrency,
            refresh_html=refresh_html,
        )
    except ManifestLoadError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except ValueError as exc:
        typer.echo(f"configuration-error: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    render_summary(result.summary)
    raise typer.Exit(code=result.summary.exit_code)


if __name__ == "__main__":
    app()
