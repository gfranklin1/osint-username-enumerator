from __future__ import annotations

from pathlib import Path

import httpx
import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(rel: str) -> str:
    return (FIXTURES / rel).read_text(encoding="utf-8")


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
