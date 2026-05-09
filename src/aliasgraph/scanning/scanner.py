from __future__ import annotations

import asyncio
from collections.abc import Iterable

import httpx

from aliasgraph.models import PlatformConfig, Profile

USER_AGENT = "AliasGraph/0.1 (+https://github.com/jwihardi/osint-username-enumerator)"
DEFAULT_TIMEOUT = 10.0


def _is_found(resp: httpx.Response, cfg: PlatformConfig) -> bool:
    if resp.status_code in cfg.not_found_status_codes:
        return False
    if resp.status_code >= 400:
        return False
    if cfg.not_found_body_substrings:
        body = resp.text
        for needle in cfg.not_found_body_substrings:
            if needle in body:
                return False
    return True


async def _check_one(
    client: httpx.AsyncClient,
    cfg: PlatformConfig,
    username: str,
) -> Profile | None:
    url = cfg.profile_url.format(username=username)
    try:
        resp = await client.get(url, follow_redirects=True)
    except httpx.HTTPError:
        return None
    if not _is_found(resp, cfg):
        return None
    return Profile(site=cfg.name, url=str(resp.url), username=username)


async def _platform_worker(
    client: httpx.AsyncClient,
    cfg: PlatformConfig,
    usernames: list[str],
    results: list[Profile],
) -> None:
    for u in usernames:
        profile = await _check_one(client, cfg, u)
        if profile is not None:
            results.append(profile)
        await asyncio.sleep(cfg.rate_limit_seconds)


async def scan(
    usernames: Iterable[str],
    platforms: Iterable[PlatformConfig],
    timeout: float = DEFAULT_TIMEOUT,
) -> list[Profile]:
    usernames = list(usernames)
    platforms = list(platforms)
    results: list[Profile] = []
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        await asyncio.gather(
            *(_platform_worker(client, cfg, usernames, results) for cfg in platforms)
        )
    return results
