"""Detect platform-boilerplate bios so they do not pollute similarity scoring.

When a generic HTML scraper reads `<meta og:description>` from a site that has
no real user-bio field, it pulls the site's tagline ("Imgur: The magic of the
Internet"), per-page stock copy ("Overview of {user} activities"), or the
platform's own marketing pitch. None of those represent the user, so we treat
them as no bio at all.
"""
from __future__ import annotations

import re

# Snippets that strongly imply the description is platform copy, not a user bio.
_PLATFORM_BOILERPLATE = [
    "the magic of the internet",
    "imagine, program, share",
    "organize anything, together",
    "scratch is a free programming",
    "make games, stories",
    "see instagram photos and videos",
    "instagram photos and videos",
    "tiktok - make your day",
    "share your videos with friends",
    "make your day",
    "discover docker images from",
    "discover and share",
    "user · ",
    "discover {username}",
    "follow {username}",
    "explore {username}",
    "overview of {username}",
    "profile on themeforest",
    "wordpress.org profile for",
    "github gist: star and fork",
    "find the best & newest featured gifs",
    "openstreetmap is a map of the world",
    "trello is a collaboration tool",
    "research papers on academia.edu",
    "gists by creating an account on github",
    "{username}'s profile",
    "{username}'s gists",
    "{username}'s blog",
    "is an artist on deviantart",
    "discover {username}'s",
    "buying, selling, collecting on ebay",
    "yandex",
]


def is_platform_boilerplate(bio: str | None, username: str, site: str | None = None) -> bool:
    if not bio:
        return False
    b = bio.lower().strip()
    if len(b) < 4:
        return True  # 1–3 chars is noise (single emoji, "hi", "."), not a bio
    u = username.lower()
    s = (site or "").lower()
    for snippet in _PLATFORM_BOILERPLATE:
        marker = snippet.replace("{username}", u)
        if marker in b:
            return True
    # "{username} on {site}" pattern.
    if re.search(rf"\b{re.escape(u)}\b\s+on\s+\b{re.escape(s)}\b", b):
        return True
    return False


def clean_bio(bio: str | None, username: str, site: str | None = None) -> str | None:
    """Return None if the bio looks like platform copy; otherwise the original bio."""
    if is_platform_boilerplate(bio, username, site):
        return None
    return bio
