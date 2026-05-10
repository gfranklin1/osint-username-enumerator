# AliasGraph v0.3 — Senior-Engineer Audit Pass

> **Status:** plan approved. Implementation underway. Each item below ships with its fix already designed; this document is the canonical record of what changed and why.

User-decided defaults baked in:
- Scope: comprehensive — bugs, security, accuracy, code smell.
- Scoring math: rebalance weights to sum to 1.0 + treat missing-data as missing (renormalize over present features).
- Privacy: replace user's real handle in tests with placeholder; keep public-figure fixtures.
- Boilerplate: drop bio min length 12 → 4.

---

## 1. Bugs (correctness)

### 1.1 `scraping/links.py:31` — trailing-paren strip eats legitimate URL chars
`url.strip().rstrip(".,;:)!?]\"'")` strips trailing `)` from URLs like `https://en.wikipedia.org/wiki/Foo_(bar)` when `normalize()` is called from per-site scrapers (which receive raw URLs from APIs/HTML attrs, not URL_RE matches).

**Fix:** restrict the rstrip to characters that are unambiguously sentence punctuation: `.,;:!?` only. Drop `)]\"'` — the URL_RE already excludes them at extraction time, and other call sites pass clean URLs.

### 1.2 `pipeline.py:184–188` — `_seen_pairs` builds wrong cartesian product
Comment claims "Track (site, username) we already swept", but the code uses `for p in profiles for u in usernames` — only sites where a profile was *found*, not all sites scanned. Follow-pass therefore re-scans 404'd sites for handles in our username list.

**Fix:** pass `sites` into `_seen_pairs` and iterate `for s in sites for u in usernames`. Update the call site in `pipeline.run` to thread `sites` through.

### 1.3 `scraping/links.py:121` — reserved-paths list incomplete
`{"about", "privacy", "terms", "login", "signup"}` misses common landing paths. URLs like `https://twitter.com/explore`, `https://instagram.com/explore`, `https://github.com/notifications` get parsed as handles `explore` / `notifications` and feed false positives into `extracted_handles` and the follow-pass.

**Fix:** expand to a module-level `_RESERVED_HANDLE_PATHS` covering: `about, accounts, business, contact, careers, dashboard, developers, directory, discover, docs, download, explore, faq, feed, features, find, help, home, i, jobs, legal, login, logout, messages, notifications, privacy, pricing, register, search, security, settings, shop, signin, signout, signup, sitemap, status, store, support, terms, tos, trending, tv, u, user, users, watch, web`.

### 1.4 `scoring/features.py:39–53` + `scoring/scorer.py:43–50` — missing-data conflated with low similarity
`_bio_sim`, `_location_sim`, and avatar similarity all return `0.0` when an input is `None`. The weighted sum then loses up to ~0.45 of weight for sparse profiles, making it impossible for two real matches without bios/locations/avatars to cross the cluster threshold via base weights alone.

**Fix:**
1. Change feature helpers to return `Optional[float]` (None = missing).
2. Update `MatchFeatures` fields to `float | None`.
3. In `score_pair`, compute weighted sum over present features only and renormalize: `weighted = sum(w_i * f_i) / sum(w_i for present features)`.
4. Username + display_name + crosslink_strength are always-present, so the denominator never goes to zero.

### 1.5 `scoring/scorer.py:7–15` — weight semantics confused
`WEIGHTS` mixes six base feature weights (sum 0.95) with `crosslink_one_way_boost` (0.25), which is added separately at line 84. The dict reads like a single normalized weight set but isn't.

**Fix:**
1. Rename `WEIGHTS` → `BASE_WEIGHTS` and rebalance to sum to exactly 1.0.
2. Move `crosslink_one_way_boost` to a top-level `ONE_WAY_BOOST = 0.25` constant.
3. Document the 0.97 cap, MUTUAL_FLOOR=0.99, ONE_WAY_CAP=0.95.

### 1.6 `scoring/scorer.py:55` — `min(rarity_a, rarity_b)` is dead code
The branch only runs when `a.username.lower() == b.username.lower()`, and `username_rarity` lowercases its input, so both calls return the same value.

**Fix:** call `username_rarity(a.username)` once.

### 1.7 `__init__.py:1` ↔ `pyproject.toml:3` — version drift
`__version__ = "0.1.0"`, project version `"0.2.0"`.

**Fix:** read from package metadata via `importlib.metadata.version("aliasgraph")`.

### 1.8 `platforms/loader.py:25` — dead conditional
`url_main.rstrip("/") + ("/" if not url_main.endswith("/") else "")` — after `rstrip("/")`, `endswith("/")` is always False, so this always appends `/`.

**Fix:** simplify to `url_main.rstrip("/") + "/"`.

