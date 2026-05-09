from __future__ import annotations

import json

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.base import fetch_text
from aliasgraph.scraping.links import (
    extract_urls_from_text,
    github_url,
    normalize,
    parse_handles,
    twitter_url,
)


class DevtoScraper:
    site = "Dev.to"

    async def scrape(self, profile: Profile, client: httpx.AsyncClient) -> Profile:
        status, _, text = await fetch_text(
            client,
            f"https://dev.to/api/users/by_username?url={profile.username}",
            accept="application/json",
        )
        if status != 200 or not text:
            return profile
        try:
            data = json.loads(text)
        except (ValueError, json.JSONDecodeError):
            return profile

        urls: list[str] = []
        if w := data.get("website_url"):
            urls.append(w)
        if g := data.get("github_username"):
            urls.append(github_url(g))
        if tw := data.get("twitter_username"):
            urls.append(twitter_url(tw))
        urls.extend(extract_urls_from_text(data.get("summary")))

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
                "display_name": data.get("name") or profile.display_name,
                "bio": data.get("summary") or profile.bio,
                "location": data.get("location") or profile.location,
                "avatar_url": data.get("profile_image") or profile.avatar_url,
                "created_at": data.get("joined_at") or profile.created_at,
                "links": normalized,
                "extracted_handles": parse_handles(normalized),
            }
        )
