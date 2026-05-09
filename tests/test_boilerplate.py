from aliasgraph.scraping.boilerplate import clean_bio, is_platform_boilerplate


def test_imgur_tagline_is_boilerplate():
    assert is_platform_boilerplate("Imgur: The magic of the Internet", "alice")
    assert clean_bio("Imgur: The magic of the Internet", "alice") is None


def test_per_user_overview_is_boilerplate():
    assert is_platform_boilerplate(
        "Overview of allarkvarkk activities, statistics", "allarkvarkk"
    )


def test_real_bio_is_kept():
    bio = "Studying CS and Math at the University of Maryland."
    assert not is_platform_boilerplate(bio, "gfranklin1")
    assert clean_bio(bio, "gfranklin1") == bio


def test_user_on_site_pattern_filtered():
    assert is_platform_boilerplate("ben on Trello", "ben", site="Trello")
