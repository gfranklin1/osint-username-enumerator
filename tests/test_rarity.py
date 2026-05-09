from aliasgraph.scoring.rarity import username_rarity


def test_common_handles_are_zero():
    assert username_rarity("ben") == 0.0
    assert username_rarity("john") == 0.0
    assert username_rarity("admin") == 0.0


def test_long_unusual_handles_score_high():
    assert username_rarity("allarkvarkk") > 0.85
    assert username_rarity("gfranklin1") > 0.55


def test_short_handles_low_unless_unusual():
    assert username_rarity("foo") < 0.20
    assert username_rarity("xyz") < 0.20


def test_repeated_chars_capped_low():
    assert username_rarity("aaaaaaaa") <= 0.25
