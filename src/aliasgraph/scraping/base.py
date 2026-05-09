from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

from aliasgraph.models import Profile, SiteError
from aliasgraph.scanning.scanner import USER_AGENT, _error_reason

DEFAULT_PER_HOST = 4
DEFAULT_SCRAPE_TIMEOUT = 10.0
MAX_BODY_BYTES = 1_048_576  # 1 MiB


@dataclass
class ScrapeProgress:
    total: int
    done: int = 0
    enriched: int = 0
    failed: int = 0
    current: str = ""


ScrapeCallback = Callable[[ScrapeProgress], None]


class ProfileScraper(Protocol):
    site: str

    async def scrape(self, profile: Profile, client: httpx.AsyncClient) -> Profile: ...


_REGISTRY: dict[str, ProfileScraper] = {}


def register(scraper: ProfileScraper) -> None:
    _REGISTRY[scraper.site.lower()] = scraper


def get_scraper(site: str) -> ProfileScraper | None:
    return _REGISTRY.get(site.lower())


async def fetch_text(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    accept: str = "*/*",
    timeout: float = DEFAULT_SCRAPE_TIMEOUT,
) -> tuple[int, str, str]:
    """GET a URL with body cap. Returns (status, final_url, text)."""
    h = {"User-Agent": USER_AGENT, "Accept": accept}
    if headers:
        h.update(headers)
    async with client.stream("GET", url, headers=h, follow_redirects=True, timeout=timeout) as r:
        chunks: list[bytes] = []
        size = 0
        async for chunk in r.aiter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BODY_BYTES:
                break
        body = b"".join(chunks)
        try:
            text = body.decode(r.encoding or "utf-8", errors="replace")
        except LookupError:
            text = body.decode("utf-8", errors="replace")
        return r.status_code, str(r.url), text


async def scrape_all(
    profiles: Iterable[Profile],
    *,
    timeout: float = DEFAULT_SCRAPE_TIMEOUT,
    per_host: int = DEFAULT_PER_HOST,
    enable_generic: bool = True,
    enable_avatar_hash: bool = True,
    progress_cb: ScrapeCallback | None = None,
) -> tuple[list[Profile], list[SiteError]]:
    """Run the appropriate scraper for each profile in parallel, with per-host limits."""
    from aliasgraph.scraping.generic import GenericHTMLScraper  # avoid cycle

    profiles = list(profiles)
    enriched_out: list[Profile] = []
    errors: list[SiteError] = []
    progress = ScrapeProgress(total=len(profiles))

    host_sems: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(per_host))
    generic = GenericHTMLScraper() if enable_generic else None

    limits = httpx.Limits(max_connections=per_host * 8, max_keepalive_connections=per_host * 4)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:

        async def task(p: Profile) -> None:
            scraper = get_scraper(p.site) or generic
            if scraper is None:
                enriched_out.append(p)
                progress.done += 1
                if progress_cb is not None:
                    progress_cb(progress)
                return
            host = urlparse(str(p.url)).netloc.lower()
            sem = host_sems[host]
            progress.current = f"{p.site}/{p.username}"
            async with sem:
                try:
                    enriched = await scraper.scrape(p, client)
                    enriched_out.append(enriched)
                    if enriched is not p and (
                        enriched.bio or enriched.display_name or enriched.links
                    ):
                        progress.enriched += 1
                except Exception as exc:  # never raise out
                    enriched_out.append(p)
                    errors.append(
                        SiteError(
                            site=p.site,
                            username=p.username,
                            reason=f"scrape_{_error_reason(exc)}",
                        )
                    )
                    progress.failed += 1
            progress.done += 1
            if progress_cb is not None:
                progress_cb(progress)

        await asyncio.gather(*(task(p) for p in profiles))

        if enable_avatar_hash:
            from aliasgraph.scraping.avatar import populate_avatar_hashes
            enriched_out = await populate_avatar_hashes(enriched_out, client)

    enriched_out.sort(key=lambda p: (p.site.lower(), p.username))
    return enriched_out, errors
