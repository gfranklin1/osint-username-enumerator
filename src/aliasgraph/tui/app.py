"""Textual TUI for AliasGraph.

Three screens:

- ``FormScreen``    — collects pipeline configuration.
- ``RunningScreen`` — runs the pipeline as a worker, shows live progress.
- ``ResultsScreen`` — clusters tree on the left, detail panel on the right,
  re-tune controls so the user can adjust thresholds and re-cluster without
  re-fetching, plus export buttons.

The TUI is opt-in (``pip install aliasgraph[tui]``) and never imported by the
rest of the package — failures here cannot break the CLI.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Static,
    Switch,
    Tree,
)

from aliasgraph.clustering import build_clusters
from aliasgraph.models import (
    AssertedAccount,
    Cluster,
    Profile,
    ScanResult,
)
from aliasgraph.pipeline import PipelineCallbacks, PipelineConfig
from aliasgraph.pipeline import run as run_pipeline
from aliasgraph.reporting.html_report import write_html
from aliasgraph.reporting.json_report import write_json
from aliasgraph.scanning.scanner import ScanProgress
from aliasgraph.scraping.base import ScrapeProgress

# --------------------------------------------------------------------------- #
#  FormScreen
# --------------------------------------------------------------------------- #


class FormScreen(Screen):
    """Configure a scan."""

    BINDINGS = [
        Binding("ctrl+r", "run", "Run scan"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer(id="form-body"):
            yield Label("Seed username (required)", classes="field-label")
            yield Input(placeholder="e.g. testuser1", id="seed")
            yield Label("First name (optional)", classes="field-label")
            yield Input(id="first")
            yield Label("Last name (optional)", classes="field-label")
            yield Input(id="last")
            yield Label("Aliases (comma-separated)", classes="field-label")
            yield Input(placeholder="alt1, alt2", id="aliases")
            yield Label("Numeric suffixes (comma-separated)", classes="field-label")
            yield Input(placeholder="2005, 1, 99", id="suffixes")
            yield Label("Platforms (comma-separated, blank = all)", classes="field-label")
            yield Input(placeholder="GitHub, Reddit, Dev.to", id="platforms")
            yield Label("Site limit (0 = no limit)", classes="field-label")
            yield Input(value="0", id="site_limit")
            yield Label("Max username candidates", classes="field-label")
            yield Input(value="30", id="max_candidates")
            yield Label("Concurrency", classes="field-label")
            yield Input(value="50", id="concurrency")
            yield Label("Timeout (s)", classes="field-label")
            yield Input(value="8.0", id="timeout")
            yield Label("Likely threshold (0.0–1.0)", classes="field-label")
            yield Input(value="0.75", id="likely_threshold")
            yield Label("Quality threshold (0.0–1.0)", classes="field-label")
            yield Input(value="0.30", id="quality_threshold")
            yield Label("Max link follow depth", classes="field-label")
            yield Input(value="1", id="max_link_depth")

            yield Label("Toggles", classes="field-label")
            with Horizontal(classes="switches-row"):
                yield Label("Scrape")
                yield Switch(value=True, id="scrape")
                yield Label("Avatar")
                yield Switch(value=True, id="avatar_hash")
                yield Label("Follow")
                yield Switch(value=True, id="follow_links")
                yield Label("Cluster")
                yield Switch(value=True, id="cluster")
                yield Label("Embed")
                yield Switch(value=False, id="use_embeddings")

            with Horizontal(classes="button-row"):
                yield Button.success("Run scan (Ctrl+R)", id="run-btn")
                yield Button("Quit", id="quit-btn")
        yield Footer()

    # ----- actions ----- #

    def action_run(self) -> None:
        cfg = self._build_cfg()
        if cfg is not None:
            self.app.push_screen(RunningScreen(cfg))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-btn":
            cfg = self._build_cfg()
            if cfg is not None:
                self.app.push_screen(RunningScreen(cfg))
        elif event.button.id == "quit-btn":
            self.app.exit()

    # ----- helpers ----- #

    def _val(self, wid: str) -> str:
        return self.query_one(f"#{wid}", Input).value

    def _sw(self, wid: str) -> bool:
        return self.query_one(f"#{wid}", Switch).value

    def _csv(self, wid: str) -> list[str]:
        return [x.strip() for x in self._val(wid).split(",") if x.strip()]

    def _build_cfg(self) -> PipelineConfig | None:
        seed = self._val("seed").strip()
        if not seed:
            self.app.bell()
            self.notify("Seed is required.", severity="error")
            return None
        try:
            return PipelineConfig(
                seed=seed,
                first_name=self._val("first").strip() or None,
                last_name=self._val("last").strip() or None,
                aliases=self._csv("aliases"),
                numeric_suffixes=self._csv("suffixes"),
                max_candidates=int(self._val("max_candidates") or 30),
                platform_filter=self._csv("platforms"),
                site_limit=int(self._val("site_limit") or 0),
                timeout=float(self._val("timeout") or 8.0),
                concurrency=int(self._val("concurrency") or 50),
                scrape=self._sw("scrape"),
                avatar_hash=self._sw("avatar_hash"),
                follow_links=self._sw("follow_links"),
                max_link_depth=int(self._val("max_link_depth") or 1),
                cluster=self._sw("cluster"),
                likely_threshold=float(self._val("likely_threshold") or 0.75),
                quality_threshold=float(self._val("quality_threshold") or 0.30),
                use_embeddings=self._sw("use_embeddings"),
            )
        except ValueError as e:
            self.notify(f"Invalid number: {e}", severity="error")
            return None


# --------------------------------------------------------------------------- #
#  RunningScreen
# --------------------------------------------------------------------------- #


class RunningScreen(Screen):
    """Live progress while the pipeline executes."""

    BINDINGS = [
        Binding("escape", "back", "Back to form"),
    ]

    def __init__(self, cfg: PipelineConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self._done = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="running-body"):
            yield Static(
                f"Scanning seed: [bold]{self.cfg.seed}[/]",
                id="seed-line",
            )
            yield Label("Existence checks", classes="field-label")
            yield ProgressBar(id="scan-bar", show_eta=True)
            yield Label("Profile scraping", classes="field-label")
            yield ProgressBar(id="scrape-bar", show_eta=True)
            yield Label("Status", classes="field-label")
            yield RichLog(id="status-log", highlight=False, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self._run(), exclusive=True, group="pipeline")

    async def _run(self) -> None:
        scan_bar = self.query_one("#scan-bar", ProgressBar)
        scrape_bar = self.query_one("#scrape-bar", ProgressBar)
        log = self.query_one("#status-log", RichLog)

        def on_scan(p: ScanProgress) -> None:
            scan_bar.update(total=p.total or None, progress=p.checked)

        def on_scrape(p: ScrapeProgress) -> None:
            scrape_bar.update(total=p.total or None, progress=p.done)

        def on_status(msg: str) -> None:
            log.write(f"[green]·[/] {msg}")

        cbs = PipelineCallbacks(
            on_scan_progress=on_scan,
            on_scrape_progress=on_scrape,
            on_status=on_status,
        )
        try:
            result = await run_pipeline(self.cfg, cbs)
        except Exception as e:  # surface to user, don't crash the TUI
            log.write(f"[red]ERROR: {type(e).__name__}: {e}[/]")
            log.write("[dim]Press Esc to return to the form.[/]")
            return
        self._done = True
        self.app.switch_screen(ResultsScreen(result, self.cfg))

    def action_back(self) -> None:
        if not self._done:
            self.workers.cancel_group(self, "pipeline")
        self.app.pop_screen()


# --------------------------------------------------------------------------- #
#  ResultsScreen
# --------------------------------------------------------------------------- #


class ResultsScreen(Screen):
    """Browse clusters / profiles / errors. Re-tune and re-cluster in place."""

    BINDINGS = [
        Binding("ctrl+r", "recluster", "Re-cluster"),
        Binding("n", "new_scan", "New scan"),
        Binding("escape", "new_scan", "Back"),
    ]

    def __init__(self, result: ScanResult, cfg: PipelineConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.result = result
        # Combined raw profiles preserve quality scores so we can re-filter
        # without re-fetching. ``profiles`` here are the verified ones; the
        # weak hits are exposed via ``unverified_profiles``.
        self.raw_profiles: list[Profile] = (
            list(result.profiles) + list(result.unverified_profiles)
        )

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="results-body"):
            yield Static(self._summary(), id="summary", markup=True)
            with Horizontal(id="results-grid"):
                yield Tree("Results", id="cluster-tree")
                yield ScrollableContainer(id="detail-panel")
            with Horizontal(id="retune-row"):
                yield Label("Retune:", classes="muted")
                yield Label("likely")
                yield Input(value=f"{self.cfg.likely_threshold:.2f}", id="rt-likely")
                yield Label("quality")
                yield Input(value=f"{self.cfg.quality_threshold:.2f}", id="rt-quality")
                yield Button("Re-cluster (Ctrl+R)", id="recluster-btn")
            with Horizontal(classes="action-row"):
                yield Button("Save JSON", id="save-json")
                yield Button("Save HTML", id="save-html")
                yield Button.warning("New scan (N)", id="new-scan")
                yield Button("Quit", id="quit-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_tree()
        self._show_overview()

    # ----- summary / tree ----- #

    def _summary(self) -> str:
        r = self.result
        return (
            f"[bold]{r.seed}[/] · "
            f"variants [bold]{len(r.generated_usernames)}[/] · "
            f"profiles [cyan]{len(r.profiles)}[/] · "
            f"clusters [green]{len(r.clusters)}[/] · "
            f"weak [yellow]{len(r.unverified_profiles)}[/] · "
            f"errors [dim]{len(r.errored_sites)}[/]"
        )

    def _populate_tree(self) -> None:
        tree = self.query_one("#cluster-tree", Tree)
        tree.clear()
        tree.root.expand()
        if self.result.clusters:
            for c in self.result.clusters:
                node = tree.root.add(
                    f"Cluster {c.cluster_id} · {c.confidence:.0%} (min {c.min_edge:.0%})",
                    data={"type": "cluster", "cluster": c},
                    expand=True,
                )
                for m in c.members:
                    node.add_leaf(m, data={"type": "member", "key": m})
                for a in c.asserted:
                    node.add_leaf(
                        f"⊥ {a.site}:{a.handle} (asserted)",
                        data={"type": "asserted", "asserted": a},
                    )
        in_cluster = {
            m.lower() for c in self.result.clusters for m in c.members
        }
        ungrouped = [p for p in self.result.profiles if p.key() not in in_cluster]
        if ungrouped:
            ung_node = tree.root.add(
                f"Ungrouped profiles ({len(ungrouped)})", expand=False
            )
            for p in ungrouped:
                ung_node.add_leaf(
                    f"{p.site}:{p.username}  q={p.quality:.2f}",
                    data={"type": "profile", "profile": p},
                )
        if self.result.unverified_profiles:
            weak = tree.root.add(
                f"Weak hits ({len(self.result.unverified_profiles)})", expand=False
            )
            for p in self.result.unverified_profiles:
                weak.add_leaf(
                    f"{p.site}:{p.username}  q={p.quality:.2f}",
                    data={"type": "profile", "profile": p},
                )
        if self.result.errored_sites:
            err_node = tree.root.add(
                f"Errors ({len(self.result.errored_sites)})", expand=False
            )
            for e in self.result.errored_sites[:50]:
                err_node.add_leaf(
                    f"{e.site}:{e.username} — {e.reason}",
                    data={"type": "error", "error": e},
                )
            if len(self.result.errored_sites) > 50:
                err_node.add_leaf(
                    f"… +{len(self.result.errored_sites) - 50} more",
                    data={"type": "info"},
                )

    # ----- detail panel ----- #

    def _set_detail(self, widget: Static) -> None:
        panel = self.query_one("#detail-panel", ScrollableContainer)
        panel.remove_children()
        panel.mount(widget)

    def _show_text(self, text: str) -> None:
        self._set_detail(Static(text, markup=True))

    def _show_overview(self) -> None:
        self._show_text(
            "[bold green]AliasGraph results[/]\n\n"
            "Select a cluster, member, or weak hit on the left to see details.\n"
            "Use the retune row to adjust thresholds and re-cluster without "
            "re-fetching.\n\n"
            "[dim]Bindings:[/] Ctrl+R re-cluster · N new scan · Q quit"
        )

    def _show_cluster(self, c: Cluster) -> None:
        lines = [
            f"[bold green]Cluster {c.cluster_id}[/]",
            f"confidence: [bold]{c.confidence:.0%}[/]   "
            f"min edge: [bold]{c.min_edge:.0%}[/]",
            f"members: {len(c.members)}",
            "",
            "[bold]Evidence[/]",
        ]
        if c.evidence:
            lines.extend(f"  + {e}" for e in c.evidence)
        else:
            lines.append("  [dim](none)[/]")
        if c.asserted:
            lines.append("")
            lines.append("[bold]Asserted accounts[/]")
            for a in c.asserted:
                via = ", ".join(a.asserted_by)
                lines.append(f"  • {a.site}:{a.handle}  via {via}")
        self._show_text("\n".join(lines))

    def _show_profile(self, p: Profile) -> None:
        lines = [
            f"[bold cyan]{p.site}:{p.username}[/]   q={p.quality:.2f}",
            f"url: {p.url}",
        ]
        if p.display_name:
            lines.append(f"display: {p.display_name}")
        if p.bio:
            lines.append(f"bio: {p.bio}")
        if p.location:
            lines.append(f"location: {p.location}")
        if p.followers is not None:
            lines.append(f"followers: {p.followers}")
        if p.created_at:
            lines.append(f"created: {p.created_at}")
        if p.links:
            lines.append("")
            lines.append("[bold]Links[/]")
            lines.extend(f"  {u}" for u in p.links[:20])
            if len(p.links) > 20:
                lines.append(f"  … +{len(p.links) - 20} more")
        if p.extracted_handles:
            lines.append("")
            lines.append("[bold]Extracted handles[/]")
            for h in p.extracted_handles[:20]:
                lines.append(f"  → {h.site}:{h.handle}")
        self._show_text("\n".join(lines))

    def _show_asserted(self, a: AssertedAccount) -> None:
        via = ", ".join(a.asserted_by)
        self._show_text(
            f"[bold yellow]{a.site}:{a.handle}[/]\n\n"
            f"asserted by: {via}\n"
            f"url: {a.url}\n\n"
            "[dim]Not directly scanned. Run a new scan with this handle as "
            "the seed to verify.[/]"
        )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data or {}
        kind = data.get("type")
        if kind == "cluster":
            self._show_cluster(data["cluster"])
        elif kind == "member":
            key = str(data["key"]).lower()
            for p in self.raw_profiles:
                if p.key() == key:
                    self._show_profile(p)
                    return
            self._show_text(f"No loaded profile for {key}")
        elif kind == "asserted":
            self._show_asserted(data["asserted"])
        elif kind == "profile":
            self._show_profile(data["profile"])
        elif kind == "error":
            e = data["error"]
            self._show_text(
                f"[bold]{e.site}[/] / {e.username}\nreason: {e.reason}"
            )
        else:
            self._show_overview()

    # ----- buttons / actions ----- #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "recluster-btn":
            self._recluster()
        elif bid == "save-json":
            self._save_json()
        elif bid == "save-html":
            self._save_html()
        elif bid == "new-scan":
            self.app.pop_screen()
        elif bid == "quit-btn":
            self.app.exit()

    def action_recluster(self) -> None:
        self._recluster()

    def action_new_scan(self) -> None:
        self.app.pop_screen()

    def _save_json(self) -> None:
        path = Path(f"{self.cfg.seed}.json")
        try:
            write_json(self.result, path)
            self.notify(f"Wrote {path.resolve()}", severity="information")
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")

    def _save_html(self) -> None:
        path = Path(f"{self.cfg.seed}.html")
        try:
            write_html(self.result, path)
            self.notify(f"Wrote {path.resolve()}", severity="information")
        except Exception as e:
            self.notify(f"Save failed: {e}", severity="error")

    def _recluster(self) -> None:
        try:
            new_likely = float(
                self.query_one("#rt-likely", Input).value
                or self.cfg.likely_threshold
            )
            new_quality = float(
                self.query_one("#rt-quality", Input).value
                or self.cfg.quality_threshold
            )
        except ValueError as e:
            self.notify(f"Invalid threshold: {e}", severity="error")
            return
        if not (0.0 <= new_likely <= 1.0 and 0.0 <= new_quality <= 1.0):
            self.notify("Thresholds must be in [0.0, 1.0]", severity="error")
            return

        verified = [p for p in self.raw_profiles if p.quality >= new_quality]
        unverified = [p for p in self.raw_profiles if p.quality < new_quality]
        embedder = None
        if self.cfg.use_embeddings:
            try:
                from aliasgraph.scoring.embeddings import (
                    SentenceTransformerEmbedder,
                )
                embedder = SentenceTransformerEmbedder()
            except SystemExit as e:
                self.notify(str(e), severity="error")
                return
        clusters = (
            build_clusters(verified, threshold=new_likely, embedder=embedder)
            if len(verified) >= 2
            else []
        )
        self.result = ScanResult(
            seed=self.result.seed,
            generated_usernames=self.result.generated_usernames,
            profiles=verified,
            errored_sites=self.result.errored_sites,
            clusters=clusters,
            unverified_profiles=unverified,
        )
        self.cfg.likely_threshold = new_likely
        self.cfg.quality_threshold = new_quality
        self.query_one("#summary", Static).update(self._summary())
        self._populate_tree()
        self.notify(
            f"Re-clustered: {len(clusters)} cluster(s) "
            f"at likely={new_likely:.2f}, quality={new_quality:.2f}",
            severity="information",
        )


# --------------------------------------------------------------------------- #
#  App
# --------------------------------------------------------------------------- #


class AliasGraphApp(App):
    CSS_PATH = "styles.tcss"
    TITLE = "AliasGraph"
    SUB_TITLE = "OSINT username enumeration"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def on_mount(self) -> None:
        self.push_screen(FormScreen())
