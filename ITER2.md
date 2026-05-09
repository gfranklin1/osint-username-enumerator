# AliasGraph v0.2 — Profile Scraping & Link Extraction

> **Status:** design only. v0.1 (existence checks across the vendored maigret site DB) is implemented. This document describes the next iteration; no code in `src/` reflects it yet.

---

## 1. Goals

When the scanner confirms a profile exists, AliasGraph should:

1. **Enrich the `Profile`** — fill the currently-empty fields on `src/aliasgraph/models.py` (`display_name`, `bio`, `location`, `avatar_url`, `created_at`, `followers`, `following`).
2. **Extract every outbound link** the user advertises on that profile — bio URLs, dedicated link fields (e.g. GitHub `blog`, Dev.to `website_url`), `<link rel="me">`, OpenGraph `og:url`, and JSON-LD `sameAs`.
3. **Normalize and dedupe** those links so the v0.3 scorer can compute link-overlap and so v0.2 can already produce statements like "GitHub profile links to LinkedIn profile X".

The motivating use case: a GitHub user has a Twitter handle in their bio. v0.2 must capture that link, parse it as `(site=Twitter, handle=…)`, and store it on the `Profile`. v0.3 then turns that into evidence; v0.2 just records it.

---

## 2. Pipeline placement

```
existence checks  →  ProfileScraper (v0.2)  →  feature extractor (v0.3)
[scanner.py]         [scraping/*]               [scoring/*]
```

Each `Profile` returned from `aliasgraph.scanning.scanner.scan` is fed through a scraper. The scraper returns a new (enriched) `Profile`. Errors do not propagate — they become `SiteError` entries (model already exists at `src/aliasgraph/models.py`).

---

## 3. Scraper interface

```python
from typing import Protocol
import httpx
from aliasgraph.models import Profile

class ProfileScraper(Protocol):
    site: str  # must equal PlatformConfig.name

    async def scrape(self, profile: Profile, client: httpx.AsyncClient) -> Profile: ...
```

A registry maps `site → scraper`. Anything not registered falls back to `GenericHTMLScraper`.

```python
SCRAPERS: dict[str, ProfileScraper] = {}

def register(scraper: ProfileScraper) -> None:
    SCRAPERS[scraper.site] = scraper

def get_scraper(site: str) -> ProfileScraper:
    return SCRAPERS.get(site, GENERIC_SCRAPER)
```

---

## 4. Per-site strategies

| Site             | Method                                                              | Fields captured                                                                                                            |
| ---------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **GitHub**       | `GET https://api.github.com/users/{username}` (unauth, 60 req/hr/IP) | `name`, `bio`, `location`, `blog`, `twitter_username`, `company`, `created_at`, `followers`, `following`, `avatar_url`     |
| **Reddit**       | `GET https://www.reddit.com/user/{username}/about.json`              | `subreddit.public_description` (bio), `created_utc`, `link_karma`, `icon_img` (avatar). No structured link field — regex.  |
| **Dev.to**       | `GET https://dev.to/api/users/by_username?url={username}`            | `summary`, `location`, `website_url`, `twitter_username`, `github_username`, `joined_at`, `profile_image`                  |
| **everything else** | `GenericHTMLScraper` (HTML fallback)                              | `<title>`, `<meta name=description>`, `og:title`, `og:description`, `og:image`, `og:url`, `<link rel="me">`, JSON-LD `Person` |

The generic scraper uses `selectolax` (fast) or `beautifulsoup4` for parsing. JSON-LD blocks are parsed with `json.loads`; we look for objects whose `@type` is `"Person"` or contains `"Person"`, then read `name`, `description`, `url`, and `sameAs`.

Adding a new site-specific scraper is a single file under `src/aliasgraph/scraping/sites/{site}.py` plus a `register(...)` call.

---

## 5. Link extraction strategy

Run in this order, accumulate, then normalize:

1. **Site-specific fields.** Each per-site scraper knows its own link fields:
   - GitHub: `blog`, `twitter_username` → `https://twitter.com/{handle}`.
   - Dev.to: `website_url`, `github_username`, `twitter_username`, `mastodon_url`.
   - Reddit: none structured — fall through to bio regex.
