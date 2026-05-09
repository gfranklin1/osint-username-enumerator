from aliasgraph.models import ExtractedHandle, Profile
from aliasgraph.scraping.validation import (
    looks_like_error_page,
    looks_like_site_title,
    profile_quality,
    is_garbled_profile,
)


def _p(site, username, **kw) -> Profile:
    return Profile(site=site, url=f"https://{site.lower()}.com/{username}", username=username, **kw)


def test_error_pages_detected():
    assert looks_like_error_page("Channel Not Found - Kick Streaming")
    assert looks_like_error_page("Steam Community :: Error")
    assert looks_like_error_page("Page Does Not Exist")
    assert not looks_like_error_page("Garrett Franklin")


def test_site_titles_detected():
    assert looks_like_site_title("OP.GG - The Best LoL Builds & Stats", "OP.GG", "alice")
    assert looks_like_site_title("TikTok - Make Your Day", "TikTok", "alice")
    # username present → not a generic site title
    assert not looks_like_site_title("alice • Instagram photos", "Instagram", "alice")


def test_quality_high_for_real_profile():
    p = _p(
        "GitHub", "gfranklin1",
        display_name="Garrett Franklin",
        bio="Studying Computer Science and Math at the University of Maryland.",
        location="College Park, MD",
        avatar_url="https://avatars.githubusercontent.com/u/123",
        extracted_handles=[ExtractedHandle(site="LinkedIn", handle="garrettfranklin0", source_url="https://linkedin.com/in/garrettfranklin0")],
    )
    assert profile_quality(p) >= 0.80


def test_quality_zero_for_error_page():
    p = _p("Kick", "gfranklin1", display_name="Channel Not Found - Kick Streaming")
    assert profile_quality(p) == 0.0


def test_quality_zero_for_landing_page():
    p = _p("OP.GG", "gfranklin1",
           display_name="OP.GG - The Best LoL Builds & Stats",
           bio="The Best LoL Champion Builds and Player Stats by OP.GG")
    # Site title display + boilerplate-ish bio → should be very low.
    assert profile_quality(p) < 0.30


def test_quality_low_for_username_only():
    p = _p("Spotify", "gfranklin1", display_name="gfranklin1")
    # Display name is just the username — weak signal only.
    assert profile_quality(p) < 0.30


def test_garbled_text_detection():
    p = _p("yamaya.ru", "gfranklin1", display_name="��������� ���� � ��������")
    assert is_garbled_profile(p)
