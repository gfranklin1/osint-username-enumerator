from __future__ import annotations

from collections import Counter

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aliasgraph.models import Profile, ScanResult


def _short(s: str | None, limit: int = 80) -> str:
    if not s:
        return ""
    s = s.strip().replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _profile_row(p: Profile) -> tuple[str, str, str, str, str]:
    return (
        p.site,
        p.username,
        _short(p.display_name or "", 28),
        _short(p.bio or "", 50),
        _short(str(p.url), 60),
    )


def render(result: ScanResult, console: Console | None = None) -> None:
    console = console or Console()

    # Header
    header = Text()
    header.append(f"Seed: {result.seed}", style="bold")
    header.append("    ")
    header.append(f"Variants: {len(result.generated_usernames)}    ")
    header.append(f"Profiles: {len(result.profiles)}    ", style="cyan")
    header.append(f"Clusters: {len(result.clusters)}    ", style="green")
    header.append(f"Errors: {len(result.errored_sites)}", style="dim")
    console.print(Panel(header, title="AliasGraph", expand=False))

    profile_by_key = {p.key(): p for p in result.profiles}
    clustered_keys: set[str] = set()

    for cluster in result.clusters:
        clustered_keys.update(m.lower() for m in cluster.members)
        members = [profile_by_key[m.lower()] for m in cluster.members if m.lower() in profile_by_key]

        members_table = Table(show_header=True, header_style="bold", padding=(0, 1))
        members_table.add_column("Source", style="cyan")
        members_table.add_column("Site", style="cyan")
        members_table.add_column("Username", style="bold")
        members_table.add_column("Display name")
        members_table.add_column("Bio", overflow="fold", max_width=40)
        members_table.add_column("URL", style="dim")
        for m in members:
            members_table.add_row("verified", *_profile_row(m))
        for a in cluster.asserted:
            via = ", ".join(a.asserted_by)
            members_table.add_row(
                Text(f"asserted via {via}", style="yellow"),
                Text(a.site, style="cyan"),
                Text(a.handle, style="bold yellow"),
                Text("(not scanned)", style="dim italic"),
                Text("", style="dim"),
                Text(_short(a.url, 60), style="dim"),
            )

        evidence_lines: list[str] = []
        for line in cluster.evidence:
            evidence_lines.append(f"[green]+[/green] {line}")
        evidence = Text.from_markup("\n".join(evidence_lines)) if evidence_lines else Text("(no aggregated evidence)", style="dim")

        title = (
            f"[bold green]Cluster {cluster.cluster_id}[/bold green] — "
            f"confidence [bold]{cluster.confidence:.0%}[/bold] — "
            f"{len(members)} profile{'s' if len(members) != 1 else ''}"
        )
        body = Group(members_table, Text("\nEvidence:", style="bold"), evidence)
        console.print(Panel(body, title=title, title_align="left", border_style="green"))

    ungrouped = [p for p in result.profiles if p.key() not in clustered_keys]
    if ungrouped:
        table = Table(title=f"Ungrouped profiles ({len(ungrouped)})", show_header=True)
        table.add_column("Site", style="cyan")
        table.add_column("Username", style="bold")
        table.add_column("Display name")
        table.add_column("Bio", overflow="fold", max_width=40)
        table.add_column("URL", style="dim")
        for p in ungrouped:
            table.add_row(*_profile_row(p))
        console.print(table)

    if not result.profiles:
        console.print("[yellow]No profiles found.[/yellow]")

    if result.errored_sites:
        reasons = Counter(e.reason for e in result.errored_sites)
        sites_down = sorted({e.site for e in result.errored_sites})
        summary = ", ".join(f"{r}={n}" for r, n in reasons.most_common())
        preview = ", ".join(sites_down[:15])
        more = "" if len(sites_down) <= 15 else f" … (+{len(sites_down) - 15} more)"
        console.print(
            f"\n[dim]Errors: {len(sites_down)} sites · {summary} · {preview}{more}[/dim]"
        )
