from __future__ import annotations

from rich.console import Console
from rich.table import Table

from aliasgraph.models import ScanResult


def render(result: ScanResult, console: Console | None = None) -> None:
    console = console or Console()
    console.rule(f"AliasGraph Report — seed: {result.seed}")
    console.print(
        f"Generated usernames: {len(result.generated_usernames)}    "
        f"Profiles found: {len(result.profiles)}"
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
