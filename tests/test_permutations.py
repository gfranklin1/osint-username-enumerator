from aliasgraph.permutations import generate


def test_seed_in_output():
    out = generate("jacobhauptman")
    assert "jacobhauptman" in out


def test_dedup_and_bound():
    out = generate(
        "jacobhauptman",
        first="Jacob",
        last="Hauptman",
        aliases=["jacobhauptman", "jacobhauptman"],
        numeric_suffixes=["2005", "1"],
        max_candidates=20,
    )
    assert len(out) == len(set(out))
    assert len(out) <= 20


def test_separator_variants():
    out = generate("seed", first="jacob", last="hauptman")
    assert "jacob.hauptman" in out
    assert "jacob_hauptman" in out
    assert "jacob-hauptman" in out
    assert "jacobhauptman" in out


def test_initials():
    out = generate("seed", first="jacob", last="hauptman")
    assert "jhauptman" in out


def test_alias_passthrough():
    out = generate("seed", aliases=["jacobmilo2005"])
    assert "jacobmilo2005" in out
