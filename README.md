# AliasGraph

OSINT username permutation and explainable account-attribution tool. See [ITER1.md](ITER1.md) (v0.1 spec) and [ITER2.md](ITER2.md) (v0.2 spec) for the full design.

## Status

**v0.2** — full pipeline:

1. Generate likely username variants from seed + identity hints.
2. Concurrent existence checks across **1413 sites** (vendored from [maigret](https://github.com/soxoj/maigret), MIT — see `src/aliasgraph/resources/SITES_NOTICE.md`).
3. Profile scraping — GitHub / Reddit / Dev.to via JSON APIs, all other sites via a generic HTML scraper (OpenGraph + JSON-LD `Person.sameAs` + `<link rel="me">`).
4. Cross-platform link extraction — bio URLs, dedicated link fields, IndieWeb `rel=me`. Each link is parsed against a canonical host map into `(platform, handle)` pointers.
5. **Auto-follow** at depth 1 — extracted handles become new seeds for a second-pass scan.
6. Pairwise scoring with explicit evidence — mutual cross-link → ≥99% confidence; one-way cross-link → strong boost; bio / display-name / location / username / link-overlap each contribute weighted similarity.
7. Connected-component clustering on edges above the likely-threshold (default 0.75).
8. Live progress for both scan and scrape phases. JSON or terminal report.

Optional `[ml]` extra adds sentence-transformer bio embeddings behind `--use-embeddings` for higher-quality bio similarity.

## Install

```bash
uv venv --python 3.14.4
uv pip install -e '.[dev]'
# optional, for --use-embeddings:
uv pip install -e '.[dev,ml]'
```

## Usage

```bash
# how many sites are available
uv run aliasgraph list-sites

# typical: scrape, follow links, cluster, write JSON
uv run aliasgraph scan gvanrossum --site-limit 100 --output report.json --format json

# fast smoke
uv run aliasgraph scan torvalds --site-limit 60 --max-candidates 1

# with identity hints + suffixes
uv run aliasgraph scan torvalds \
    --first-name Linus --last-name Torvalds \
    --alias ltorvalds --numeric-suffix 91 \
    --site-limit 300 --max-candidates 20 --concurrency 80

# limit to specific platforms
uv run aliasgraph scan torvalds --platform GitHub --platform Reddit

# no scraping (v0.1-style existence-only output)
uv run aliasgraph scan torvalds --no-scrape --no-cluster

# embeddings-backed bio similarity
uv run aliasgraph scan torvalds --site-limit 100 --use-embeddings
```

### Flags

Discovery / scanning:
- `--max-candidates N` — cap generated username variants (default 30)
- `--site-limit N` — cap sites scanned, 0 = all (default 0)
- `--concurrency N` — parallel HTTP requests (default 50)
- `--timeout SECS` — per-request timeout (default 8)
- `--platform NAME` — repeatable; restrict to specific sites
- `--first-name`, `--last-name`, `--alias`, `--numeric-suffix` — identity hints

Scrape / cluster:
- `--scrape / --no-scrape` (default on)
- `--follow-links / --no-follow-links` — second-pass scan on extracted handles (default on)
- `--max-link-depth N` (default 1)
- `--cluster / --no-cluster` (default on)
- `--likely-threshold FLOAT` — minimum pairwise score to draw a cluster edge (default 0.75)
- `--use-embeddings` — enable sentence-transformers bio similarity (requires `[ml]` extra)

Output:
- `--format terminal|json`, `--output PATH`, `--quiet`

## Scoring intuition

| Evidence | Effect |
| --- | --- |
| Mutual cross-link (A links B, B links A) | floor at **0.99** |
| One-way cross-link | weighted score + 0.20 boost (capped at 0.95) |
| Identical / shared link in profile bios | weighted via Jaccard (weight 0.25) |
| Same display name | weight 0.15 |
| Similar bio (rapidfuzz token-set or embeddings) | weight 0.20 |
| Similar usernames | weight 0.20 |
| Same location | weight 0.05 |

Generic bio tokens (`developer`, `founder`, `student`, …) are penalized so two profiles that just say "developer" don't cluster together.

Each cluster comes with an evidence list explaining *why* its members were grouped.

## Test

```bash
uv run pytest -q
```

## Limitations

- Sites that need JavaScript or login walls (Twitter/X, Instagram, LinkedIn for non-public bios) usually return a generic page; the generic scraper still extracts what it can but cross-links from those pages are usually corporate, not user-owned.
- The vendored maigret site DB is noisy: some sites return false positives (e.g. Bit.ly's `not_found` rule is loose). Errors and unreachable sites are reported separately in `errored_sites`, not silently dropped.
- Caching, robots.txt enforcement, avatar perceptual hashing, and HTML/Markdown reports are deferred.
