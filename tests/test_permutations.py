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


def test_numeric_suffixes_applied_to_alpha_bases():
    out = generate(
        "alphabase",
        numeric_suffixes=["2005"],
        max_candidates=20,
    )
    assert "alphabase2005" in out
    assert "alphabase_2005" in out


def test_numeric_suffix_skipped_on_numeric_base():
    out = generate(
        "2005",
        numeric_suffixes=["2005"],
        max_candidates=20,
    )
    assert "20052005" not in out
    assert "2005_2005" not in out


def test_max_candidates_short_circuits():
    # With a very low cap and many possible variants, generate() must
    # respect the cap (no overflow then slice).
    out = generate(
        "seed",
        first="jacob",
        last="hauptman",
        numeric_suffixes=["1", "2", "3", "4"],
        max_candidates=5,
    )
    assert len(out) == 5
