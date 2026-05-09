import asyncio

import httpx

from aliasgraph.models import Profile
from aliasgraph.scraping.generic import GenericHTMLScraper

from tests._helpers import fixture_text


def test_generic_scraper_parses_og_jsonld_and_relme():
    html = fixture_text("scrapers/generic_og.html")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            base = Profile(site="Example", url="https://example.com/jane", username="jane")
            return await GenericHTMLScraper().scrape(base, client)

    p = asyncio.run(run())
    assert p.display_name == "Jane Doe"
    assert "Berlin" in (p.bio or "")
    assert p.avatar_url == "https://example.com/avatar.jpg"
    sites = {h.site for h in p.extracted_handles}
    # rel=me Twitter, JSON-LD Instagram + Medium, og:description GitHub link
    assert {"Twitter", "Instagram", "Medium", "GitHub"}.issubset(sites)
