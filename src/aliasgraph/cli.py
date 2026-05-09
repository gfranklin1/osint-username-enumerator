from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path

import typer

from aliasgraph.models import ScanResult
from aliasgraph.permutations import generate
from aliasgraph.platforms import get_platforms
from aliasgraph.reporting.json_report import to_json, write_json
from aliasgraph.reporting.terminal_report import render
from aliasgraph.scanning import scan as run_scan

app = typer.Typer(add_completion=False, help="AliasGraph — OSINT username enumeration.")


@app.callback()
def _main() -> None:
    """AliasGraph root."""


class OutputFormat(str, Enum):
    terminal = "terminal"
    json = "json"


@app.command()
def scan(
    seed: str = typer.Argument(..., help="Seed username."),
    first_name: str | None = typer.Option(None, "--first-name"),
    last_name: str | None = typer.Option(None, "--last-name"),
    alias: list[str] = typer.Option([], "--alias", help="Known alias (repeatable)."),
    platform: list[str] = typer.Option(
        [], "--platform", help="Limit to platform name (repeatable)."
    ),
    max_candidates: int = typer.Option(100, "--max-candidates"),
    numeric_suffix: list[str] = typer.Option(
        [], "--numeric-suffix", help="Numeric suffix to append, e.g. 2005 (repeatable)."
    ),
    fmt: OutputFormat = typer.Option(OutputFormat.terminal, "--format"),
    output: Path | None = typer.Option(None, "--output", help="Write report to file."),
) -> None:
    """Scan platforms for username variants of SEED."""
    usernames = generate(
        seed,
        first=first_name,
        last=last_name,
        aliases=alias,
        numeric_suffixes=numeric_suffix,
        max_candidates=max_candidates,
    )
    cfgs = get_platforms(platform)
    profiles = asyncio.run(run_scan(usernames, cfgs))
    result = ScanResult(seed=seed, generated_usernames=usernames, profiles=profiles)

    if fmt is OutputFormat.json:
        payload = to_json(result)
        if output:
            write_json(result, output)
            typer.echo(f"Wrote {output}")
        else:
            typer.echo(payload)
    else:
        render(result)
        if output:
            write_json(result, output)
            typer.echo(f"Also wrote JSON to {output}")


if __name__ == "__main__":
    app()
