import asyncio

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.sites.devto import DevtoScraper

from tests._helpers import fixture_text


def test_devto_scraper():
    payload = fixture_text("scrapers/devto_ben.json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=payload, headers={"content-type": "application/json"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            base = Profile(site="Dev.to", url="https://dev.to/ben", username="ben")
            return await DevtoScraper().scrape(base, client)

    p = asyncio.run(run())
    assert p.display_name == "Ben Halpern"
    assert p.location == "NY"
    sites = {h.site for h in p.extracted_handles}
    assert "GitHub" in sites and "Twitter" in sites
