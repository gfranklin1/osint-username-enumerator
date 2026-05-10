"""Smoke test for the follow-link pass — see ITER3 §5.2.

We register a fake site-specific scraper that the pipeline-driven scan
exercises, then assert a discovered cross-platform handle gets re-scanned
on its target site and merged into the resulting profile list.
"""
from __future__ import annotations

import asyncio

import httpx

from aliasgraph.models import ExtractedHandle, PlatformConfig, Profile
from aliasgraph.pipeline import _follow_pass, PipelineCallbacks, PipelineConfig


def _site(name: str) -> PlatformConfig:
    return PlatformConfig(
        name=name,
        profile_url=f"https://{name.lower()}.example/{{username}}",
    )


def test_follow_pass_scans_extracted_handle_on_target_site(monkeypatch):
    # Initial profile on GitHub points to a Twitter handle we haven't scanned.
    initial = Profile(
        site="GitHub",
        url="https://github.example/alice",
        username="alice",
        extracted_handles=[
            ExtractedHandle(
                site="Twitter",
                handle="evilfollow",
                source_url="https://twitter.com/evilfollow",
            )
        ],
    )

    sites = [_site("GitHub"), _site("Twitter")]
    cfg = PipelineConfig(seed="alice", scrape=False, follow_links=True)

    # Fake the scan-call inside _follow_pass: return a Twitter profile when
    # asked for "evilfollow" on the Twitter site.
    async def fake_run_scan(usernames, plats, **kwargs):
        out = []
        for cfg_site in plats:
            for u in usernames:
                out.append(
                    Profile(
                        site=cfg_site.name,
                        url=f"https://{cfg_site.name.lower()}.example/{u}",
                        username=u,
                    )
                )
        return out, []

    monkeypatch.setattr("aliasgraph.pipeline.run_scan", fake_run_scan)

    profiles, errs = asyncio.run(
        _follow_pass(
            [initial],
            sites,
            cfg,
            PipelineCallbacks(),
            already_scanned={("github", "alice")},
        )
    )
    keys = {p.key() for p in profiles}
    assert "github:alice" in keys
    assert "twitter:evilfollow" in keys
    assert errs == []


def test_follow_pass_skips_already_scanned():
    initial = Profile(
        site="GitHub",
        url="https://github.example/alice",
        username="alice",
        extracted_handles=[
            ExtractedHandle(
                site="Twitter",
                handle="alice",
                source_url="https://twitter.com/alice",
            )
        ],
    )

    sites = [_site("GitHub"), _site("Twitter")]
    cfg = PipelineConfig(seed="alice", scrape=False)

    profiles, errs = asyncio.run(
        _follow_pass(
            [initial],
            sites,
            cfg,
            PipelineCallbacks(),
            already_scanned={("twitter", "alice")},  # twitter:alice already swept
        )
    )
    # No new profiles added, no error — the handle was filtered out.
    assert {p.key() for p in profiles} == {"github:alice"}
    assert errs == []
