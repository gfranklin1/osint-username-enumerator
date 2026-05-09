from __future__ import annotations

from collections import Counter

from rich.console import Console
from rich.table import Table

from aliasgraph.models import ScanResult


def render(result: ScanResult, console: Console | None = None) -> None:
    console = console or Console()
    console.rule(f"AliasGraph Report — seed: {result.seed}")
    console.print(
        f"Generated usernames: {len(result.generated_usernames)}    "
        f"Profiles found: {len(result.profiles)}    "
        f"Errored checks: {len(result.errored_sites)}"
    )

    if result.profiles:
        table = Table(title="Profiles", show_lines=False)
        table.add_column("Site")
        table.add_column("Username")
        table.add_column("URL")
        for p in result.profiles:
            table.add_row(p.site, p.username, str(p.url))
        console.print(table)
    else:
        console.print("[yellow]No profiles found.[/yellow]")

    if result.errored_sites:
        reasons = Counter(e.reason for e in result.errored_sites)
        sites_down = sorted({e.site for e in result.errored_sites})
        console.print(
            f"\n[dim]Sites unreachable / errored ({len(sites_down)} sites, "
            f"{sum(reasons.values())} checks): "
            + ", ".join(f"{r}={n}" for r, n in reasons.most_common())
            + "[/dim]"
        )
        preview = ", ".join(sites_down[:15])
        more = "" if len(sites_down) <= 15 else f" … (+{len(sites_down) - 15} more)"
        console.print(f"[dim]  {preview}{more}[/dim]")
