import asyncio

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.sites.reddit import RedditScraper

from tests._helpers import fixture_text


def test_reddit_scraper_extracts_bio_and_link():
    payload = fixture_text("scrapers/reddit_about.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            base = Profile(site="Reddit", url="https://www.reddit.com/user/spez", username="spez")
            return await RedditScraper().scrape(base, client)

    p = asyncio.run(run())
    assert "Reddit cofounder" in (p.bio or "")
    assert any(h.site == "GitHub" and h.handle == "spez" for h in p.extracted_handles)
    assert p.created_at is not None