### 1.9 `platforms/loader.py:48` — empty `urlMain` produces malformed URLs
`url_main = v.get("urlMain") or ""`; if a site uses `{urlMain}` in `url` but has no/empty `urlMain`, substitution yields `https:///path` and a downstream Pydantic ValidationError.

**Fix:** in `_resolve_placeholder`, raise `_UnresolvedPlaceholder("urlMain")` when the value is falsy so the site is skipped cleanly.

### 1.10 `cli.py:98` — uncaught pipeline exception
Any pipeline raise produces a raw traceback on the CLI.

**Fix:** wrap in try/except; print a one-line error to `err_console`; raise `typer.Exit(1)`. Add `--debug` flag to surface the full traceback.

### 1.11 `cli.py:115` — `--format terminal --output X` writes JSON or HTML based on extension
This dual behavior is undocumented and surprising.

**Fix:** update `--output` help text; default unknown extensions to JSON.

### 1.12 `scraping/sites/reddit.py:55` — Reddit karma stored in `followers` field
Karma ≠ followers. Two unrelated profiles with similar karma get a false followers-count similarity signal.

**Fix:** leave `followers` as `None` for Reddit.

### 1.13 `scraping/base.py:115–117` — enriched counter undercounts
Only counts the profile as enriched if bio/display_name/links was added; ignores avatar/created_at/followers/extracted_handles enrichments.

**Fix:** count as enriched if any post-scrape field differs.

---

## 2. Security

### 2.1 `scraping/avatar.py:25` — SSRF in avatar fetch
`fetch_avatar_hash` GETs any URL in `Profile.avatar_url`. For sites scraped by `GenericHTMLScraper`, `avatar_url` comes from `og:image` on a (potentially hostile) page, so an attacker can point us at `http://169.254.169.254/...` (cloud metadata), `http://localhost:22/`, internal RFC1918 IPs, etc.

**Fix:** add `_is_safe_public_url(url)` in `scraping/links.py`:
- Resolves only `http`/`https`.
- Rejects bare-IP hosts in private ranges (10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1, fc00::/7, fe80::/10).
- Rejects `localhost`, `*.local`, `metadata.google.internal`, `metadata.aws.amazon.com`.
- Uses stdlib `ipaddress` only — no DNS resolution.

Apply the gate in `fetch_avatar_hash` before `client.stream`.

### 2.2 `reporting/html_report.py:174,186,200` — XSS via untrusted URL in `src`/`href`
`html.escape(...)` escapes quotes, but the *value* itself can be `javascript:alert(1)` from a hostile `og:image` or page redirect. Browsers may execute `javascript:` in `<a href>`.

**Fix:** add `_safe_url(s)` that returns empty string for any non-http(s) URL; use it for every `src=` and `href=` attribute.

### 2.3 `scraping/avatar.py:28` — hardcoded 10s timeout per profile
Hostile avatar host can deliberately slow-stream up to 10s per profile.

**Fix:** lower to `httpx.Timeout(5.0, connect=2.0, read=3.0)`.

### 2.4 `scraping/links.py:42` — IDN/punycode not normalized
`netloc.lower()` doesn't canonicalize Unicode hostnames. `münchen.de` and `xn--mnchen-3ya.de` dedupe as different links.

**Fix:** in `normalize`, attempt `netloc.encode("idna").decode("ascii")` inside try/except, falling back to lowercased original on UnicodeError.

---

## 3. Accuracy (scoring + filters)

### 3.1 `scraping/boilerplate.py:54` — bio length false positive
`if len(b) < 12: return True` rejects "CS student" (10), "ML eng" (6), "Coder" (5), "Designer" (8).

**Fix:** lower threshold to `4`.

### 3.2 `scoring/rarity.py:43–46` — magic entropy constants undocumented
**Fix:** add docstring above `_shannon` explaining the 2.5 bits/char cutoff and 0.10 scale, with the 0.15 cap.

### 3.3 `scoring/rarity.py:51` — sharp boundary at `unique_chars < 3`
"abab" (2 unique) capped at 0.25, "abac" (3 unique) full bonus.

**Fix:** smooth into two cases: `1 → 0.0`, `2 → min(base, 0.25)`.

### 3.4 `scoring/features.py:23–26` — `_ratio` heuristic undocumented
**Fix:** one-line comment noting `token_set_ratio` mostly matters for multi-word display names.

### 3.5 `scoring/scorer.py:77` — magic 0.97 cap undocumented
**Fix:** inline comment explaining the headroom for crosslinks.

### 3.6 `scoring/features.py:48–53` — generic-token penalty hidden
**Fix:** docstring on `_bio_sim`.

