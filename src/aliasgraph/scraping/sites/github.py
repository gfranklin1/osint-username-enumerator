from __future__ import annotations

import json

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.base import fetch_text
from aliasgraph.scraping.links import (
    extract_urls_from_text,
    normalize,
    parse_handles,
    twitter_url,
)


class GithubScraper:
    site = "GitHub"

    async def scrape(self, profile: Profile, client: httpx.AsyncClient) -> Profile:
        status, _, text = await fetch_text(
            client,
            f"https://api.github.com/users/{profile.username}",
            accept="application/vnd.github+json",
            headers={"X-GitHub-Api-Version": "2022-11-28"},
        )
        if status != 200 or not text:
            return profile
        try:
            data = json.loads(text)
        except (ValueError, json.JSONDecodeError):
            return profile

        # Pull GitHub's "social accounts" — this is where LinkedIn / Mastodon / etc. live.
        social_status, _, social_text = await fetch_text(
            client,
            f"https://api.github.com/users/{profile.username}/social_accounts",
            accept="application/vnd.github+json",
            headers={"X-GitHub-Api-Version": "2022-11-28"},
        )
        social_links: list[str] = []
        if social_status == 200 and social_text:
            try:
                for entry in json.loads(social_text):
                    if isinstance(entry, dict) and isinstance(entry.get("url"), str):
                        social_links.append(entry["url"])
            except (ValueError, json.JSONDecodeError):
                pass

        urls: list[str] = []
        if blog := data.get("blog"):
            urls.append(blog if "://" in blog else f"https://{blog}")
        if tw := data.get("twitter_username"):
            urls.append(twitter_url(tw))
        urls.extend(social_links)
        urls.extend(extract_urls_from_text(data.get("bio")))

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
                "bio": data.get("bio") or profile.bio,
                "location": data.get("location") or profile.location,
                "avatar_url": data.get("avatar_url") or profile.avatar_url,
                "created_at": data.get("created_at") or profile.created_at,
                "followers": data.get("followers"),
                "following": data.get("following"),
                "links": normalized,
                "extracted_handles": parse_handles(normalized),
            }
        )