2. **Bio / description regex sweep.**
   - URL regex: `https?://[^\s<>"]+`.
   - Bare handles: `@[A-Za-z0-9_]+` (low-confidence; only kept if context suggests a known platform — e.g. "twitter: @foo").
   - Known shorteners (`bit.ly`, `t.co`, `tinyurl.com`, `lnkd.in`) — flag for optional resolution.
3. **HTML fallback signals.**
   - `<a rel="me" href="…">` — IndieWeb identity links.
   - JSON-LD `sameAs` arrays.
   - `<meta property="og:see_also" content="…">`.

All matches go into a single list before normalization.

---

## 6. Link normalization

```python
def normalize(url: str) -> str | None: ...
```

Steps:

1. Lowercase scheme and host.
2. Strip tracking query params: `utm_*`, `fbclid`, `gclid`, `ref`, `igshid`, `mc_cid`, `mc_eid`.
3. Drop fragment (`#…`).
4. Trim trailing slash from path.
5. Reject obvious junk: `javascript:`, `mailto:` (handled separately), data URIs, internal anchors.
6. Optionally resolve shorteners by issuing a `HEAD` and following the `Location` (gated behind `--resolve-shorteners`, off by default — adds latency and an extra request).

After normalization, dedupe with a `set` while preserving insertion order.

### Host → platform mapping

A small table maps known hostnames back to canonical platform names from the maigret DB:

```python
LINK_HOST_MAP = {
    "github.com":     ("GitHub",   r"^/(?P<handle>[^/]+)/?$"),
    "twitter.com":    ("Twitter",  r"^/(?P<handle>[^/]+)/?$"),
    "x.com":          ("Twitter",  r"^/(?P<handle>[^/]+)/?$"),
    "linkedin.com":   ("LinkedIn", r"^/in/(?P<handle>[^/]+)/?$"),
    "reddit.com":     ("Reddit",   r"^/(?:user|u)/(?P<handle>[^/]+)/?$"),
    "instagram.com":  ("Instagram",r"^/(?P<handle>[^/]+)/?$"),
    "dev.to":         ("Dev.to",   r"^/(?P<handle>[^/]+)/?$"),
    "mastodon.social":("Mastodon", r"^/@(?P<handle>[^/]+)/?$"),
    # …expand as needed
}
```

Reuse `aliasgraph.platforms.load_all_sites()` to validate the canonical platform name actually exists in the loaded DB.

---

## 7. Cross-platform link graph (motivating example)

Concrete walkthrough:

```
seed: torvalds
v0.1 finds:    GitHub:torvalds
v0.2 scrapes GitHub:
    bio       = "Linux kernel"
    blog      = "https://www.linuxfoundation.org/about/people/board/"
    twitter   = "Linus__Torvalds"
v0.2 normalizes links →
    https://www.linuxfoundation.org/about/people/board
    https://twitter.com/linus__torvalds        ← matches LINK_HOST_MAP
v0.2 emits extracted_handles = [("Twitter", "Linus__Torvalds")]
```

