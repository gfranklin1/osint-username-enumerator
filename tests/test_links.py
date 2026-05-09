import pytest

from aliasgraph.scraping.links import (
    extract_urls_from_text,
    normalize,
    parse_handle,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://Twitter.com/Foo/", "https://twitter.com/Foo"),
        ("HTTP://www.GitHub.com/torvalds?utm_source=x&id=1", "http://github.com/torvalds?id=1"),
        ("https://example.com/path/#frag", "https://example.com/path"),
        ("https://example.com/?utm_medium=x&fbclid=y", "https://example.com/"),
        ("javascript:alert(1)", None),
        ("mailto:a@b.com", None),
        ("not a url", None),
    ],
)
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_extract_urls():
    text = "ping me at https://twitter.com/foo or https://github.com/foo!"
    out = extract_urls_from_text(text)
    assert "https://twitter.com/foo" in out
    assert "https://github.com/foo" in out


@pytest.mark.parametrize(
    "url, site, handle",
    [
        ("https://github.com/torvalds", "GitHub", "torvalds"),
        ("https://gist.github.com/torvalds", "GitHubGist", "torvalds"),
        ("https://twitter.com/Linus__Torvalds", "Twitter", "Linus__Torvalds"),
        ("https://x.com/Linus__Torvalds", "Twitter", "Linus__Torvalds"),
        ("https://www.linkedin.com/in/jane-doe", "LinkedIn", "jane-doe"),
        ("https://reddit.com/user/spez", "Reddit", "spez"),
        ("https://www.reddit.com/u/spez/", "Reddit", "spez"),
        ("https://instagram.com/janedoe", "Instagram", "janedoe"),
        ("https://dev.to/ben", "Dev.to", "ben"),
        ("https://www.tiktok.com/@charlidamelio", "TikTok", "charlidamelio"),
        ("https://medium.com/@gvanrossum", "Medium", "gvanrossum"),
        ("https://mastodon.social/@dansup", "Mastodon", "dansup"),
        ("https://news.ycombinator.com/user?id=pg", "HackerNews", "pg"),
    ],
)
def test_parse_handle(url, site, handle):
    h = parse_handle(url)
    assert h is not None, url
    assert h.site == site
    assert h.handle == handle


def test_parse_handle_unknown_returns_none():
    assert parse_handle("https://random-site.example/profile") is None
