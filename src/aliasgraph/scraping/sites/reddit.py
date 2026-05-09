from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.base import fetch_text
from aliasgraph.scraping.links import extract_urls_from_text, normalize, parse_handles


class RedditScraper:
    site = "Reddit"

    async def scrape(self, profile: Profile, client: httpx.AsyncClient) -> Profile:
        status, _, text = await fetch_text(
            client,
            f"https://www.reddit.com/user/{profile.username}/about.json",
            accept="application/json",
        )
        if status != 200 or not text:
            return profile
        try:
            data = json.loads(text).get("data", {})
        except (ValueError, json.JSONDecodeError):
            return profile

        sub = data.get("subreddit") or {}
        bio = sub.get("public_description") or sub.get("description") or None
        display_name = sub.get("title") or data.get("name") or profile.display_name
        avatar = sub.get("icon_img") or data.get("icon_img")

        created = data.get("created_utc")
        created_iso: str | None = None
        if isinstance(created, int | float):
            created_iso = datetime.fromtimestamp(created, tz=UTC).isoformat()

        urls = extract_urls_from_text(bio)
        normalized: list[str] = []
        seen: set[str] = set()
        for u in urls:
            n = normalize(u)
            if not n or n in seen:
                continue
            seen.add(n)
            normalized.append(n)

        return profile.model_copy(
            update={
                "display_name": display_name or profile.display_name,
                "bio": bio or profile.bio,
                "avatar_url": avatar.split("?")[0] if avatar else profile.avatar_url,
                "created_at": created_iso or profile.created_at,
                "followers": data.get("total_karma") if isinstance(data.get("total_karma"), int) else None,
                "links": normalized,
                "extracted_handles": parse_handles(normalized),
            }
        )
