from __future__ import annotations

import asyncio
from enum import Enum
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from aliasgraph.models import ScanResult
from aliasgraph.permutations import generate
from aliasgraph.platforms import filter_sites, load_all_sites
from aliasgraph.reporting.json_report import to_json, write_json
from aliasgraph.reporting.terminal_report import render
from aliasgraph.scanning import scan as run_scan
from aliasgraph.scanning.scanner import ScanProgress

app = typer.Typer(add_completion=False, help="AliasGraph — OSINT username enumeration.")


@app.callback()
def _main() -> None:
    """AliasGraph root."""


class OutputFormat(str, Enum):
    terminal = "terminal"
    json = "json"


@app.command(name="list-sites")
def list_sites() -> None:
    """Print number of available sites loaded from the vendored database."""
    sites = load_all_sites()
    typer.echo(f"{len(sites)} sites loaded")


@app.command()
def scan(
    seed: str = typer.Argument(..., help="Seed username."),
    first_name: str | None = typer.Option(None, "--first-name"),
    last_name: str | None = typer.Option(None, "--last-name"),
    alias: list[str] = typer.Option([], "--alias", help="Known alias (repeatable)."),
    platform: list[str] = typer.Option(
        [], "--platform", help="Limit to platform name (repeatable)."
    ),
    site_limit: int = typer.Option(
        0, "--site-limit", help="Cap number of sites scanned (0 = all)."
    ),
    max_candidates: int = typer.Option(30, "--max-candidates"),
    numeric_suffix: list[str] = typer.Option(
        [], "--numeric-suffix", help="Numeric suffix to append (repeatable)."
    ),
    concurrency: int = typer.Option(50, "--concurrency"),
    timeout: float = typer.Option(8.0, "--timeout"),
    fmt: OutputFormat = typer.Option(OutputFormat.terminal, "--format"),
    output: Path | None = typer.Option(None, "--output", help="Write report to file."),
    quiet: bool = typer.Option(False, "--quiet", help="Disable progress bar."),
) -> None:
    """Scan platforms for username variants of SEED."""
    console = Console(stderr=True)
    usernames = generate(
        seed,
        first=first_name,
        last=last_name,
        aliases=alias,
        numeric_suffixes=numeric_suffix,
        max_candidates=max_candidates,
    )
    all_sites = load_all_sites()
    sites = filter_sites(
        all_sites,
        names=platform or None,
        limit=site_limit if site_limit > 0 else None,
    )
    if not sites:
        typer.echo("No sites matched the given filters.", err=True)
        raise typer.Exit(code=1)

    console.print(
        f"[bold]Seed:[/bold] {seed}    "
        f"[bold]Variants:[/bold] {len(usernames)}    "
        f"[bold]Sites:[/bold] {len(sites)}    "
        f"[bold]Total checks:[/bold] {len(usernames) * len(sites)}"
    )

    profiles, errors = asyncio.run(
        _scan_with_progress(
            usernames, sites, timeout, concurrency, console=console, quiet=quiet
        )
    )

    result = ScanResult(
        seed=seed, generated_usernames=usernames, profiles=profiles, errored_sites=errors
    )

    if fmt is OutputFormat.json:
        if output:
            write_json(result, output)
            console.print(f"[green]Wrote {output}[/green]")
        else:
            typer.echo(to_json(result))
    else:
        render(result)
        if output:
            write_json(result, output)
            console.print(f"[green]Also wrote JSON to {output}[/green]")


async def _scan_with_progress(
    usernames: list[str],
    sites: list,
    timeout: float,
    concurrency: int,
    console: Console,
    quiet: bool,
):
    if quiet:
        return await run_scan(usernames, sites, timeout=timeout, concurrency=concurrency)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TextColumn("found {task.fields[found]} • err {task.fields[errored]} • skip {task.fields[skipped]}"),
        TextColumn("•"),
        TextColumn("[dim]{task.fields[current]}[/dim]"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as bar:
        total = len(usernames) * len(sites)
        task_id = bar.add_task(
            "scanning",
            total=total,
            found=0,
            errored=0,
            skipped=0,
            current="",
        )

        def cb(p: ScanProgress) -> None:
            bar.update(
                task_id,
                completed=p.checked,
                found=p.found,
                errored=p.errored,
                skipped=p.skipped,
                current=p.current[:40],
            )

        return await run_scan(
            usernames, sites, timeout=timeout, concurrency=concurrency, progress_cb=cb
        )


if __name__ == "__main__":
    app()
