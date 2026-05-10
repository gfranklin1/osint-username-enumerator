from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from aliasgraph.clustering import build_clusters
from aliasgraph.models import (
    Cluster,
    PlatformConfig,
    Profile,
    ScanResult,
    SiteError,
)
from aliasgraph.permutations import generate
from aliasgraph.platforms import filter_sites, load_all_sites
from aliasgraph.scanning import scan as run_scan
from aliasgraph.scanning.scanner import ProgressCallback as ScanCB
from aliasgraph.scraping import scrape_all
from aliasgraph.scraping.base import ScrapeCallback
from aliasgraph.scraping.validation import (
    dedupe_signature,
    is_garbled_profile,
    profile_quality,
)

# Trigger registration of site-specific scrapers.
import aliasgraph.scraping.sites  # noqa: F401


@dataclass
class PipelineConfig:
    seed: str
    first_name: str | None = None
    last_name: str | None = None
    aliases: list[str] = field(default_factory=list)
    numeric_suffixes: list[str] = field(default_factory=list)
    max_candidates: int = 30
    platform_filter: list[str] = field(default_factory=list)
    site_limit: int = 0
    timeout: float = 8.0
    concurrency: int = 50
    scrape: bool = True
    avatar_hash: bool = True
    follow_links: bool = True
    max_link_depth: int = 1
    cluster: bool = True
    likely_threshold: float = 0.75
    use_embeddings: bool = False
    quality_threshold: float = 0.30  # below this, profile is "unverified" and skipped from clustering


@dataclass
class PipelineCallbacks:
    on_scan_progress: ScanCB | None = None
    on_scrape_progress: ScrapeCallback | None = None
    on_status: Callable[[str], None] | None = None


def _status(cbs: PipelineCallbacks, msg: str) -> None:
    if cbs.on_status:
        cbs.on_status(msg)


async def run(cfg: PipelineConfig, cbs: PipelineCallbacks | None = None) -> ScanResult:
    cbs = cbs or PipelineCallbacks()

    usernames = generate(
        cfg.seed,
        first=cfg.first_name,
        last=cfg.last_name,
        aliases=cfg.aliases,
        numeric_suffixes=cfg.numeric_suffixes,
        max_candidates=cfg.max_candidates,
    )

    all_sites = load_all_sites()
    sites = filter_sites(
        all_sites,
        names=cfg.platform_filter or None,
        limit=cfg.site_limit if cfg.site_limit > 0 else None,
    )
    if not sites:
        return ScanResult(seed=cfg.seed, generated_usernames=usernames, profiles=[])

    _status(cbs, f"Scanning {len(usernames)} variants × {len(sites)} sites …")
    profiles, errors = await run_scan(
        usernames,
        sites,
        timeout=cfg.timeout,
        concurrency=cfg.concurrency,
        progress_cb=cbs.on_scan_progress,
    )

    if cfg.scrape and profiles:
        _status(cbs, f"Scraping {len(profiles)} profiles …")
        enriched, scrape_errors = await scrape_all(
            profiles,
            timeout=cfg.timeout,
            enable_avatar_hash=cfg.avatar_hash,
            progress_cb=cbs.on_scrape_progress,
        )
        profiles = enriched
        errors.extend(scrape_errors)

        if cfg.follow_links and cfg.max_link_depth > 0:
            profiles, follow_errors = await _follow_pass(
                profiles,
                all_sites,
                cfg,
                cbs,
                already_scanned=_seen_pairs(sites, usernames, profiles),
            )
            errors.extend(follow_errors)

    # Compute quality + dedupe near-identical false-positive landings.
    profiles = _annotate_quality(profiles)
    profiles = _dedupe_landing_pages(profiles)

    verified = [p for p in profiles if p.quality >= cfg.quality_threshold]
    unverified = [p for p in profiles if p.quality < cfg.quality_threshold]

    embedder = None
    if cfg.use_embeddings:
        from aliasgraph.scoring.embeddings import SentenceTransformerEmbedder
        _status(cbs, "Loading sentence-transformer model …")
        embedder = SentenceTransformerEmbedder()

    clusters: list[Cluster] = []
    if cfg.cluster and len(verified) >= 2:
        _status(
            cbs,
            f"Scoring {len(verified)} verified profiles "
            f"({len(unverified)} weak hits skipped) and clustering …",
        )
        clusters = build_clusters(
            verified,
            threshold=cfg.likely_threshold,
            embedder=embedder,
        )

    return ScanResult(
        seed=cfg.seed,
        generated_usernames=usernames,
        profiles=verified,
        errored_sites=errors,
        clusters=clusters,
        unverified_profiles=unverified,
    )


