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
    if not a or not b:
        return 0.0
    return max(fuzz.ratio(a, b), fuzz.token_set_ratio(a, b)) / 100.0


def _username_sim(a: Profile, b: Profile) -> float:
    return _ratio(a.username.lower(), b.username.lower())


def _display_sim(a: Profile, b: Profile) -> float:
    da = (a.display_name or a.username).lower()
    db = (b.display_name or b.username).lower()
    return _ratio(da, db)


def _bio_sim(a: Profile, b: Profile, embedder: Embedder | None) -> float:
    if not a.bio or not b.bio:
        return 0.0
    if embedder is not None:
        v = embedder.similarity(a.bio, b.bio)
        if v is not None:
            return float(v)
    # Token-set rapidfuzz with generic-token penalty
    base = fuzz.token_set_ratio(a.bio.lower(), b.bio.lower()) / 100.0
    a_tokens = {t for t in _tokens(a.bio) if t not in GENERIC_BIO_TOKENS}
    b_tokens = {t for t in _tokens(b.bio) if t not in GENERIC_BIO_TOKENS}
    if not a_tokens or not b_tokens:
        return base * 0.5
    jacc = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    return max(base, jacc)


def _tokens(s: str) -> list[str]:
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in s).split() if len(t) > 1]


def _location_sim(a: Profile, b: Profile) -> float:
    if not a.location or not b.location:
        return 0.0
    return _ratio(a.location.lower(), b.location.lower())


def _link_overlap(a: Profile, b: Profile) -> float:
    la = {x.lower() for x in a.links}
    lb = {x.lower() for x in b.links}
    if not la and not lb:
        return 0.0
    union = la | lb
    if not union:
        return 0.0
    return len(la & lb) / len(union)


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
        avatar_similarity=hamming_similarity(a.avatar_hash, b.avatar_hash),
        crosslink_strength=_crosslink(a, b),
    )
