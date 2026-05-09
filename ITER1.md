# AliasGraph

**AliasGraph** is a Python-based OSINT username enumeration and account-attribution tool. It extends the classic username-checking model used by tools like Sherlock or Maigret by adding algorithmic username permutations, public-profile scraping, feature extraction, and explainable relatedness scoring.

Instead of only checking whether an exact username exists on many websites, AliasGraph generates likely username variants, collects public metadata from discovered profiles, and groups accounts by how likely they are to belong to the same person or identity.

> Target runtime: **Python 3.14.4**

---

## Table of Contents

* [Overview](#overview)
* [Motivation](#motivation)
* [Features](#features)
* [Ethical Use](#ethical-use)
* [How It Works](#how-it-works)
* [Scoring Model](#scoring-model)
* [Example Output](#example-output)
* [Project Structure](#project-structure)
* [Installation](#installation)
* [Usage](#usage)
* [Configuration](#configuration)
* [Development Roadmap](#development-roadmap)
* [Limitations](#limitations)
* [License](#license)

---

## Overview

AliasGraph is designed to answer questions like:

* Does this username exist across public platforms?
* Are these accounts likely connected?
* Which discovered accounts are probably the same person?
* Which accounts are weak matches or likely unrelated?
* What evidence supports a match?

Traditional username enumeration tools usually perform exact checks:

```text
input: jacobhauptman
check: github.com/jacobhauptman
check: reddit.com/user/jacobhauptman
check: instagram.com/jacobhauptman
```

AliasGraph uses a more flexible approach:

```text
input: jacobhauptman
variants:
  jacobhauptman
  jacob.hauptman
  jacob_hauptman
  jacob-hauptman
  jhauptman
  jacobh
  hauptmanj
  jacob2005
  jacobmilo2005
```

Then it evaluates discovered profiles using public metadata such as usernames, display names, bios, linked accounts, avatars, locations, and profile text similarity.

---

## Motivation

People rarely use one exact username everywhere. A person might use:

```text
jacobhauptman
jacob.hauptman
jhauptman
jacob_milo2005
jacubdev
hauptmanj
```

Exact-string tools miss these relationships. AliasGraph attempts to model identity similarity more realistically by combining:

* username morphology
* permutation rules
* public profile metadata
* explicit cross-links
* text similarity
* avatar similarity
* graph clustering
* explainable scoring

The goal is not only to find accounts, but to explain **why** they may or may not be related.

---

## Features

Planned and/or implemented features:

* Generate likely username permutations from one or more seed handles
* Check public profile existence across supported platforms
* Scrape public metadata from discovered profiles
* Normalize profile data into a common schema
* Compare accounts using explainable similarity features
* Cluster likely related accounts into identity groups
* Score matches using weighted evidence
* Export results as JSON and human-readable reports
* Support optional word embeddings for bio/profile-text similarity
* Support optional avatar hashing for image similarity
* Provide transparent evidence for every match

Example evidence report:

```text
GitHub: jhauptman
LinkedIn: jacob-hauptman
Relatedness: 94%

Evidence:
+ Same full name
+ GitHub links to the same LinkedIn profile
+ Similar username structure
+ Bio mentions computer science on both profiles
+ Similar location metadata
```

---

## Ethical Use

AliasGraph is intended for legitimate, defensive, educational, and research-oriented OSINT workflows.

Acceptable uses include:

* auditing your own public online footprint
* checking username reuse across your own accounts
* security research with proper authorization
* investigating impersonation of yourself or an organization you represent
* learning about public OSINT methodology
* building a portfolio project around graph analysis and profile attribution

Do **not** use this tool for:

* stalking
* harassment
* doxxing
* credential attacks
* bypassing privacy settings
* targeting private individuals without a legitimate reason
* violating platform terms of service
* collecting or storing sensitive personal information unnecessarily

AliasGraph should only collect publicly available information and should respect rate limits, robots.txt where applicable, and platform rules.

---

## How It Works

AliasGraph follows a pipeline-based design:

```text
Seed Identity
    ↓
Username Permutation Engine
    ↓
Platform Scanner
    ↓
Profile Scraper
    ↓
Feature Extractor
    ↓
Relatedness Scorer
    ↓
Graph Clusterer
    ↓
Report Generator
```

### 1. Seed Identity

The user provides one or more known usernames or identity hints.

Example:

```bash
aliasgraph scan jacobhauptman --name "Jacob Hauptman"
```

Possible inputs:

* username
* display name
* first name
* last name
* known aliases
* optional keywords
* optional known links

---

### 2. Username Permutation Engine

The permutation engine generates likely username variants.

For example, given:

```text
first name: jacob
last name: hauptman
known handle: jacobmilo2005
```

The engine may generate:

```text
jacobhauptman
jacob.hauptman
jacob_hauptman
jacob-hauptman
jhauptman
j.hauptman
hauptmanj
jacobh
jacobmilo2005
jacob.milo2005
jacob_milo2005
jacob-2005
jhauptman05
jhauptman2005
```

Permutation categories:

* separator changes: `.`, `_`, `-`, none
* first/last combinations
* initials
* reversed order
* common birth-year suffixes
* numeric suffixes
* alias suffixes
* spelling variants
* leetspeak variants, optionally
* platform-specific normalization rules

The goal is not to generate every possible username. The goal is to generate a useful, bounded set of likely candidates.

---

### 3. Platform Scanner

The scanner checks whether each candidate username appears to exist on supported platforms.

Example platforms:

* GitHub
* GitLab
* Reddit
* Stack Overflow
* Kaggle
* Medium
* Dev.to
* YouTube
* npm
* PyPI
* Hacker News
* Codeberg
* SourceHut

Each platform module defines:

```python
class PlatformConfig:
    name: str
    profile_url: str
    not_found_patterns: list[str]
    rate_limit_seconds: float
    requires_javascript: bool
```

The scanner should prefer lightweight HTTP requests when possible and only use browser automation for JavaScript-heavy sites.

---

### 4. Profile Scraper

If a profile exists, AliasGraph extracts public metadata.

Normalized profile schema:

```python
from pydantic import BaseModel, HttpUrl

class Profile(BaseModel):
    site: str
    url: HttpUrl
    username: str
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    links: list[str] = []
    avatar_url: str | None = None
    avatar_hash: str | None = None
    created_at: str | None = None
    followers: int | None = None
    following: int | None = None
    raw_html_hash: str | None = None
```

The scraper should be conservative and avoid collecting unnecessary personal data.

---

### 5. Feature Extractor

The feature extractor converts raw profile data into comparable signals.

Possible features:

* username similarity
* display-name similarity
* bio text similarity
* external link overlap
* avatar perceptual hash similarity
* location similarity
* account creation timing
* shared keywords
* shared repositories or project topics
* profile page structure
* explicit cross-links

Example feature object:

```python
class MatchFeatures(BaseModel):
    username_similarity: float
    display_name_similarity: float
    bio_similarity: float
    link_overlap_score: float
    avatar_similarity: float
    location_similarity: float
    temporal_similarity: float
    explicit_crosslink: bool
```

---

### 6. Relatedness Scorer

The scorer combines evidence into a final probability-like score.

Example:

```python
score = (
    0.30 * username_similarity
    + 0.25 * link_overlap_score
    + 0.15 * bio_similarity
    + 0.15 * avatar_similarity
    + 0.10 * display_name_similarity
    + 0.05 * location_similarity
)
```

The score should be explainable. AliasGraph should report not only the final number, but the strongest evidence behind it.

---

### 7. Graph Clusterer

Profiles can be represented as nodes in a graph.

Edges represent relatedness:

```text
GitHub:jhauptman ─── 0.94 ─── LinkedIn:jacob-hauptman
GitHub:jhauptman ─── 0.81 ─── Kaggle:jacob_milo2005
Reddit:jacob2005 ─── 0.33 ─── GitHub:jhauptman
```

High-confidence edges form likely identity clusters.

Possible graph tools:

* `networkx`
* connected components
* community detection
* threshold-based clustering

---

### 8. Report Generator

Reports should be available in multiple formats:

* JSON
* Markdown
* HTML
* terminal output

Example CLI output:

```text
AliasGraph Report
=================

Seed: jacobhauptman
Generated usernames: 48
Profiles found: 7
Likely clusters: 2

Cluster 1: likely same identity
--------------------------------
GitHub      jhauptman          96%
LinkedIn    jacob-hauptman     98%
Kaggle      jacob_milo2005     82%
Dev.to      jacobhauptman      77%

Strongest evidence:
+ GitHub links to LinkedIn
+ Same display name
+ Similar bio text
+ Similar username morphology

Cluster 2: weak / probably unrelated
------------------------------------
Reddit      jacobhauptman      31%
Instagram   jacob2005          24%
```

---

## Scoring Model

AliasGraph should use explainable weighted scoring before using a black-box model.

### Evidence Strength

#### Very Strong Evidence

* One profile links directly to another
* Multiple profiles link to the same personal website
* Same verified email hash or public PGP key
* Same unique avatar
* Same full name plus same organization or location
* Same GitHub, LinkedIn, website, or portfolio link

#### Medium Evidence

* Similar bio text
* Similar display name
* Same school, company, or project keywords
* Similar usernames with uncommon structure
* Similar profile descriptions
* Same project names across platforms

#### Weak Evidence

* Same first name only
* Same generic interests
* Similar but common username
* Similar account age
* Similar follower count
* Generic bio words like `developer`, `student`, or `gamer`

---

## Example Output

Example JSON output:

```json
{
  "seed": "jacobhauptman",
  "generated_usernames": [
    "jacobhauptman",
    "jacob.hauptman",
    "jacob_hauptman",
    "jhauptman"
  ],
  "profiles": [
    {
      "site": "github",
      "username": "jhauptman",
      "url": "https://github.com/jhauptman",
      "display_name": "Jacob Hauptman",
      "bio": "CS student interested in ML and systems",
      "links": ["https://linkedin.com/in/jacob-hauptman"]
    }
  ],
  "clusters": [
    {
      "cluster_id": 1,
      "confidence": 0.94,
      "profiles": [
        "github:jhauptman",
        "linkedin:jacob-hauptman"
      ],
      "evidence": [
        "Same display name",
        "Explicit LinkedIn link found on GitHub",
        "High username similarity"
      ]
    }
  ]
}
```

---

## Project Structure

Suggested layout:

```text
aliasgraph/
├── README.md
├── pyproject.toml
├── src/
│   └── aliasgraph/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── permutations/
│       │   ├── __init__.py
│       │   └── generator.py
│       ├── platforms/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── github.py
│       │   ├── reddit.py
│       │   └── devto.py
│       ├── scanning/
│       │   ├── __init__.py
│       │   ├── scanner.py
│       │   └── rate_limit.py
│       ├── scraping/
│       │   ├── __init__.py
│       │   ├── parser.py
│       │   └── avatar.py
│       ├── features/
│       │   ├── __init__.py
│       │   ├── text.py
│       │   ├── username.py
│       │   ├── links.py
│       │   └── avatar.py
│       ├── scoring/
│       │   ├── __init__.py
│       │   ├── scorer.py
│       │   └── explanations.py
│       ├── clustering/
│       │   ├── __init__.py
│       │   └── graph.py
│       └── reporting/
│           ├── __init__.py
│           ├── json_report.py
│           ├── markdown_report.py
│           └── html_report.py
├── tests/
│   ├── test_permutations.py
│   ├── test_username_similarity.py
│   ├── test_scoring.py
│   └── test_clustering.py
└── examples/
    ├── basic_scan.json
    └── report.md
```

---

## Installation

AliasGraph targets **Python 3.14.4**.

Recommended setup using `uv`:

```bash
uv python install 3.14.4
uv venv --python 3.14.4
source .venv/bin/activate
uv pip install -e .
```

Alternative setup using standard `venv`:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Optional ML dependencies:

```bash
python -m pip install -e '.[ml]'
```

Optional development dependencies:

```bash
python -m pip install -e '.[dev]'
```

---

## Example `pyproject.toml`

```toml
[project]
name = "aliasgraph"
version = "0.1.0"
description = "OSINT username permutation and explainable account-attribution tool"
readme = "README.md"
requires-python = ">=3.14.4"
license = { text = "MIT" }
authors = [
    { name = "Your Name" }
]
dependencies = [
    "httpx>=0.28.0",
    "beautifulsoup4>=4.13.0",
    "selectolax>=0.3.0",
    "pydantic>=2.0.0",
    "typer>=0.12.0",
    "rich>=13.0.0",
    "rapidfuzz>=3.0.0",
    "networkx>=3.0",
]

[project.optional-dependencies]
ml = [
    "sentence-transformers>=3.0.0",
    "numpy>=2.0.0",
    "scikit-learn>=1.5.0",
]
image = [
    "pillow>=10.0.0",
    "imagehash>=4.3.0",
]
browser = [
    "playwright>=1.45.0",
]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.6.0",
    "mypy>=1.10.0",
]

[project.scripts]
aliasgraph = "aliasgraph.cli:app"

[tool.ruff]
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]

[tool.mypy]
python_version = "3.14"
strict = true
```

---

## Usage

### Basic scan

```bash
aliasgraph scan jacobhauptman
```

### Scan with identity hints

```bash
aliasgraph scan jacobhauptman \
  --first-name Jacob \
  --last-name Hauptman \
  --alias jacobmilo2005 \
  --keyword "computer science" \
  --keyword "machine learning"
```

### Limit platforms

```bash
aliasgraph scan jacobhauptman --platform github --platform reddit --platform devto
```

### Export JSON

```bash
aliasgraph scan jacobhauptman --output report.json
```

### Export Markdown

```bash
aliasgraph scan jacobhauptman --format markdown --output report.md
```

### Use embeddings

```bash
aliasgraph scan jacobhauptman --use-embeddings
```

### Use avatar similarity

```bash
aliasgraph scan jacobhauptman --use-avatar-hash
```

---

## Configuration

Example config file:

```yaml
scanner:
  timeout_seconds: 10
  max_concurrency: 20
  user_agent: "AliasGraph/0.1"
  respect_rate_limits: true

permutations:
  max_candidates: 100
  include_numeric_suffixes: true
  include_initials: true
  include_leetspeak: false

scoring:
  likely_threshold: 0.75
  possible_threshold: 0.50
  weak_threshold: 0.25
  weights:
    username_similarity: 0.30
    link_overlap: 0.25
    bio_similarity: 0.15
    avatar_similarity: 0.15
    display_name_similarity: 0.10
    location_similarity: 0.05

platforms:
  github:
    enabled: true
    rate_limit_seconds: 1.0
  reddit:
    enabled: true
    rate_limit_seconds: 2.0
  devto:
    enabled: true
    rate_limit_seconds: 1.0
```

---

## Development Roadmap

### Version 0.1

* Basic CLI
* Username permutation engine
* Platform config system
* HTTP-based profile existence checks
* JSON output
* GitHub, Reddit, Dev.to support

### Version 0.2

* Public profile metadata scraping
* Normalized profile schema
* Username similarity scoring
* Display-name similarity scoring
* Markdown reports

### Version 0.3

* Link-overlap scoring
* Evidence explanations
* Graph-based clustering
* Rich terminal output

### Version 0.4

* Optional sentence-transformer embeddings
* Bio/profile similarity scoring
* Optional avatar perceptual hashing
* HTML reports

### Version 0.5

* More platform modules
* Better rate limiting
* Caching
* Retry logic
* Plugin architecture

### Version 1.0

* Stable CLI
* Stable JSON schema
* Full report generation
* Configurable scoring model
* Tested platform modules
* Documentation and examples

---

## Limitations

AliasGraph should not claim certainty. It estimates likelihood based on public evidence.

Possible sources of error:

* common usernames
* copied bios
* reused profile pictures
* private or deleted profiles
* platform anti-scraping behavior
* false positives from generic metadata
* false negatives from missing public data
* stale profile pages
* rate limits or temporary network errors

The tool should always communicate uncertainty clearly.

Bad output:

```text
This is definitely the same person.
```

Better output:

```text
These accounts are likely related based on shared links, similar usernames, and matching display names. Confidence: 86%.
```

---

## Design Principles

AliasGraph should be:

* **Explainable**: every score should have evidence
* **Modular**: each platform should be a separate module
* **Conservative**: avoid overclaiming identity matches
* **Respectful**: avoid aggressive scraping or privacy-invasive collection
* **Reproducible**: reports should include inputs, config, and scoring weights
* **Extensible**: new platforms and scoring features should be easy to add

---

## Possible Resume Bullet

```text
Built AliasGraph, a Python OSINT attribution engine that generates probabilistic username permutations, scrapes public profile metadata, and clusters accounts using explainable similarity signals including linked accounts, profile text embeddings, avatar hashes, and username morphology.
```

Shorter version:

```text
Built a Python OSINT tool that finds username variants across platforms and clusters likely related accounts using explainable profile-similarity scoring.
```

---

## License

This project is intended to be released under the MIT License.

---

## Disclaimer

AliasGraph is for educational, defensive, and authorized research purposes only. The maintainers are not responsible for misuse. Users are responsible for following all applicable laws, platform terms of service, and ethical guidelines.

