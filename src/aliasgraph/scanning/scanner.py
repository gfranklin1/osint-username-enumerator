from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import httpx

from aliasgraph.models import PlatformConfig, Profile, SiteError

USER_AGENT = "AliasGraph/0.1 (+https://github.com/jwihardi/osint-username-enumerator)"
DEFAULT_TIMEOUT = 8.0
DEFAULT_CONCURRENCY = 50


@dataclass
class ScanProgress:
    total: int
    checked: int = 0
    found: int = 0
    errored: int = 0
    skipped: int = 0
    current: str = ""


ProgressCallback = Callable[[ScanProgress], None]


def _username_allowed(cfg: PlatformConfig, username: str) -> bool:
    if not cfg.regex_check:
        return True
    try:
        return re.search(cfg.regex_check, username) is not None
    except re.error:
        return True  # bad regex in DB — don't block


def _classify(resp: httpx.Response, cfg: PlatformConfig, requested_url: str) -> bool:
    """Return True if the response indicates the profile exists."""
    check = cfg.check_type
    if check == "status_code":
        return 200 <= resp.status_code < 300
    if check == "response_url":
        # found if the final URL still looks like the profile path (no redirect to home/login)
        return str(resp.url).rstrip("/") == requested_url.rstrip("/")
    # default: "message" — body must contain all presence_strings and none of absence_strings
    if resp.status_code >= 400:
        return False
    body = resp.text
    if cfg.absence_strings and any(s in body for s in cfg.absence_strings):
        return False
    if cfg.presence_strings and not all(s in body for s in cfg.presence_strings):
        return False
    return True


def _error_reason(exc: BaseException) -> str:
    if isinstance(exc, asyncio.TimeoutError | httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connection"
    if isinstance(exc, httpx.HTTPError):
        return type(exc).__name__
    return type(exc).__name__


async def _check_one(
    client: httpx.AsyncClient,
    cfg: PlatformConfig,
    username: str,
) -> tuple[Profile | None, SiteError | None]:
    if not _username_allowed(cfg, username):
        return None, None  # silently skipped — not an error
    url = cfg.profile_url.format(username=username)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", **cfg.headers}
    try:
        resp = await client.get(url, headers=headers, follow_redirects=True)
    except Exception as exc:  # network/timeout/etc
        return None, SiteError(site=cfg.name, username=username, reason=_error_reason(exc))
    if resp.status_code >= 500:
        return None, SiteError(site=cfg.name, username=username, reason=f"http_{resp.status_code}")
    try:
        if _classify(resp, cfg, url):
            return Profile(site=cfg.name, url=str(resp.url), username=username), None
    except Exception:
        return None, SiteError(site=cfg.name, username=username, reason="classify_failed")
    return None, None


async def scan(
    usernames: Iterable[str],
    platforms: Iterable[PlatformConfig],
    timeout: float = DEFAULT_TIMEOUT,
    concurrency: int = DEFAULT_CONCURRENCY,
    progress_cb: ProgressCallback | None = None,
) -> tuple[list[Profile], list[SiteError]]:
    usernames = list(usernames)
    platforms = list(platforms)
    profiles: list[Profile] = []
    errors: list[SiteError] = []

    progress = ScanProgress(total=len(usernames) * len(platforms))
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:

        async def task(cfg: PlatformConfig, u: str) -> None:
            async with sem:
                progress.current = f"{cfg.name}/{u}"
                profile, err = await _check_one(client, cfg, u)
                progress.checked += 1
                if profile is not None:
                    profiles.append(profile)
                    progress.found += 1
                elif err is not None:
                    errors.append(err)
                    progress.errored += 1
                else:
                    progress.skipped += 1
                if progress_cb is not None:
                    progress_cb(progress)

        await asyncio.gather(*(task(cfg, u) for cfg in platforms for u in usernames))

    profiles.sort(key=lambda p: (p.site.lower(), p.username))
    errors.sort(key=lambda e: (e.site.lower(), e.username))
    return profiles, errors
