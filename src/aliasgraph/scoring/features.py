from __future__ import annotations

from typing import Protocol

from rapidfuzz import fuzz

from aliasgraph.models import MatchFeatures, Profile
from aliasgraph.scraping.avatar import hamming_similarity

# Tokens that should not be allowed to inflate similarity by themselves.
GENERIC_BIO_TOKENS = {
    "developer", "engineer", "student", "gamer", "writer", "musician",
    "designer", "artist", "creator", "founder", "ceo", "cto", "dev",
    "programmer", "coder", "hacker", "geek", "nerd", "fan", "lover",
    "and", "or", "of", "the", "a", "an", "i", "my", "me", "is",
}


class Embedder(Protocol):
    def similarity(self, a: str | None, b: str | None) -> float | None: ...


def _ratio(a: str | None, b: str | None) -> float:
    """Best-of two rapidfuzz string-similarity scores in [0, 1].

    Used for username, display-name, and location comparisons. ``token_set_ratio``
    mostly matters for multi-word display names (e.g. "Linus Torvalds" vs
    "Torvalds, Linus"); for usernames without whitespace it collapses to ``ratio``.
    """
    if not a or not b:
        return 0.0
    return max(fuzz.ratio(a, b), fuzz.token_set_ratio(a, b)) / 100.0


def _username_sim(a: Profile, b: Profile) -> float:
    return _ratio(a.username.lower(), b.username.lower())


def _display_sim(a: Profile, b: Profile) -> float:
    da = (a.display_name or a.username).lower()
    db = (b.display_name or b.username).lower()
    return _ratio(da, db)


def _bio_sim(a: Profile, b: Profile, embedder: Embedder | None) -> float | None:
    """Bio similarity in [0, 1], or None if either bio is missing.

    Strategy:
    1. If an embedder is configured, use cosine similarity of sentence vectors.
    2. Otherwise fall back to rapidfuzz token_set_ratio combined with a
       Jaccard score over non-generic tokens, taking the max.
    3. If both bios are entirely composed of generic tokens (e.g. "developer
       and engineer"), the score is multiplied by 0.5 — generic vocabulary
       matching is weak evidence on its own.
    """
    if not a.bio or not b.bio:
        return None
    if embedder is not None:
        v = embedder.similarity(a.bio, b.bio)
        if v is not None:
            return float(v)
    base = fuzz.token_set_ratio(a.bio.lower(), b.bio.lower()) / 100.0
    a_tokens = {t for t in _tokens(a.bio) if t not in GENERIC_BIO_TOKENS}
    b_tokens = {t for t in _tokens(b.bio) if t not in GENERIC_BIO_TOKENS}
    if not a_tokens or not b_tokens:
        return base * 0.5
    jacc = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    return max(base, jacc)


def _tokens(s: str) -> list[str]:
    """Lowercase alphanumeric tokens with single-char tokens dropped (kills 'a'/'i' noise)."""
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(t) > 1]


def _location_sim(a: Profile, b: Profile) -> float | None:
    if not a.location or not b.location:
        return None
    return _ratio(a.location.lower(), b.location.lower())


def _link_overlap(a: Profile, b: Profile) -> float | None:
    """Jaccard overlap of normalized outbound links, or None if both sides are empty."""
    la = {x.lower() for x in a.links}
    lb = {x.lower() for x in b.links}
    if not la and not lb:
        return None
    union = la | lb
    if not union:
        return None
    return len(la & lb) / len(union)


def _avatar_sim(a: Profile, b: Profile) -> float | None:
    if not a.avatar_hash or not b.avatar_hash:
        return None
    return hamming_similarity(a.avatar_hash, b.avatar_hash)


def _crosslink(a: Profile, b: Profile) -> str:
    a_to_b = any(
        h.site.lower() == b.site.lower() and h.handle.lower() == b.username.lower()
        for h in a.extracted_handles
    )
    b_to_a = any(
        h.site.lower() == a.site.lower() and h.handle.lower() == a.username.lower()
        for h in b.extracted_handles
    )
    if a_to_b and b_to_a:
        return "mutual"
    if a_to_b or b_to_a:
        return "one_way"
    return "none"


def pairwise_features(
    a: Profile, b: Profile, *, embedder: Embedder | None = None
) -> MatchFeatures:
    return MatchFeatures(
        username_similarity=_username_sim(a, b),
        display_name_similarity=_display_sim(a, b),
        bio_similarity=_bio_sim(a, b, embedder),
        link_overlap_score=_link_overlap(a, b),
        location_similarity=_location_sim(a, b),
        avatar_similarity=_avatar_sim(a, b),
        crosslink_strength=_crosslink(a, b),
    )
