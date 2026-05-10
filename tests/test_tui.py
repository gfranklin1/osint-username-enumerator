"""Smoke tests for the optional Textual TUI.

Skipped automatically when textual isn't installed (``aliasgraph[tui]``).
"""
from __future__ import annotations

import pytest

textual = pytest.importorskip("textual")

# Imports below depend on textual being importable.
from textual.widgets import Input, Switch, Tree  # noqa: E402

from aliasgraph.models import Cluster, Profile, ScanResult  # noqa: E402
from aliasgraph.pipeline import PipelineConfig  # noqa: E402
from aliasgraph.tui.app import (  # noqa: E402
    AliasGraphApp,
    FormScreen,
    ResultsScreen,
)


@pytest.mark.asyncio
async def test_form_screen_validates_and_builds_config():
    app = AliasGraphApp()
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        scr = app.screen
        assert isinstance(scr, FormScreen)

        # Empty seed must be rejected.
        assert scr._build_cfg() is None

        # Filled-in form yields a valid PipelineConfig.
        scr.query_one("#seed", Input).value = "testuser1"
        scr.query_one("#first", Input).value = "Test"
        scr.query_one("#last", Input).value = "User"
        scr.query_one("#aliases", Input).value = "alt1, alt2"
        scr.query_one("#scrape", Switch).value = False
        cfg = scr._build_cfg()
        assert cfg is not None
        assert cfg.seed == "testuser1"
        assert cfg.first_name == "Test"
        assert cfg.aliases == ["alt1", "alt2"]
        assert cfg.scrape is False
        await app.action_quit()


@pytest.mark.asyncio
async def test_results_screen_renders_and_reclusters():
    app = AliasGraphApp()
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        cfg = PipelineConfig(seed="testuser1", scrape=False, cluster=False)
        p1 = Profile(
            site="GitHub",
            url="https://github.com/testuser1",
            username="testuser1",
            display_name="Test User",
            quality=0.85,
        )
        p2 = Profile(
            site="Reddit",
            url="https://reddit.com/user/testuser1",
            username="testuser1",
            display_name="Test U",
            quality=0.65,
        )
        weak = Profile(
            site="Facebook",
            url="https://facebook.com/testuser1",
            username="testuser1",
            quality=0.10,
        )
        cluster = Cluster(
            cluster_id=1,
            confidence=0.92,
            min_edge=0.85,
            members=["GitHub:testuser1", "Reddit:testuser1"],
            evidence=["Same display name"],
        )
        result = ScanResult(
            seed="testuser1",
            generated_usernames=["testuser1"],
            profiles=[p1, p2],
            clusters=[cluster],
            unverified_profiles=[weak],
        )
        await app.push_screen(ResultsScreen(result, cfg))
        await pilot.pause()
        rscr = app.screen
        tree = rscr.query_one("#cluster-tree", Tree)
        labels = [str(child.label) for child in tree.root.children]
        assert any("Cluster 1" in lbl for lbl in labels)
        assert any("Weak" in lbl for lbl in labels)

        # Tighten quality threshold so p2 falls out of "verified".
        rscr.query_one("#rt-quality", Input).value = "0.70"
        rscr._recluster()
        await pilot.pause()
        assert len(rscr.result.profiles) == 1
        assert len(rscr.result.clusters) == 0  # only one verified, no pair to cluster
        assert len(rscr.result.unverified_profiles) == 2
        await app.action_quit()