def _annotate_quality(profiles: list[Profile]) -> list[Profile]:
    out: list[Profile] = []
    for p in profiles:
        if is_garbled_profile(p):
            out.append(p.model_copy(update={"quality": 0.0}))
            continue
        q = profile_quality(p)
        out.append(p.model_copy(update={"quality": round(q, 3)}))
    return out


def _dedupe_landing_pages(profiles: list[Profile]) -> list[Profile]:
    """Collapse profiles whose (display, bio, avatar) signature is identical.

    Per-region clones of the same site (e.g. OP.GG LoL Korea / Europe / etc.)
    return the same generic landing page for any username — keep only the
    first to avoid bloating clusters and reports.
    """
    seen: dict[tuple[str, str, str], Profile] = {}
    out: list[Profile] = []
    for p in profiles:
        sig = dedupe_signature(p)
        # Only dedupe when at least display+bio carry meaningful content.
        if not sig[0] or not sig[1]:
            out.append(p)
            continue
        if sig in seen:
            continue
        seen[sig] = p
        out.append(p)
    return out


def _seen_pairs(
    sites: list[PlatformConfig],
    usernames: list[str],
    profiles: list[Profile],
) -> set[tuple[str, str]]:
    """All (site, username) pairs we've already swept this run.

    Includes every (scanned_site × generated_username) combination — the
    initial scan tried *all* of those, not just the ones where a profile was
    found — plus the verified profiles themselves (their usernames may not be
    in `usernames` if they came in via a previous follow-pass).
    """
    seen = {(p.site.lower(), p.username.lower()) for p in profiles}
    seen.update((s.name.lower(), u.lower()) for s in sites for u in usernames)
    return seen


async def _follow_pass(
    profiles: list[Profile],
    all_sites: list[PlatformConfig],
    cfg: PipelineConfig,
    cbs: PipelineCallbacks,
    already_scanned: set[tuple[str, str]],
) -> tuple[list[Profile], list[SiteError]]:
    by_site: dict[str, set[str]] = {}
    for p in profiles:
        for h in p.extracted_handles:
            key = (h.site.lower(), h.handle.lower())
            if key in already_scanned:
                continue
            by_site.setdefault(h.site, set()).add(h.handle)

    if not by_site:
        return profiles, []

    site_index = {s.name.lower(): s for s in all_sites}
    targets: list[tuple[PlatformConfig, list[str]]] = []
    for site_name, handles in by_site.items():
        cfg_site = site_index.get(site_name.lower())
        if cfg_site is None:
            continue
        targets.append((cfg_site, sorted(handles)))

    if not targets:
        return profiles, []

    _status(cbs, f"Following {sum(len(h) for _, h in targets)} cross-platform link(s) …")
    new_errors: list[SiteError] = []
    new_profiles: list[Profile] = []

    for cfg_site, handles in targets:
        prof, errs = await run_scan(
            handles,
            [cfg_site],
            timeout=cfg.timeout,
            concurrency=cfg.concurrency,
        )
        new_profiles.extend(prof)
        new_errors.extend(errs)

    if new_profiles and cfg.scrape:
        scraped, scrape_errors = await scrape_all(
            new_profiles, timeout=cfg.timeout, enable_avatar_hash=cfg.avatar_hash
        )
        new_profiles = scraped
        new_errors.extend(scrape_errors)

    # Merge, dedupe by key
    keyed = {p.key(): p for p in profiles}
    for p in new_profiles:
        keyed.setdefault(p.key(), p)
    return sorted(keyed.values(), key=lambda p: p.key()), new_errors
