"""Regression test for ITER3 §1.2 — `_seen_pairs` must include every
(scanned_site × generated_username) combination, not only sites where a
profile was found."""
from __future__ import annotations

from aliasgraph.models import PlatformConfig, Profile
from aliasgraph.pipeline import _seen_pairs


def _site(name: str) -> PlatformConfig:
    return PlatformConfig(
        name=name,
        profile_url=f"https://{name.lower()}.example/{{username}}",
    )


def _profile(site: str, user: str) -> Profile:
    return Profile(
        site=site,
        url=f"https://{site.lower()}.example/{user}",
        username=user,
    )


def test_seen_pairs_covers_full_cartesian():
    sites = [_site("GitHub"), _site("Reddit"), _site("DeadSite")]
    usernames = ["alice", "bob"]
    profiles = [_profile("GitHub", "alice")]  # only GitHub found a hit

    seen = _seen_pairs(sites, usernames, profiles)

    # All 3 × 2 site/username combinations are recorded as scanned, plus the
    # one verified profile (already in the cartesian set).
    assert len(seen) == 6
    assert ("github", "alice") in seen
    assert ("github", "bob") in seen
    assert ("reddit", "alice") in seen
    assert ("reddit", "bob") in seen
    assert ("deadsite", "alice") in seen
    assert ("deadsite", "bob") in seen


def test_seen_pairs_includes_follow_discovered_profiles():
    sites = [_site("GitHub")]
    usernames = ["alice"]
    # Follow-pass added a Twitter profile — its username isn't in `usernames`
    # but it must still be tracked so we don't re-scan it.
    profiles = [_profile("GitHub", "alice"), _profile("Twitter", "evilfollow")]

    seen = _seen_pairs(sites, usernames, profiles)
    assert ("twitter", "evilfollow") in seen
    assert ("github", "alice") in seen
