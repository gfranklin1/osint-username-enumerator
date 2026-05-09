from __future__ import annotations

from collections.abc import Iterable

from aliasgraph.models import PlatformConfig

PLATFORMS: list[PlatformConfig] = [
    PlatformConfig(
        name="github",
        profile_url="https://github.com/{username}",
        rate_limit_seconds=1.0,
        not_found_status_codes=[404],
    ),
    PlatformConfig(
        name="reddit",
        profile_url="https://www.reddit.com/user/{username}/about.json",
        rate_limit_seconds=2.0,
        not_found_status_codes=[404],
        not_found_body_substrings=['"error"'],
    ),
    PlatformConfig(
        name="devto",
        profile_url="https://dev.to/{username}",
        rate_limit_seconds=1.0,
        not_found_status_codes=[404],
    ),
]


def get_platforms(names: Iterable[str] | None = None) -> list[PlatformConfig]:
    if not names:
        return list(PLATFORMS)
    wanted = {n.lower() for n in names}
    return [p for p in PLATFORMS if p.name in wanted]
