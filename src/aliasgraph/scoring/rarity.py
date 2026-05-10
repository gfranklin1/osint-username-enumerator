"""Heuristic for how unlikely a username is to belong to two different people.

Returns a value in [0, 1] where higher means rarer. The score is combined into
the pairwise scorer so that an exact match across platforms on a long, unusual
handle counts as strong evidence on its own — even when bios are missing.

Deliberately simple: no external corpus needed.
"""
from __future__ import annotations

import math

# Very common short handles or first-name handles. Add as needed.
_COMMON_HANDLES = {
    "admin", "user", "test", "demo", "guest", "info", "support", "hello",
    "ben", "tom", "max", "sam", "alex", "ana", "ali", "kim", "lee", "jon",
    "joe", "amy", "eva", "ann", "ron", "tim", "nick", "jane", "john", "mike",
    "matt", "kate", "luke", "ryan", "anna", "emma", "noah", "liam", "leo",
    "ace", "ash", "art", "art1", "user1", "test1",
}


def username_rarity(username: str) -> float:
    """Return a rarity score in [0, 1]. 1.0 = very rare; 0.0 = extremely common."""
    if not username:
        return 0.0
    u = username.strip().lower()
    if u in _COMMON_HANDLES:
        return 0.0

    length = len(u)
    if length <= 3:
        return 0.05
    if length <= 5:
        base = 0.25
    elif length <= 7:
        base = 0.55
    elif length <= 10:
        base = 0.80
    else:
        base = 0.92

    # Shannon entropy boost — gibberish like "x7q3kbz" is rarer than "matthew".
    # English text averages ~4.7 bits/char and English usernames cluster around
    # 2.8–3.2 bits/char; we use 2.5 as the "below typical" cutoff so usernames
    # with even modest randomness pick up bonus, scaled gently (0.10/bit) and
    # capped at 0.15 so it never dominates the length-based base.
    entropy = _shannon(u)
    entropy_bonus = max(0.0, min(0.15, (entropy - 2.5) * 0.10))

    # Mixed digits/letters bonus — real-name + suffix patterns ("gfranklin1").
    has_digit = any(c.isdigit() for c in u)
    has_alpha = any(c.isalpha() for c in u)
    mixed_bonus = 0.05 if (has_digit and has_alpha) else 0.0

    # Heavy repetition penalty (e.g. "aaaaaaaa"). Smoothed: 1 unique char is
    # always trivial; 2 unique chars is capped (covers "abab", "abba"); 3+
    # gets the full bonus stack.
    unique_chars = len(set(u))
    if unique_chars == 1:
        return 0.0
    if unique_chars == 2:
        return min(base, 0.25)

    return max(0.0, min(1.0, base + entropy_bonus + mixed_bonus))


def _shannon(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
