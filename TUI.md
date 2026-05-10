# AliasGraph TUI

Interactive terminal UI for AliasGraph. The CLI (`aliasgraph scan ...`) is
unchanged — the TUI is an additive, opt-in interface for users who'd rather
fill in a form, watch live progress, and explore results interactively than
juggle command-line flags.

Built on [Textual](https://textual.textualize.io/). Asyncio-native, runs in
any modern terminal, no browser needed.

---

## Install

The TUI is shipped as an optional extra so the base install stays lean:

```bash
uv pip install -e '.[tui]'
# or:
pip install 'aliasgraph[tui]'
```

If textual isn't installed, `aliasgraph tui` prints a one-line install hint
and exits 1 — the rest of the CLI is unaffected.

## Launch

```bash
aliasgraph tui
```

That's it. The same `aliasgraph` binary; new subcommand. No new
console-scripts entry, no environment variable, no config file.

## Screens

The TUI has three screens. Push order is **Form → Running → Results**.

### 1. Form

Configure a scan. Mirrors the `aliasgraph scan` flag set:

| Field                  | CLI equivalent              | Default |
| ---------------------- | --------------------------- | ------- |
| Seed username          | positional `SEED`           | —       |
| First name             | `--first-name`              | —       |
| Last name              | `--last-name`               | —       |
| Aliases                | `--alias` (repeatable)      | —       |
| Numeric suffixes       | `--numeric-suffix`          | —       |
| Platforms              | `--platform`                | all     |
| Site limit             | `--site-limit`              | 0       |
| Max candidates         | `--max-candidates`          | 30      |
| Concurrency            | `--concurrency`             | 50      |
| Timeout (s)            | `--timeout`                 | 8.0     |
| Likely threshold       | `--likely-threshold`        | 0.75    |
| Quality threshold      | `--quality-threshold`       | 0.30    |
| Max link depth         | `--max-link-depth`          | 1       |
| Toggle: Scrape         | `--scrape / --no-scrape`    | on      |
| Toggle: Avatar         | `--avatar-hash / --no-avatar-hash` | on |
| Toggle: Follow         | `--follow-links / --no-follow-links` | on |
| Toggle: Cluster        | `--cluster / --no-cluster`  | on      |
| Toggle: Embed          | `--use-embeddings`          | off     |

Empty seed is rejected with a notification; everything else falls back to
defaults if blank.

**Bindings:** `Ctrl+R` runs the scan, `Ctrl+Q` quits.

### 2. Running

Live progress while the pipeline executes:

- Existence-checks progress bar.
- Profile-scraping progress bar.
- Status log (one line per pipeline phase).

The pipeline runs as a Textual worker on the same asyncio loop, so progress
updates are immediate. If anything raises, the error is logged in red and the
screen stays open — press `Esc` to return to the form.

### 3. Results

Two-pane layout:

- **Left:** a `Tree` of clusters → members → asserted accounts, plus
  ungrouped profiles, weak hits (filtered by quality threshold), and errors.
- **Right:** a detail panel that shows information for whatever is selected
  in the tree (cluster summary, profile fields, asserted-account context,
  error reason).

Below the tree: a **Retune** row with the `likely` and `quality` thresholds
as text inputs, plus a **Re-cluster** button. Re-clustering uses the cached
raw profiles (the verified + weak union, with their per-profile quality
scores intact) to re-filter and re-cluster *without re-fetching anything*.
Iterate on the thresholds until the cluster boundaries look right.

Action row at the bottom:

- **Save JSON** — writes `<seed>.json` in the current directory.
- **Save HTML** — writes `<seed>.html` (same renderer as the CLI).
- **New scan** — pops back to the form (current results discarded).
- **Quit** — exits.

**Bindings:** `Ctrl+R` re-cluster · `N` new scan · `Esc` back to form ·
`Ctrl+Q` quit.

## When to use which

- Use the **CLI** when you're scripting, piping, or running unattended (CI,
  cron, batch jobs).
- Use the **TUI** when you're investigating one identity interactively and
  want to iterate on thresholds without re-fetching, or when you want to
  drill into individual profiles, clusters, and asserted accounts visually.

Both produce the same `ScanResult`; both can write the same JSON / HTML
report.

## Architecture (one paragraph)

`tui/app.py` defines a `textual.app.App` with three `Screen` subclasses
(`FormScreen`, `RunningScreen`, `ResultsScreen`). The pipeline runs as a
Textual worker so the UI stays responsive. Pipeline progress callbacks
update widgets directly (same asyncio loop). Re-clustering on the results
screen calls `aliasgraph.clustering.build_clusters` over the cached raw
profiles — no new network requests. Styling lives in `tui/styles.tcss`
(palette mirrors the HTML report).

Tested via Textual's `App.run_test()` harness (`tests/test_tui.py`). The
test file uses `pytest.importorskip("textual")` so it's silently skipped
when the optional dep isn't installed.
