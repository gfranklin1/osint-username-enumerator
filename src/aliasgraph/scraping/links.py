from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from aliasgraph.models import ExtractedHandle

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

_TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "ref",
    "ref_src",
    "igshid",
    "mc_cid",
    "mc_eid",
    "yclid",
    "msclkid",
    "_hsenc",
    "_hsmi",
}
_TRACKING_PREFIXES = ("utm_",)
_REJECT_SCHEMES = {"javascript", "mailto", "data", "tel"}


def normalize(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip().rstrip(".,;:)!?]\"'")
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if not parsed.scheme or parsed.scheme.lower() in _REJECT_SCHEMES:
        return None
    if parsed.scheme.lower() not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/") or "/"
    qs = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k not in _TRACKING_PARAMS and not any(k.startswith(p) for p in _TRACKING_PREFIXES)
    ]
    qs.sort()
    return urlunparse(
        (parsed.scheme.lower(), netloc, path, "", urlencode(qs), "")
    )


def extract_urls_from_text(text: str | None) -> list[str]:
    if not text:
        return []
    raw = URL_RE.findall(text)
    out: list[str] = []
    seen: set[str] = set()
    for r in raw:
        n = normalize(r)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


# Hostname → (canonical platform name, path regex with named "handle" group).
LINK_HOST_MAP: dict[str, tuple[str, re.Pattern[str]]] = {
    "github.com":        ("GitHub",      re.compile(r"^/(?P<handle>[^/]+)/?$")),
    "gist.github.com":   ("GitHubGist",  re.compile(r"^/(?P<handle>[^/]+)/?$")),
    "twitter.com":       ("Twitter",     re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "x.com":             ("Twitter",     re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "linkedin.com":      ("LinkedIn",    re.compile(r"^/in/(?P<handle>[^/?#]+)/?$")),
    "reddit.com":        ("Reddit",      re.compile(r"^/(?:user|u)/(?P<handle>[^/?#]+)/?$")),
    "old.reddit.com":    ("Reddit",      re.compile(r"^/(?:user|u)/(?P<handle>[^/?#]+)/?$")),
    "instagram.com":     ("Instagram",   re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "dev.to":            ("Dev.to",      re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "facebook.com":      ("Facebook",    re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "youtube.com":       ("YouTube",     re.compile(r"^/(?:@|c/|user/|channel/)(?P<handle>[^/?#]+)/?$")),
    "tiktok.com":        ("TikTok",      re.compile(r"^/@(?P<handle>[^/?#]+)/?$")),
    "bsky.app":          ("Bluesky",     re.compile(r"^/profile/(?P<handle>[^/?#]+)/?$")),
    "threads.net":       ("Threads",     re.compile(r"^/@(?P<handle>[^/?#]+)/?$")),
    "medium.com":        ("Medium",      re.compile(r"^/@(?P<handle>[^/?#]+)/?$")),
    "twitch.tv":         ("Twitch",      re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "gitlab.com":        ("GitLab",      re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "codeberg.org":      ("Codeberg",    re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "bitbucket.org":     ("Bitbucket",   re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "keybase.io":        ("Keybase",     re.compile(r"^/(?P<handle>[^/?#]+)/?$")),
    "news.ycombinator.com": ("HackerNews", re.compile(r"^/user/?$")),  # ?id= in query, handled below
    "mastodon.social":   ("Mastodon",    re.compile(r"^/@(?P<handle>[^/?#]+)/?$")),
    "fosstodon.org":     ("Mastodon",    re.compile(r"^/@(?P<handle>[^/?#]+)/?$")),
    "hachyderm.io":      ("Mastodon",    re.compile(r"^/@(?P<handle>[^/?#]+)/?$")),
}


def parse_handle(url: str) -> ExtractedHandle | None:
    n = normalize(url)
    if not n:
        return None
    parsed = urlparse(n)
    host = parsed.netloc
    entry = LINK_HOST_MAP.get(host)
    if not entry:
        return None
    site, pattern = entry
    # Special case: HackerNews uses ?id=
    if host == "news.ycombinator.com":
        qs = dict(parse_qsl(parsed.query))
        h = qs.get("id")
        if not h:
            return None
        return ExtractedHandle(site=site, handle=h, source_url=n)
    m = pattern.match(parsed.path or "/")
    if not m:
        return None
    handle = m.group("handle")
    if not handle or handle.lower() in {"about", "privacy", "terms", "login", "signup"}:
        return None
    return ExtractedHandle(site=site, handle=handle, source_url=n)


def parse_handles(urls: Iterable[str]) -> list[ExtractedHandle]:
    out: list[ExtractedHandle] = []
    seen: set[tuple[str, str]] = set()
    for u in urls:
        h = parse_handle(u)
        if h is None:
            continue
        key = (h.site.lower(), h.handle.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    return out


def twitter_url(handle: str) -> str:
    return f"https://twitter.com/{handle.lstrip('@')}"


def github_url(handle: str) -> str:
    return f"https://github.com/{handle}"
