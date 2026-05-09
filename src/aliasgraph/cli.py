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
)

from aliasgraph.pipeline import PipelineCallbacks, PipelineConfig, run as run_pipeline
from aliasgraph.platforms import load_all_sites
from aliasgraph.reporting.html_report import render_html, write_html
from aliasgraph.reporting.json_report import to_json, write_json
from aliasgraph.reporting.terminal_report import render
from aliasgraph.scanning.scanner import ScanProgress
from aliasgraph.scraping.base import ScrapeProgress

app = typer.Typer(add_completion=False, help="AliasGraph — OSINT username enumeration.")


@app.callback()
def _main() -> None:
    """AliasGraph root."""


class OutputFormat(str, Enum):
    terminal = "terminal"
    json = "json"
    html = "html"


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
    platform: list[str] = typer.Option([], "--platform"),
    site_limit: int = typer.Option(0, "--site-limit"),
    max_candidates: int = typer.Option(30, "--max-candidates"),
    numeric_suffix: list[str] = typer.Option([], "--numeric-suffix"),
    concurrency: int = typer.Option(50, "--concurrency"),
    timeout: float = typer.Option(8.0, "--timeout"),
    scrape: bool = typer.Option(True, "--scrape/--no-scrape"),
    follow_links: bool = typer.Option(True, "--follow-links/--no-follow-links"),
    max_link_depth: int = typer.Option(1, "--max-link-depth"),
    cluster: bool = typer.Option(True, "--cluster/--no-cluster"),
    likely_threshold: float = typer.Option(0.75, "--likely-threshold"),
    use_embeddings: bool = typer.Option(False, "--use-embeddings"),
    fmt: OutputFormat = typer.Option(OutputFormat.terminal, "--format"),
    output: Path | None = typer.Option(None, "--output"),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    """Scan platforms for username variants of SEED, scrape, score, and cluster."""
    err_console = Console(stderr=True)
    cfg = PipelineConfig(
        seed=seed,
        first_name=first_name,
        last_name=last_name,
        aliases=alias,
        numeric_suffixes=numeric_suffix,
        max_candidates=max_candidates,
        platform_filter=platform,
        site_limit=site_limit,
        timeout=timeout,
        concurrency=concurrency,
        scrape=scrape,
        follow_links=follow_links,
        max_link_depth=max_link_depth,
        cluster=cluster,
        likely_threshold=likely_threshold,
        use_embeddings=use_embeddings,
    )

    result = asyncio.run(_run(cfg, err_console, quiet))

    if fmt is OutputFormat.json:
        if output:
            write_json(result, output)
            err_console.print(f"[green]Wrote {output}[/green]")
        else:
            typer.echo(to_json(result))
    elif fmt is OutputFormat.html:
        if output:
            write_html(result, output)
            err_console.print(f"[green]Wrote {output}  (open in browser)[/green]")
        else:
            typer.echo(render_html(result))
    else:
        render(result)
        if output:
            write_html(result, output) if str(output).endswith(".html") else write_json(result, output)
            err_console.print(f"[green]Also wrote {output}[/green]")


async def _run(cfg: PipelineConfig, err_console: Console, quiet: bool):
    if quiet:
        return await run_pipeline(cfg)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TextColumn("{task.fields[stats]}"),
        TextColumn("•"),
        TextColumn("[dim]{task.fields[current]}[/dim]"),
        TimeElapsedColumn(),
        console=err_console,
        transient=False,
    ) as bar:
        scan_task = {"id": None}
        scrape_task = {"id": None}

        def on_scan(p: ScanProgress) -> None:
            if scan_task["id"] is None:
                scan_task["id"] = bar.add_task(
                    "scan", total=p.total, stats="", current=""
                )
            bar.update(
                scan_task["id"],
                completed=p.checked,
                stats=f"found {p.found} • err {p.errored} • skip {p.skipped}",
                current=p.current[:40],
            )

        def on_scrape(p: ScrapeProgress) -> None:
            if scrape_task["id"] is None:
                scrape_task["id"] = bar.add_task(
                    "scrape", total=p.total, stats="", current=""
                )
            bar.update(
                scrape_task["id"],
                completed=p.done,
                total=p.total,
                stats=f"enriched {p.enriched} • failed {p.failed}",
                current=p.current[:40],
            )

        def on_status(msg: str) -> None:
            err_console.print(f"[bold]·[/bold] {msg}")

        cbs = PipelineCallbacks(
            on_scan_progress=on_scan,
            on_scrape_progress=on_scrape,
            on_status=on_status,
        )
        return await run_pipeline(cfg, cbs)


if __name__ == "__main__":
    app()
