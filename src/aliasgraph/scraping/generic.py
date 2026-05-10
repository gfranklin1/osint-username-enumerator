from __future__ import annotations

import json

import httpx
from selectolax.parser import HTMLParser

from aliasgraph.models import Profile
from aliasgraph.scraping.base import fetch_text
from aliasgraph.scraping.boilerplate import clean_bio
from aliasgraph.scraping.links import (
    extract_urls_from_text,
    normalize,
    parse_handles,
)


class GenericHTMLScraper:
    site = "*"

    async def scrape(self, profile: Profile, client: httpx.AsyncClient) -> Profile:
        status, _, text = await fetch_text(client, str(profile.url), accept="text/html,*/*")
        if status >= 400 or not text:
            return profile
        tree = HTMLParser(text)

        bio = _meta(tree, "og:description") or _meta_name(tree, "description")
        title_node = tree.css_first("title")
        display_name = _meta(tree, "og:title") or (title_node.text() if title_node else None)
        avatar = _meta(tree, "og:image")

        urls: list[str] = []

        # <link rel="me" href="..."> and <a rel="me">
        for sel in ('link[rel="me"]', 'a[rel="me"]'):
            for node in tree.css(sel):
                href = node.attributes.get("href")
                if href:
                    urls.append(href)

        # JSON-LD
        for script in tree.css('script[type="application/ld+json"]'):
            raw = script.text() or ""
            for sa, name, desc in _walk_jsonld(raw):
                urls.extend(sa)
                if not display_name and name:
                    display_name = name
                if not bio and desc:
                    bio = desc

        # og:url and og:see_also
        for meta in ("og:url", "og:see_also"):
            v = _meta(tree, meta)
            if v:
                urls.append(v)

        # Bio text URL sweep
        urls.extend(extract_urls_from_text(bio))

        normalized: list[str] = []
        seen: set[str] = set()
        own_url = normalize(str(profile.url))
        for u in urls:
            n = normalize(u)
            if not n or n == own_url:
                continue
            if n in seen:
                continue
            seen.add(n)
            normalized.append(n)

        cleaned_bio = clean_bio(_trim(bio), profile.username, profile.site)
        cleaned_display = _strip_site_title(display_name, profile.site)
        return profile.model_copy(
            update={
                "display_name": _trim(cleaned_display) or profile.display_name,
                "bio": cleaned_bio if cleaned_bio is not None else profile.bio,
                "avatar_url": avatar or profile.avatar_url,
                # Always overwrite with the freshly normalized values — falling
                # back to the prior list would mask intentional clears and
                # confuse downstream "did anything change?" checks.
                "links": normalized,
                "extracted_handles": parse_handles(normalized),
            }
        )


def _strip_site_title(display: str | None, site: str | None) -> str | None:
    """Drop display names that are just the site's name or page title."""
    if not display:
        return display
    d = display.strip()
    s = (site or "").strip()
    if not s:
        return d
    if d.lower() == s.lower():
        return None
    return d


def _meta(tree: HTMLParser, prop: str) -> str | None:
    node = tree.css_first(f'meta[property="{prop}"]')
    if node is None:
        return None
    v = node.attributes.get("content")
    return v.strip() if v else None


def _meta_name(tree: HTMLParser, name: str) -> str | None:
    node = tree.css_first(f'meta[name="{name}"]')
    if node is None:
        return None
    v = node.attributes.get("content")
    return v.strip() if v else None


def _trim(s: str | None, limit: int = 600) -> str | None:
    if not s:
        return None
    s = s.strip()
    if len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s or None


def _walk_jsonld(raw: str):
    try:
        data = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        return
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        t = node.get("@type")
        is_person = (
            t == "Person"
            or (isinstance(t, list) and "Person" in t)
        )
        if is_person:
            sa = node.get("sameAs") or []
            if isinstance(sa, str):
                sa = [sa]
            yield (
                [s for s in sa if isinstance(s, str)],
                node.get("name") if isinstance(node.get("name"), str) else None,
                node.get("description") if isinstance(node.get("description"), str) else None,
            )
        for v in node.values():
            if isinstance(v, dict | list):
                stack.append(v)
