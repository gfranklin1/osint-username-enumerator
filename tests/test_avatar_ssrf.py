"""SSRF guard around avatar fetching — see ITER3 §2.1."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from aliasgraph.scraping.avatar import fetch_avatar_hash
from aliasgraph.scraping.links import is_safe_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/avatar.png",
        "http://localhost/avatar.png",
        "http://10.0.0.1/avatar.png",
        "http://192.168.1.1/avatar.png",
        "http://172.16.0.1/avatar.png",
        "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        "http://[::1]/avatar.png",
        "http://[fe80::1]/avatar.png",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://internal-svc.local/avatar.png",
        "ftp://example.com/avatar.png",  # wrong scheme
        "javascript:alert(1)",
    ],
)
def test_is_safe_public_url_rejects_unsafe(url):
    assert is_safe_public_url(url) is False, url


@pytest.mark.parametrize(
    "url",
    [
        "https://avatars.githubusercontent.com/u/1",
        "https://example.com/photo.jpg",
        "http://1.1.1.1/img.png",
        "https://img.icons8.com/x.png",
    ],
)
def test_is_safe_public_url_accepts_public(url):
    assert is_safe_public_url(url) is True, url


def test_fetch_avatar_hash_short_circuits_unsafe_url_without_http_call():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, content=b"\x89PNG\r\n\x1a\n", headers={"content-type": "image/png"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_avatar_hash(client, "http://127.0.0.1/avatar.png")

    result = asyncio.run(run())
    assert result is None
    assert calls == [], "fetch_avatar_hash must not issue an HTTP request to private IPs"
