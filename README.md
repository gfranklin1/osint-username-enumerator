# AliasGraph

OSINT username permutation, profile scraping, and explainable account-attribution. Given a seed handle, AliasGraph generates likely username variants, checks them across ~1400 sites, scrapes the profiles it finds, follows cross-platform links, scores every pair of profiles using explainable similarity features, and clusters the ones that probably belong to the same person.

Two interfaces, one engine: a scriptable [CLI](#every-flag) for batch / pipeline use and an interactive [TUI](TUI.md) for hands-on investigation.

Design specs: [ITER1.md](ITER1.md) (v0.1) · [ITER2.md](ITER2.md) (v0.2) · [ITER3.md](ITER3.md) (v0.3 audit pass) · [TUI.md](TUI.md) (interactive UI).

---

## What it does

```
seed handle
   │
   ▼
[1] Permutation engine ──── username variants (with optional name / alias / suffix hints)
   │                        skips numeric-only bases; deterministic, bounded
   ▼
[2] Concurrent scanner ──── ~1400 sites (vendored from maigret, MIT)
   │     status_code / message / response_url checks
   ▼
[3] Profile scraper ─────── GitHub / Reddit / Dev.to via APIs;
   │                        all other sites via generic HTML (OpenGraph, JSON-LD, rel=me)
   │                        + avatar fetch + perceptual hash (pHash, SSRF-guarded)
   │                        + GitHub social_accounts → LinkedIn / Mastodon / etc.
   ▼
[4] Link extractor ──────── URL regex + LINK_HOST_MAP → (platform, handle)
   │                        IDN-canonicalized; reserved paths (/explore, /feed, …) rejected
   ▼
[5] Follow-pass ─────────── extracted handles become new seeds (depth 1)
   │
   ▼
[6] Pairwise scorer ─────── username / display / bio (rapidfuzz or embeddings) /
   │                        link overlap / location / avatar pHash / cross-link evidence
   │                        weighted average renormalized over present features only
   │                        + rare-username prior + boilerplate-bio filter
   ▼
[7] Core-pair clusterer ─── networkx + majority-admission so chain transitivity
   │                        doesn't collapse strangers; confidence + min_edge per cluster
   ▼
[8] Reporter ────────────── terminal (rich), JSON, or self-contained HTML (XSS-hardened)
```

---

## Install

Requires Python 3.14.

```bash
uv venv --python 3.14.4
uv pip install -e '.[dev]'
```

Optional extras (combine freely):

| Extra | Purpose |
| --- | --- |
| `[ml]` | sentence-transformers for higher-quality bio similarity. |
| `[tui]` | Textual-based interactive TUI (`aliasgraph tui`). |

```bash
# Everything:
uv pip install -e '.[dev,ml,tui]'
```

---

## Quick start

```bash
# How many sites are loaded?
uv run aliasgraph list-sites
# → 1413 sites loaded

# Quickest sweep (cap site count for speed)
uv run aliasgraph scan torvalds --site-limit 60

# Full sweep across every site
uv run aliasgraph scan torvalds

# Generate clickable browser report
uv run aliasgraph scan torvalds --site-limit 100 --format html --output report.html
xdg-open report.html

# Launch the interactive TUI
uv run aliasgraph tui
```

---

## Every flag

```
USAGE
  aliasgraph scan SEED [OPTIONS]
  aliasgraph tui                # interactive TUI (requires [tui] extra)
  aliasgraph list-sites

DISCOVERY (permutation engine)
  --first-name TEXT          Identity hint, used by the permutation engine.
  --last-name TEXT           Identity hint.
  --alias TEXT               Known additional handle. Repeatable.
  --numeric-suffix TEXT      Append e.g. 91 / 2005 to candidates. Repeatable.
                             Skipped for purely numeric bases (no "20052005").
  --max-candidates INT       Cap generated variants. Short-circuits inside the
                             generator — doesn't over-build then slice. (default: 30)

SCANNING (existence checks)
  --platform NAME            Restrict scan to a site by name. Repeatable.
  --site-limit INT           Scan at most N sites; 0 = all. (default: 0)
  --concurrency INT          Parallel HTTP requests. (default: 50)
  --timeout FLOAT            Per-request timeout in seconds. (default: 8.0)

SCRAPING (profile enrichment)
  --scrape / --no-scrape             Enrich found profiles. (default: on)
  --avatar-hash / --no-avatar-hash   Download + pHash avatars. SSRF-guarded:
                                     loopback / RFC1918 / cloud-metadata hosts
                                     are short-circuited before any HTTP call.
                                     (default: on)
  --follow-links / --no-follow-links Re-scan handles extracted from bios.
                                     (default: on)
  --max-link-depth INT               Cap follow-link recursion. (default: 1)

SCORING & CLUSTERING
  --cluster / --no-cluster   Build identity clusters. (default: on)
  --likely-threshold FLOAT   Minimum pairwise score for a cluster edge. (default: 0.75)
  --quality-threshold FLOAT  Minimum profile-quality score required for a profile
                             to participate in clustering. Lower = more matches +
                             more false positives. (default: 0.30)
  --use-embeddings           Use sentence-transformers for bio similarity.
                             Requires `aliasgraph[ml]` extra.

OUTPUT
  --format {terminal,json,html}   Report format. (default: terminal)
  --output PATH                   Write report to file. With --format terminal
                                  the format is inferred from the extension
                                  (.html → HTML, anything else → JSON).
  --quiet                         Suppress live progress bar.
  --debug                         Show full traceback on pipeline error
                                  (otherwise a one-line error + exit 1).
```

---

## TUI

```bash
uv pip install -e '.[tui]'   # one-time
uv run aliasgraph tui
```

Form → Running → Results screens with:
- Every CLI flag exposed as form fields / toggles.
- Live progress bars while the pipeline runs (existence checks + scraping).
- Browsable cluster tree on the left; member detail panel on the right.
- **Re-tune in place**: adjust `likely` / `quality` thresholds and re-cluster
  *without re-fetching* — uses the cached raw profile set with their per-profile
  quality scores intact.
- Save JSON / HTML directly from the results screen.

Bindings: `Ctrl+R` re-cluster · `N` new scan · `Esc` back · `Ctrl+Q` quit.

Full TUI documentation: **[TUI.md](TUI.md)**.

---

## Worked examples

### Find your own footprint, get a browser report

```bash
uv run aliasgraph scan myhandle \
  --first-name First --last-name Last \
  --format html --output report.html
```

### Fast smoke against a known account

```bash
uv run aliasgraph scan torvalds --site-limit 60 --max-candidates 1
```

### Full deep sweep with embeddings + JSON for downstream tooling

```bash
uv run aliasgraph scan torvalds --use-embeddings --format json --output torvalds.json
```

### Scan only specific platforms

```bash
uv run aliasgraph scan torvalds --platform GitHub --platform Reddit --platform Dev.to
```

### Try multiple identity variants

```bash
uv run aliasgraph scan jdoe \
  --first-name Jane --last-name Doe \
  --alias jdoe89 --alias janedoe \
  --numeric-suffix 89 --numeric-suffix 1995 \
  --max-candidates 50
```

### Existence-only scan (skip scraping/clustering)

```bash
uv run aliasgraph scan torvalds --no-scrape --no-cluster
```

### Disable expensive avatar fetching for speed

```bash
uv run aliasgraph scan torvalds --no-avatar-hash --no-follow-links
```

### Lower threshold to surface weaker matches

```bash
uv run aliasgraph scan torvalds --likely-threshold 0.6
```

### Strict mode — only cluster profiles with rich, validated content

```bash
uv run aliasgraph scan torvalds --quality-threshold 0.5
```

### Permissive mode — let bare URL hits cluster too

```bash
uv run aliasgraph scan torvalds --quality-threshold 0.10
```

### Pipe into jq

```bash
uv run aliasgraph scan torvalds --format json --quiet | jq '.clusters[].members'
```

### Debug a crash

```bash
uv run aliasgraph scan some-broken-handle --debug
```

### List sites in the database

```bash
uv run aliasgraph list-sites
```

---

## Output formats

| Flag | Goes to | Use when |
| --- | --- | --- |
| `--format terminal` (default) | stderr (rich panels) | Reading interactively. |
| `--format json` + `--output report.json` | file (UTF-8) | Feeding into another tool, archiving, diffing runs. |
| `--format html` + `--output report.html` | file | Sharing a clickable, dark-themed report. Single file, no external assets. URLs in `src=` / `href=` are scheme-validated to block `javascript:` / `data:` payloads in scraped content. |

---

## How scoring works

Pairwise scoring uses six base features whose weights sum to **exactly 1.0**, plus a separate one-way crosslink boost. Crucially, when a feature has no data on at least one side, it's **dropped from the average** (numerator and denominator) rather than counted as 0.0 — sparse profiles aren't silently penalized.

| Signal | Base weight | Notes |
| --- | --- | --- |
| Bio similarity | **0.21** | rapidfuzz token-set + Jaccard on non-generic tokens, or sentence-transformer cosine if `--use-embeddings`. Generic tokens (`developer`, `student`, …) are penalized. None when either bio is missing. |
| Link overlap | **0.21** | Jaccard over normalized outbound URLs. None when both sides have no links. |
| Avatar pHash similarity | **0.19** | Same image (Hamming ≤ 6 bits) → near-1.0. Identical avatars are very strong evidence. None when either avatar is missing. |
| Username string similarity | **0.18** | Catches near-but-not-exact variants (`jdoe` / `j_doe`). Always present. |
| Display name similarity | **0.16** | rapidfuzz; falls back to username when display is missing. Always present. |
| Location similarity | **0.05** | Direct fuzzy match. None when either location is missing. |
| **One-way crosslink boost** | **+0.25** (additive, capped 0.95) | A links to B but B doesn't link back. |
| **Mutual crosslink** | **floor 0.99** | Profiles that link to each other are basically certain. |
| **Same exact rare username** | step **0.20–0.60** | Long, unusual handles ≥ 0.85 rarity get +0.60. Common handles (`ben`, `john`, `admin`) get nothing. **Requires corroboration** — see below. |

**Corroboration rule for the rare-username prior.** A long unique handle counts as evidence only when accompanied by at least one of: matching bio (≥0.40), matching display name (≥0.55), matching avatar (≥pHash floor), shared link, matching location (≥0.85), or any cross-link. **Without corroboration, the prior contributes zero** — two strangers sharing only an unusual handle never auto-cluster.

**Boilerplate bios are stripped.** Things like `"Imgur: The magic of the Internet"` or `"Trello is a collaboration tool"` are recognized as platform copy and removed before scoring. Real short bios (≥4 chars: `"Coder"`, `"CS dev"`) are kept — the prior 12-char minimum cut too many legit profiles.

**Profile quality filter.** After scraping, every profile is scored on signal richness (real display name, real bio, location, avatar, extracted links, follower count, …). Profiles below `--quality-threshold` (default 0.30) are excluded from clustering and reported separately as **weak hits** — sites that returned 200 OK with no real user-specific content (error pages like "Channel Not Found", site marketing copy, garbled mojibake). They still appear in the report so you can see them, but they don't drag unrelated identities together through the rare-username prior.

**Landing-page dedupe.** Profiles whose `(display_name, bio, avatar_url)` signature is identical are collapsed (e.g. `OP.GG LoL Korea / Europe / Brazil / …` all serve the same generic landing page → kept as one).

**Asserted accounts.** When a discovered profile (e.g. GitHub) advertises a handle on a platform that we couldn't directly verify (e.g. LinkedIn refuses unauthenticated lookups), the asserted handle still appears as a yellow row inside its cluster, tagged `asserted via GitHub:user`.

---

## How clustering works

1. Score every pair of discovered profiles.
2. Drop edges below `--likely-threshold` (default 0.75).
3. Sort surviving edges high-to-low.
4. Build clusters greedily by *core-pair seeding*: when admitting a new node, require it to score above threshold against a **majority** (≥50%) of existing members. This prevents `A↔B 0.80` and `B↔C 0.80` with `A↔C 0.20` from collapsing strangers into one identity.
5. Each cluster surfaces both `confidence` (mean of surviving edge scores) and `min_edge` (weakest pairwise score) — the gap between them flags transitive risk inside large clusters.
6. Cluster evidence is aggregated: rare-username consensus, display-name variants, longest bio, locations, outbound links, in-cluster cross-links — all reported once, not per-pair.

---

## Security posture

AliasGraph fetches and renders content from arbitrary public web pages. Two guards exist for the obvious risks:

- **SSRF (avatar fetch).** Before downloading any image, the URL is checked against an `is_safe_public_url()` filter that rejects `http`/`https` URLs whose host is loopback, RFC1918 private, link-local, or a known cloud-metadata endpoint (`169.254.169.254`, `metadata.google.internal`, `metadata.aws.amazon.com`, `*.local`, `*.internal`, `localhost`). Non-http(s) schemes are rejected outright. Tested in `tests/test_avatar_ssrf.py`.
- **XSS (HTML report).** Every URL emitted into `src=` or `href=` attributes is run through `_safe_url()`, which blanks anything that doesn't begin with `http://` or `https://` — `javascript:alert(1)` from a hostile `og:image` never reaches the DOM. Tested in `tests/test_html_report.py`.

---

## Test

```bash
uv run pytest -q     # 110 tests
uv run ruff check src tests
uv run --extra dev mypy src
```

The TUI smoke tests (`tests/test_tui.py`) skip automatically when the `[tui]` extra isn't installed.

---

## Limitations

- Sites that need JavaScript or login walls (Twitter/X, Instagram, LinkedIn for non-public bios) usually return generic pages; the generic scraper still extracts what it can but cross-links from those pages are often platform-corporate, not user-owned.
- The vendored maigret site DB is noisy: a few sites return false positives (e.g. Bit.ly's not-found rule is loose). All errors and unreachable sites are reported separately, not silently dropped.
- Authenticated API access (GitHub PAT, Reddit OAuth) is not used — rate limits are tolerable for typical scan sizes but unauthenticated GitHub will throttle at 60 req/hr/IP.
- Explicitly deferred (see [ITER3.md §6](ITER3.md)): on-disk caching, robots.txt enforcement, URL-shortener resolution, bare-handle (`@foo`) extraction from bios, `Retry-After` honoring on 429.

---

## Credits

Site database vendored from [maigret](https://github.com/soxoj/maigret) (MIT). See `src/aliasgraph/resources/SITES_NOTICE.md`.

TUI built on [Textual](https://textual.textualize.io/).
