from aliasgraph.clustering import build_clusters
from aliasgraph.models import ExtractedHandle, Profile


def _p(site, username, **kw):
    return Profile(site=site, url=f"https://{site.lower()}.com/{username}", username=username, **kw)


def test_mutual_crosslink_yields_one_cluster():
    a = _p(
        "GitHub", "torvalds",
        display_name="Linus Torvalds",
        bio="Linux kernel maintainer",
        extracted_handles=[ExtractedHandle(site="Twitter", handle="Linus__Torvalds", source_url="x")],
    )
    b = _p(
        "Twitter", "Linus__Torvalds",
        display_name="Linus Torvalds",
        bio="Linux kernel maintainer",
        extracted_handles=[ExtractedHandle(site="GitHub", handle="torvalds", source_url="x")],
    )
    c = _p("Reddit", "totallyunrelated", bio="random gamer")
    clusters = build_clusters([a, b, c], threshold=0.75)
    assert len(clusters) == 1
    assert {"GitHub:torvalds", "Twitter:Linus__Torvalds"} == set(clusters[0].members)
    assert clusters[0].confidence >= 0.99


def test_no_clusters_when_below_threshold():
    a = _p("GitHub", "alice", bio="developer")
    b = _p("Reddit", "bob", bio="student")
    clusters = build_clusters([a, b], threshold=0.75)
    assert clusters == []


def test_rare_username_clusters_when_corroborated():
    # Rare exact handle PLUS at least one real signal (bio / display match) per pair.
    bio = "Studying CS and Math at the University of Maryland."
    a = _p("GitHub", "allarkvarkk", display_name="Garrett Franklin", bio=bio)
    b = _p("Substack", "allarkvarkk", display_name="G Franklin")
    c = _p("Spotify", "allarkvarkk", display_name="Garrett F.", bio=bio)
    clusters = build_clusters([a, b, c], threshold=0.75)
    assert len(clusters) == 1
    assert {"GitHub:allarkvarkk", "Substack:allarkvarkk", "Spotify:allarkvarkk"}.issubset(
        set(clusters[0].members)
    )


def test_rare_username_alone_does_not_cluster_strangers():
    # No corroborating signal — username match should NOT be enough.
    a = _p("GitHub", "allarkvarkk", display_name="Garrett Franklin")
    b = _p("Spotify", "allarkvarkk", display_name="allarkvarkk")
    clusters = build_clusters([a, b], threshold=0.75)
    assert clusters == []


def test_chain_transitivity_does_not_collapse_strangers():
    # B is similar to A and to C, but A is not similar to C → cluster must NOT include all three.
    a = _p("GitHub", "ben",
           display_name="Ben Halpern",
           bio="Cofounder of forem in Brooklyn",
           extracted_handles=[ExtractedHandle(site="Dev.to", handle="ben", source_url="x")])
    b = _p("Dev.to", "ben",
           display_name="Ben Halpern",
           bio="Cofounder of forem in Brooklyn",
           extracted_handles=[ExtractedHandle(site="GitHub", handle="ben", source_url="x")])
    # C shares username and is bridged by B but is otherwise unrelated.
    c = _p("Reddit", "ben", display_name="Ben Edwards", bio="Photographer in Berlin shooting analog film")
    clusters = build_clusters([a, b, c], threshold=0.75)
    assert len(clusters) == 1
    members = set(clusters[0].members)
    assert "GitHub:ben" in members and "Dev.to:ben" in members
    assert "Reddit:ben" not in members
