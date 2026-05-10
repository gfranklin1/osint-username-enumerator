from __future__ import annotations

from aliasgraph.models import MatchFeatures, Profile
from aliasgraph.scoring.features import Embedder, pairwise_features
from aliasgraph.scoring.rarity import username_rarity

# Six base feature weights, summing to exactly 1.0. The pairwise score is a
# weighted average over the *present* features — see ``score_pair`` for the
# renormalization, which is why a profile pair missing a bio doesn't get
# silently penalized 0.21 of weight.
BASE_WEIGHTS: dict[str, float] = {
    "username_similarity":      0.18,
    "display_name_similarity":  0.16,
    "bio_similarity":           0.21,
    "link_overlap":             0.21,
    "location_similarity":      0.05,
    "avatar_similarity":        0.19,
}

# Additive contribution applied once for a one-way crosslink, on top of the
# weighted average. Mutual crosslinks bypass the average entirely (see
# MUTUAL_FLOOR). Kept separate from BASE_WEIGHTS so the sum stays clean.
ONE_WAY_BOOST = 0.25

# Score reserved for "the profiles literally point at each other".
MUTUAL_FLOOR = 0.99
# Hard ceiling on a one-way crosslink so it stays distinguishable from mutual.
ONE_WAY_CAP = 0.95
# Reserve the [0.97, 0.99) gap for explicit-evidence scoring; weighted-only
# matches cap at 0.97 so a one-way crosslink at 0.95 stays clearly ranked
# below a "mostly evidence" 0.97.
WEIGHTED_CAP = 0.97
# Pairs of pHash strings within ~6 differing bits (≥ 0.93 similarity) are
# treated as the same image.
AVATAR_MATCH_FLOOR = 0.93


def _exact_rare_boost(rarity: float) -> float:
    """Step contribution for an exact-username match across platforms.

    The thresholds correspond roughly to:
      - 0.85: long, unusual handles (e.g. "x7q3kbz", "allarkvarkk").
      - 0.55: 7+ character handles with at least some unusual structure.
      - 0.30: mildly distinctive handles (not in the common-handle list).

    A common short handle ("ben", "alex", "test") returns 0.0 — never enough
    evidence on its own.
    """
    if rarity >= 0.85:
        return 0.60
    if rarity >= 0.55:
        return 0.40
    if rarity >= 0.30:
        return 0.20
    return 0.0


def _weighted_average(features: MatchFeatures) -> float:
    """Sum(w_i * f_i) / Sum(w_i) over the features that have data on both sides.

    Username and display_name similarities are always present, so the
    denominator is bounded below by their combined weight (~0.34) and the
    division is always safe.
    """
    pairs: list[tuple[float, float]] = [
        (BASE_WEIGHTS["username_similarity"], features.username_similarity),
        (BASE_WEIGHTS["display_name_similarity"], features.display_name_similarity),
    ]
    if features.bio_similarity is not None:
        pairs.append((BASE_WEIGHTS["bio_similarity"], features.bio_similarity))
    if features.link_overlap_score is not None:
        pairs.append((BASE_WEIGHTS["link_overlap"], features.link_overlap_score))
    if features.location_similarity is not None:
        pairs.append((BASE_WEIGHTS["location_similarity"], features.location_similarity))
    if features.avatar_similarity is not None:
        pairs.append((BASE_WEIGHTS["avatar_similarity"], features.avatar_similarity))
    weight_sum = sum(w for w, _ in pairs)
    score_sum = sum(w * v for w, v in pairs)
    return score_sum / weight_sum if weight_sum > 0 else 0.0


def score_pair(
    a: Profile, b: Profile, *, embedder: Embedder | None = None
) -> tuple[float, list[str], MatchFeatures]:
    f = pairwise_features(a, b, embedder=embedder)
    evidence: list[str] = []

    weighted = _weighted_average(f)

    # Rare-username prior: if both profiles share the *exact* same handle and
    # that handle is uncommon, that alone is strong evidence. Scaled by rarity.
    if a.username.lower() == b.username.lower():
        # Both usernames are equal (case-insensitive) and rarity is
        # case-insensitive, so a single call suffices.
        rarity = username_rarity(a.username)
        boost = _exact_rare_boost(rarity)
        # Require at least one corroborating signal so the rare-username prior
        # alone can never drag two strangers into a cluster.
        corroborated = (
            (f.bio_similarity or 0.0) >= 0.40
            or f.display_name_similarity >= 0.55
            or (f.avatar_similarity or 0.0) >= AVATAR_MATCH_FLOOR
            or (f.link_overlap_score or 0.0) > 0
            or (f.location_similarity or 0.0) >= 0.85
            or f.crosslink_strength != "none"
        )
        if boost > 0 and corroborated:
            # A rare exact-username match alone never adds score — without any
            # other signal we can't distinguish coincidence from identity.
            # With renormalization (missing features dropped from the
            # denominator), an unbounded standalone boost would push sparse
            # strangers across the cluster threshold; keep it gated.
            weighted += boost
            if rarity >= 0.55:
                evidence.append(
                    f"Exact rare-username match '{a.username}' across {a.site} and {b.site}"
                )
    weighted = min(weighted, WEIGHTED_CAP)

    if f.crosslink_strength == "mutual":
        evidence.append(f"Mutual cross-link between {a.site}:{a.username} and {b.site}:{b.username}")
        score = max(MUTUAL_FLOOR, weighted)
    elif f.crosslink_strength == "one_way":
        evidence.append(f"One-way cross-link between {a.site}:{a.username} and {b.site}:{b.username}")
        score = min(ONE_WAY_CAP, weighted + ONE_WAY_BOOST)
    else:
        score = weighted

    if (f.link_overlap_score or 0.0) > 0.0:
        shared = sorted(set(a.links) & set(b.links))
        if shared:
            evidence.append(
                f"Shared link: {shared[0]}"
                + (f" (+{len(shared) - 1} more)" if len(shared) > 1 else "")
            )
    if f.display_name_similarity >= 0.85 and a.display_name and b.display_name:
        evidence.append(f"Same display name '{a.display_name}'")
    if (f.bio_similarity or 0.0) >= 0.70:
        evidence.append("Similar bio text")
    if (f.location_similarity or 0.0) >= 0.85 and a.location and b.location:
        evidence.append(f"Same location '{a.location}'")
    if (f.avatar_similarity or 0.0) >= AVATAR_MATCH_FLOOR:
        evidence.append(
            f"Same avatar (pHash similarity {f.avatar_similarity:.0%})"
        )
    if f.username_similarity >= 0.85 and a.username.lower() != b.username.lower():
        evidence.append(f"Similar usernames '{a.username}' / '{b.username}'")

    return score, evidence, f
