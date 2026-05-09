import asyncio

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.sites.github import GithubScraper

from tests._helpers import fixture_text


def test_github_scraper_populates_fields_and_handles():
    payload = fixture_text("scrapers/github_torvalds.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.github.com" in str(request.url)
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            base = Profile(site="GitHub", url="https://github.com/torvalds", username="torvalds")
            return await GithubScraper().scrape(base, client)

    p = asyncio.run(run())
    assert p.display_name == "Linus Torvalds"
    assert p.location == "Portland, OR"
    assert p.followers == 200000
    assert "https://twitter.com/Linus__Torvalds" in p.links
    sites = {h.site for h in p.extracted_handles}
    assert "Twitter" in sites
