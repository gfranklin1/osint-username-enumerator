"""Profile quality scoring.

Maigret's existence checks have a meaningful false-positive rate: many sites
return 200 OK with a generic landing page ("Channel Not Found", site marketing
copy, error pages with HTTP 200, etc.) when the requested username doesn't
exist. After scraping, we score each profile's "quality" — how much real
user-specific signal we recovered. Low-quality profiles are kept in the report
but excluded from clustering so they don't drag unrelated identities together
through the rare-username prior.
"""
from __future__ import annotations

import re

from aliasgraph.models import Profile
from aliasgraph.scraping.boilerplate import is_platform_boilerplate

# Display-name fragments that prove the page is an error / generic landing.
_INVALID_DISPLAY_FRAGMENTS = (
    "not found",
    "404",
    "page does not exist",
    "user does not exist",
    "no longer available",
    "no such user",
    "error",
    "channel not found",
    "doesn't exist",
    "couldn't be found",
    "couldn’t be found",
    "is not available",
    "deleted account",
    "private profile",
    "page restricted",
    "removed",
)

# Display-name fragments that are clearly the SITE name, not the user.
# When the display name is "{Brand} - {tagline}" or just the site title,
# the page rendered didn't actually surface user-specific info.
_SITE_TITLE_FRAGMENTS = (
    " — ",
    " :: ",
    " | ",
    " - the best",
    " - imagine",
    " - make your",
    " - live stream",
    " - homepage",
    " · ",
    "the magic of the internet",
    "yandex",
)


def looks_like_error_page(display: str | None) -> bool:
    if not display:
        return False
    d = display.lower()
    return any(frag in d for frag in _INVALID_DISPLAY_FRAGMENTS)


def looks_like_site_title(display: str | None, site: str, username: str) -> bool:
    """True if the display name is the site's marketing title rather than user info."""
    if not display:
        return False
    d = display.strip()
    dl = d.lower()
    sl = site.lower()
    ul = username.lower()
    # Pure site name
    if dl == sl:
        return True
    # Starts with site name + dash/colon → marketing copy
    if dl.startswith(sl + " "):
        return True
    # Mentions username at all → likely user-specific even if formatted oddly
    if ul in dl:
        return False
    # Otherwise look for marketing fragments
    return any(frag in dl for frag in _SITE_TITLE_FRAGMENTS)


def profile_quality(p: Profile) -> float:
    """Return a score in [0, 1] estimating how much real user signal exists."""
    if looks_like_error_page(p.display_name):
        return 0.0

    score = 0.0

    # Display name signal
    if p.display_name:
        d = p.display_name.strip()
        if looks_like_site_title(d, p.site, p.username):
            # Generic page title, doesn't prove user exists.
            pass
        elif p.username.lower() in d.lower():
            # "alice • Instagram" — references the user, weak but real signal
            score += 0.20
        else:
            # Real display name (e.g. "Garrett Franklin")
            score += 0.35

    # Real bio (not boilerplate, not just the site's marketing copy).
    if p.bio and not is_platform_boilerplate(p.bio, p.username, p.site):
        bio_l = p.bio.strip().lower()
        site_l = p.site.lower()
        looks_marketing = (
            site_l in bio_l
            and any(kw in bio_l for kw in (
                "the best", "the most", "the world", "discover ", "find the",
                "join over", "social platform", "is a portal", "is a free",
            ))
        )
        if not looks_marketing:
            score += 0.35 if len(p.bio.strip()) >= 30 else 0.15

    # Avatar — only counts when present (default avatars are deduped by URL anyway).
    if p.avatar_url:
        score += 0.10

    # Location field set
    if p.location:
        score += 0.10

    # Extracted outbound handles (a real user filled in their bio links)
    if p.extracted_handles:
        score += 0.20

    # Followers (some scrapers populate it)
    if p.followers is not None and p.followers > 0:
        score += 0.05

    # Created timestamp populated
    if p.created_at:
        score += 0.05

    return min(1.0, score)


def garbled_text(s: str | None) -> bool:
    """Detect text that's mostly replacement characters / unprintable noise."""
    if not s:
        return False
    if not s.strip():
        return False
    bad = sum(1 for c in s if c == "�" or (ord(c) < 32 and c not in "\n\r\t"))
    return bad / max(1, len(s)) >= 0.20


# Compatibility: also refuse profiles whose display/bio is mojibake noise.
def is_garbled_profile(p: Profile) -> bool:
    return garbled_text(p.display_name) or garbled_text(p.bio)


_DEFAULT_DUP_KEY = re.compile(r"\s+")


def dedupe_signature(p: Profile) -> tuple[str, str, str]:
    """Key for collapsing near-identical false-positive pages (e.g. 12 OP.GG regional landings)."""
    name = _DEFAULT_DUP_KEY.sub(" ", (p.display_name or "").strip().lower())
    bio = _DEFAULT_DUP_KEY.sub(" ", (p.bio or "").strip().lower())[:120]
    avatar = (p.avatar_url or "").lower()
    return (name, bio, avatar)
