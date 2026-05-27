from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn

from semantic_selector.db.connection import init_database
from semantic_selector.mcp.server import run_mcp_stdio
from semantic_selector.services import build_index, inspect_index, validate_index
from semantic_selector.index_build.progress import BuildProgressReporter
from semantic_selector.settings import DEFAULT_INDEX_PATH, resolve_path

app = typer.Typer(no_args_is_help=True, help="Semantic Selector MVP CLI")


@app.command("init-db")
def init_db(
    output: Path = typer.Option(DEFAULT_INDEX_PATH, "--output", help="SQLite index path"),
) -> None:
    """Initialize an empty selector index database."""
    path = resolve_path(output)
    init_database(path)
    typer.echo(f"Initialized database at {path}")


@app.command("build-index")
def build_index_cmd(
    sources: Path = typer.Option(..., "--sources", help="Sources YAML config"),
    extractors: Path = typer.Option(
        Path("config/extractors.example.yaml"), "--extractors", help="Extractors YAML config"
    ),
    criteria: Path = typer.Option(..., "--criteria", help="Criteria YAML config"),
    output: Path = typer.Option(DEFAULT_INDEX_PATH, "--output", help="Output SQLite path"),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        help="Suppress progress messages (JSON report still printed to stdout)",
    ),
) -> None:
    """Build a derived selector index from local ontology sources."""
    progress = None
    if not quiet:
        progress = BuildProgressReporter(lambda message: typer.echo(message, err=True))
    report = build_index(
        sources_path=resolve_path(sources),
        extractors_path=resolve_path(extractors),
        criteria_path=resolve_path(criteria),
        output_path=resolve_path(output),
        progress=progress,
    )
    typer.echo(json.dumps(report.to_dict(), indent=2))


@app.command("validate-index")
def validate_index_cmd(
    index: Path = typer.Option(DEFAULT_INDEX_PATH, "--index", help="SQLite index path"),
) -> None:
    """Validate an existing selector index."""
    path = resolve_path(index)
    validate_index(path)
    typer.echo(f"Index valid: {path}")


@app.command("inspect-index")
def inspect_index_cmd(
    index: Path = typer.Option(DEFAULT_INDEX_PATH, "--index", help="SQLite index path"),
) -> None:
    """Inspect index snapshot metadata and artifact summary."""
    info = inspect_index(resolve_path(index))
    typer.echo(json.dumps(info, indent=2))


@app.command("serve-api")
def serve_api_cmd(
    index: Path = typer.Option(DEFAULT_INDEX_PATH, "--index", help="SQLite index path"),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Serve the Semantic Selector REST API."""
    from semantic_selector.api.app import create_app

    api = create_app(index_path=resolve_path(index))
    uvicorn.run(api, host=host, port=port)


@app.command("serve-mcp")
def serve_mcp_cmd(
    index: Path = typer.Option(DEFAULT_INDEX_PATH, "--index", help="SQLite index path"),
    transport: str = typer.Option("stdio", "--transport", help="MCP transport (stdio)"),
) -> None:
    """Run the read-only Semantic Selector MCP server."""
    if transport != "stdio":
        raise typer.BadParameter("Only stdio transport is supported in the MVP")
    run_mcp_stdio(resolve_path(index))


if __name__ == "__main__":
    app()
