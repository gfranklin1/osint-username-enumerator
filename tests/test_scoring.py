from aliasgraph.models import ExtractedHandle, Profile
from aliasgraph.scoring import score_pair


def _profile(site, username, **kw) -> Profile:
    return Profile(site=site, url=f"https://{site.lower()}.com/{username}", username=username, **kw)


def test_mutual_crosslink_scores_at_least_99():
    a = _profile(
        "GitHub", "torvalds",
        display_name="Linus Torvalds",
        bio="Linux kernel maintainer",
        extracted_handles=[ExtractedHandle(site="Twitter", handle="Linus__Torvalds", source_url="x")],
    )
    b = _profile(
        "Twitter", "Linus__Torvalds",
        display_name="Linus Torvalds",
        bio="Linux kernel maintainer",
        extracted_handles=[ExtractedHandle(site="GitHub", handle="torvalds", source_url="x")],
    )
    score, evidence, _ = score_pair(a, b)
    assert score >= 0.99
    assert any("Mutual cross-link" in e for e in evidence)


def test_one_way_crosslink_boosts_score():
    a = _profile(
        "GitHub", "ben",
        display_name="Ben Halpern",
        bio="Cofounder of forem; based in Brooklyn, NY",
        extracted_handles=[ExtractedHandle(site="Dev.to", handle="ben", source_url="x")],
    )
    b = _profile(
        "Dev.to", "ben",
        display_name="Ben Halpern",
        bio="Cofounder of forem; based in Brooklyn, NY",
    )
    score, evidence, _ = score_pair(a, b)
    assert score >= 0.75
    assert any("One-way cross-link" in e for e in evidence)


def test_similar_bio_and_displayname_above_threshold():
    a = _profile("GitHub", "alice", display_name="Alice Wong", bio="Photographer based in Berlin shooting analog film")
    b = _profile("Instagram", "alice", display_name="Alice Wong", bio="Photographer based in Berlin shooting analog film")
    score, _, _ = score_pair(a, b)
    assert score >= 0.5  # high without crosslinks but threshold is generous


def test_username_only_with_generic_bios_low_score():
    a = _profile("GitHub", "jdoe", display_name="John Doe", bio="developer")
    b = _profile("Reddit", "jdoe", display_name="Jane D", bio="student")
    score, _, _ = score_pair(a, b)
    assert score < 0.6