### 3.7 `clustering/graph.py:125` — cluster confidence is mean
A 3-node cluster with edges (0.99, 0.99, 0.70) reports 0.89 — misleading.

**Fix:** add `min_edge` to the `Cluster` model so reports can show "weakest link"; keep mean as headline confidence.

### 3.8 `clustering/graph.py:262` — `_looks_like_page_title` matches platform names from any cluster
Hardcoded set checked for every site; e.g. display name "instagram" on a GitHub profile would be filtered.

**Fix:** restrict to sites actually present in the cluster.

---

## 4. Hygiene (code quality, docs)

### 4.1 `scraping/generic.py:30` — `tree.css_first("title")` called twice
**Fix:** cache the result.

### 4.2 `scraping/generic.py:81` — `parse_handles(normalized) or profile.extracted_handles`
**Fix:** drop the `or` fallback for `extracted_handles` and `links`.

### 4.3 `scraping/generic.py:17` — TODO for robots.txt
**Fix:** delete the TODO; document in §6 that robots.txt is intentionally unenforced.

### 4.4 `reporting/json_report.py:13` — no encoding specified
**Fix:** `path.write_text(to_json(result), encoding="utf-8")`.

### 4.5 `pyproject.toml:8` — author name uses real name
**Fix:** change to `{ name = "jwihardi" }` (matches git author).

### 4.6 `scoring/scorer.py:20–31` — `_exact_rare_boost` thresholds undocumented
**Fix:** docstring with rationale per threshold.

### 4.7 `scraping/validation.py:30` — duplicate / overlapping fragments
**Fix:** drop "have been deleted" + "was deleted" (subsumed by "deleted").

### 4.8 `permutations/generator.py:54–57` — numeric suffix on numeric base
A seed like "2005" + suffix "2005" → "20052005".

**Fix:** skip suffix application when `base.isdigit()`.

### 4.9 `permutations/generator.py:59` — `out[:max_candidates]` truncation hides intent
**Fix:** short-circuit inside `add()` once `len(out) >= max_candidates`.

### 4.10 `scraping/sites/github.py:52` — blog URL scheme heuristic
`example.com:8080` → `https://example.com:8080` (good); `git@github.com` → `https://git@github.com` (junk, filtered downstream by normalize).

**Fix:** none — pre-existing behavior is OK; documenting as intentional.

---

## 5. Tests

### 5.1 `tests/test_models.py:5,11` — uses real handle "jhauptman"
**Fix:** replace with `"testuser1"`.

### 5.2 No test for `_follow_pass`
**Fix:** add `tests/test_follow_pass.py` using `httpx.MockTransport`.

### 5.3 No test for `_seen_pairs` regression (1.2)
**Fix:** add `tests/test_pipeline_seen_pairs.py`.

### 5.4 No XSS test for HTML report (covers 2.2)
**Fix:** add `tests/test_html_report.py` asserting no `javascript:` survives rendering.

### 5.5 No SSRF test for avatar (covers 2.1)
**Fix:** add `tests/test_avatar_ssrf.py` asserting unsafe URLs short-circuit before HTTP.

### 5.6 `tests/test_permutations.py` — missing numeric-suffix coverage
**Fix:** add a test for suffix application + numeric-base skip.

### 5.7 `tests/test_links.py` — missing reserved-paths coverage (covers 1.3)
**Fix:** add parametrize cases for `/explore`, `/notifications`, `/feed`, etc.

### 5.8 `tests/test_scoring.py` — missing renormalization coverage (covers 1.4)
**Fix:** add a test where two profiles share rare username + bio + display_name (no avatar/location/links) and assert score ≥ 0.75.

---

## 6. Out of scope (explicit non-fixes)

These are spec gaps but the project owner clarified that ITER1/ITER2 don't bind everything. Skipping:
- Caching (ITER2 §9) — not implemented; no immediate need.
- robots.txt enforcement (ITER2 §10) — TODO comment removed; behavior unchanged.
- Shortener resolution (ITER2 §5) — opt-in feature, unimplemented.
- Bare-handle `@foo` extraction (ITER2 §5) — high false-positive rate.
- Per-host `Retry-After` honoring on 429 — current fail-fast behavior is acceptable for OSINT use.

---

## 7. Verification

After all changes:
1. `uv run pytest -q` — all existing tests pass + new tests added in §5 pass.
2. `uv run ruff check src tests` — no new lint warnings.
3. `uv run mypy src` — no new type errors.
4. Smoke test: `uv run aliasgraph scan testuser1 --site-limit 20 --no-scrape --quiet --format json` returns valid JSON.
5. Manually verify the rebalanced scoring on the existing test fixtures: cluster behaviors in `test_clustering.py` still pass without threshold changes.
