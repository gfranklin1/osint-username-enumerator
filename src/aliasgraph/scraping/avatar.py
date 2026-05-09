"""Avatar fetching + perceptual hashing.

We use pHash (DCT-based perceptual hash) which yields a 64-bit fingerprint per
image. Hamming distance ≤ 5 between two hashes means the images are very
likely the same picture (potentially resized / re-encoded). Used by the
scorer as a strong identity signal: same avatar across two profiles is hard
to fake by accident.
"""
from __future__ import annotations

import io
from collections.abc import Iterable

import httpx
from PIL import Image, UnidentifiedImageError

import imagehash

from aliasgraph.models import Profile

MAX_AVATAR_BYTES = 2_097_152  # 2 MiB
PHASH_BITS = 64


async def fetch_avatar_hash(client: httpx.AsyncClient, url: str) -> str | None:
    """Download an avatar URL and return its pHash as a hex string, or None on failure."""
    try:
        async with client.stream("GET", url, timeout=10.0, follow_redirects=True) as r:
            if r.status_code != 200:
                return None
            ctype = r.headers.get("content-type", "").lower()
            if ctype and not ctype.startswith("image/"):
                return None
            buf = bytearray()
            async for chunk in r.aiter_bytes():
                buf.extend(chunk)
                if len(buf) >= MAX_AVATAR_BYTES:
                    return None  # oversized — skip rather than truncate to avoid corrupt decode
            data = bytes(buf)
    except Exception:
        return None
    if not data:
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            ph = imagehash.phash(im)
        return str(ph)
    except (UnidentifiedImageError, OSError, ValueError):
        return None


async def populate_avatar_hashes(
    profiles: Iterable[Profile],
    client: httpx.AsyncClient,
) -> list[Profile]:
    out: list[Profile] = []
    seen_url_to_hash: dict[str, str | None] = {}
    for p in profiles:
        if not p.avatar_url or p.avatar_hash:
            out.append(p)
            continue
        if p.avatar_url in seen_url_to_hash:
            h = seen_url_to_hash[p.avatar_url]
        else:
            h = await fetch_avatar_hash(client, p.avatar_url)
            seen_url_to_hash[p.avatar_url] = h
        out.append(p.model_copy(update={"avatar_hash": h}) if h else p)
    return out


def hamming_similarity(hash_a: str | None, hash_b: str | None) -> float:
    """Return [0, 1] similarity between two pHash hex strings. 1.0 = identical."""
    if not hash_a or not hash_b:
        return 0.0
    try:
        a = imagehash.hex_to_hash(hash_a)
        b = imagehash.hex_to_hash(hash_b)
    except (ValueError, TypeError):
        return 0.0
    distance = a - b  # imagehash overloads __sub__ as Hamming distance
    return max(0.0, 1.0 - (distance / PHASH_BITS))
