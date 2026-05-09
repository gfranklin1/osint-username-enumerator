from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(rel: str) -> str:
    return (FIXTURES / rel).read_text(encoding="utf-8")