The Twitter pointer is *evidence* (consumed by v0.3 scorer) and a *seed candidate* (consumed by v0.2's optional follow-pass — see §11).

---

## 8. Profile schema deltas

`Profile` already has every primitive field needed (see `src/aliasgraph/models.py:18`). One small addition is recommended for v0.2:

```python
class ExtractedHandle(BaseModel):
    site: str          # canonical platform name
    handle: str
    source_url: str    # the original link this was derived from

class Profile(BaseModel):
    # …existing fields…
    extracted_handles: list[ExtractedHandle] = []
```

Rationale: keeping `links` as raw URLs and `extracted_handles` as parsed pointers is cleaner than overloading either, and `extracted_handles` is what the v0.3 scorer and the optional follow-pass consume directly.

---

## 9. Caching

- On-disk cache under `~/.cache/aliasgraph/` (override with `--cache-dir`).
- Key: `sha1(f"{site}:{username}:{schema_version}")`.
- Value: pickled or JSON-serialized `Profile`.
- TTL: 24 hours by default; bypass with `--no-cache`.
- Cache key includes a `schema_version` constant so a model change invalidates old entries automatically.

---

## 10. Rate limiting & politeness

- Per-host `asyncio.Semaphore` (default 4) layered on top of the global concurrency limit already present in `scanner.py`.
- Honor `Retry-After` header on 429 — sleep, retry once, then give up.
- Respect `robots.txt` in the generic scraper (default on; flag to disable). Site-specific scrapers using documented APIs (GitHub, Reddit, Dev.to) bypass this — those endpoints are explicitly public.
- Reuse `USER_AGENT` from `src/aliasgraph/scanning/scanner.py`.
- Never log scraped HTML to disk except under `--debug-dump`.

---

## 11. CLI changes (preview)

```
--scrape / --no-scrape          enrich profiles (default: on once shipped)
--follow-links                  feed extracted handles back into a 2nd scan pass
--max-link-depth N              cap follow-link recursion (default: 1)
--no-cache                      bypass the on-disk cache
--cache-dir PATH                override cache location
--resolve-shorteners            HEAD-follow bit.ly / t.co / etc.
--debug-dump PATH               write raw HTML/JSON for failed scrapes
```

`--follow-links` is the feature that turns AliasGraph from "username sweeper" into "identity walker": v0.1 finds GitHub:torvalds, v0.2 sees the Twitter link in the bio, the follow-pass adds `Linus__Torvalds` as a new seed for the scanner, and the next sweep discovers the Twitter profile.

---

## 12. Error handling

A scraper must never raise. Failure modes and their `SiteError.reason` values:

- `scrape_timeout` — request timed out.
- `scrape_http_4xx` / `scrape_http_5xx` — non-success status.
- `scrape_parse_failed` — HTML / JSON parser raised.
- `scrape_rate_limited` — saw 429, retry budget exhausted.
- `scrape_robots_disallowed` — robots.txt forbids fetching.

On any failure the original (unenriched) `Profile` is returned and a `SiteError` is appended to `ScanResult.errored_sites` (model already exists at `src/aliasgraph/models.py:34`).

---

## 13. Testing strategy

Layout:

```
tests/
├── fixtures/
│   └── scrapers/
│       ├── github/torvalds.json
│       ├── reddit/spez.json
│       ├── devto/ben.json
│       └── generic/og_tags.html
├── test_scrape_github.py
├── test_scrape_reddit.py
├── test_scrape_devto.py
├── test_scrape_generic.py
├── test_link_normalize.py
└── test_link_host_map.py
```

- Each per-site test loads a fixture, runs the scraper with a mocked `httpx` transport, asserts the `Profile` fields and `extracted_handles`.
- `test_link_normalize.py` is table-driven: input URL → expected canonical URL.
- `test_link_host_map.py` covers the canonical-platform parser.

No live network in tests — everything uses `httpx.MockTransport`.

---

## 14. Out of scope (deferred)

- **Avatar perceptual hashing** — `--use-avatar-hash` is a v0.4 feature.
- **Bio / description embedding similarity** — v0.4.
- **Scoring & clustering** — v0.3 (consumes the data v0.2 produces).
- **Authenticated API access** — GitHub PAT, Reddit OAuth, etc. v0.2 stays unauthenticated; rate limits are tolerable for typical scan sizes.
- **Browser automation** — anything requiring JavaScript stays in the "skip" bucket until a future iteration that opts into Playwright.

---

## 15. Open questions

- Should shortener resolution be on by default? Trade latency for completeness.
- Persist a separate `links.jsonl` per scan (one row per link) for easy grepping, or keep links nested inside `report.json` only?
- How aggressive should bare-handle extraction be? `@foo` in a bio is highly ambiguous without surrounding "twitter:" / "instagram:" context.
- For the generic scraper, do we cap response body size (e.g. 1 MiB) to bound memory on hostile pages?

---

## 16. Acceptance criteria for v0.2

- `aliasgraph scan torvalds --site-limit 50 --scrape` produces a `report.json` where the GitHub `Profile` has populated `bio`, `location`, `created_at`, `followers`, and at least one entry in `extracted_handles`.
- Re-running the same command within 24 h is materially faster (cache hit).
- `aliasgraph scan torvalds --scrape --follow-links --max-link-depth 1` discovers at least one profile that did *not* appear in the first pass (i.e. came from a link extracted from the GitHub profile).
- `uv run pytest -q` covers all four scrapers + the link normalizer + the host map.
