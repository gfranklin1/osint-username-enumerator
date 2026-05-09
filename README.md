# AliasGraph

OSINT username permutation and explainable account-attribution tool. See [ITER1.md](ITER1.md) for the full design spec.

## Status

v0.1 — basic CLI, permutation engine, HTTP existence checks (GitHub, Reddit, Dev.to), JSON/terminal output. Scoring, clustering, scraping, and embeddings are deferred to later iterations.

## Install

```bash
uv venv --python 3.14.4
uv pip install -e '.[dev]'
```

## Usage

```bash
uv run aliasgraph scan torvalds --first-name Linus --last-name Torvalds
uv run aliasgraph scan torvalds --format json --output report.json
uv run aliasgraph scan torvalds --platform github --platform devto
```

## Test

```bash
uv run pytest -q
```
