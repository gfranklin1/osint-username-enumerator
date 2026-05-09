from __future__ import annotations

from aliasgraph.models import MatchFeatures, Profile
from aliasgraph.scoring.features import Embedder, pairwise_features
from aliasgraph.scoring.rarity import username_rarity

WEIGHTS = {
    "username_similarity": 0.15,
    "display_name_similarity": 0.15,
    "bio_similarity": 0.20,
    "link_overlap": 0.20,
    "location_similarity": 0.05,
    "avatar_similarity": 0.20,
    "crosslink_one_way_boost": 0.25,
}

AVATAR_MATCH_FLOOR = 0.93  # ≥6 differing bits in 64 still treated as same image


def _exact_rare_boost(rarity: float) -> float:
    """Step-function contribution for an exact-username match across platforms.

    A long, unusual handle is itself strong evidence; common handles get nothing.
    """
    if rarity >= 0.85:
        return 0.60
    if rarity >= 0.55:
        return 0.40
    if rarity >= 0.30:
        return 0.20
    return 0.0

MUTUAL_FLOOR = 0.99
ONE_WAY_CAP = 0.95


def score_pair(
    a: Profile, b: Profile, *, embedder: Embedder | None = None
) -> tuple[float, list[str], MatchFeatures]:
    f = pairwise_features(a, b, embedder=embedder)
    evidence: list[str] = []

    weighted = (
        WEIGHTS["username_similarity"] * f.username_similarity
        + WEIGHTS["display_name_similarity"] * f.display_name_similarity
        + WEIGHTS["bio_similarity"] * f.bio_similarity
        + WEIGHTS["link_overlap"] * f.link_overlap_score
        + WEIGHTS["location_similarity"] * f.location_similarity
        + WEIGHTS["avatar_similarity"] * f.avatar_similarity
    )

    # Rare-username prior: if both profiles share the *exact* same handle and
    # that handle is uncommon, that alone is strong evidence. Scaled by rarity.
    if a.username.lower() == b.username.lower():
        rarity = min(username_rarity(a.username), username_rarity(b.username))
        boost = _exact_rare_boost(rarity)
        # Require at least one corroborating signal so the rare-username prior
        # alone can never drag two strangers into a cluster: a real bio match,
        # a real display-name match, an avatar match, a shared link, a
        # location, or a cross-link.
        corroborated = (
            f.bio_similarity >= 0.40
            or f.display_name_similarity >= 0.55
            or f.avatar_similarity >= AVATAR_MATCH_FLOOR
            or f.link_overlap_score > 0
            or f.location_similarity >= 0.85
            or f.crosslink_strength != "none"
        )
        if boost > 0:
            if not corroborated:
                boost *= 0.30  # very small standalone contribution
            weighted += boost
            if rarity >= 0.55 and corroborated:
                evidence.append(
                    f"Exact rare-username match '{a.username}' across {a.site} and {b.site}"
                )
    weighted = min(weighted, 0.97)  # leave headroom; only crosslinks hit ≥0.99

    if f.crosslink_strength == "mutual":
        evidence.append(f"Mutual cross-link between {a.site}:{a.username} and {b.site}:{b.username}")
        score = max(MUTUAL_FLOOR, weighted)
    elif f.crosslink_strength == "one_way":
        evidence.append(f"One-way cross-link between {a.site}:{a.username} and {b.site}:{b.username}")
        score = min(ONE_WAY_CAP, weighted + WEIGHTS["crosslink_one_way_boost"])
    else:
        score = weighted

    if f.link_overlap_score > 0.0:
        shared = sorted(set(a.links) & set(b.links))
        if shared:
            evidence.append(f"Shared link: {shared[0]}" + (f" (+{len(shared) - 1} more)" if len(shared) > 1 else ""))
    if f.display_name_similarity >= 0.85 and a.display_name and b.display_name:
        evidence.append(f"Same display name '{a.display_name}'")
    if f.bio_similarity >= 0.70:
        evidence.append("Similar bio text")
    if f.location_similarity >= 0.85 and a.location and b.location:
        evidence.append(f"Same location '{a.location}'")
    if f.avatar_similarity >= AVATAR_MATCH_FLOOR:
        evidence.append(
            f"Same avatar (pHash similarity {f.avatar_similarity:.0%})"
        )
    if f.username_similarity >= 0.85 and a.username.lower() != b.username.lower():
        evidence.append(f"Similar usernames '{a.username}' / '{b.username}'")

    return score, evidence, f
