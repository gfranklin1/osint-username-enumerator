from __future__ import annotations

from collections import Counter
from itertools import combinations
from statistics import mean

from aliasgraph.models import AssertedAccount, Cluster, Profile
from aliasgraph.scoring import score_pair
from aliasgraph.scoring.features import Embedder
from aliasgraph.scoring.rarity import username_rarity

# Edges with score below `threshold` are dropped entirely.
# When admitting a new node into an existing cluster, require it to score
# at least `admission_min` against at least `admission_majority` of the
# current members. This prevents a chain (A-B 0.80, B-C 0.80, A-C 0.20)
# from collapsing strangers into one identity.
DEFAULT_ADMISSION_MAJORITY = 0.5
DEFAULT_ADMISSION_MIN_RATIO = 0.80  # admission_min = threshold * this


def build_clusters(
    profiles: list[Profile],
    *,
    threshold: float = 0.75,
    embedder: Embedder | None = None,
    admission_majority: float = DEFAULT_ADMISSION_MAJORITY,
) -> list[Cluster]:
    """Score every pair, then build clusters using a core-pair seeded greedy
    algorithm that respects pairwise consistency (no chain transitivity)."""
    if len(profiles) < 2:
        return []

    profiles = sorted(profiles, key=lambda p: p.key())
    pair_scores: dict[tuple[str, str], tuple[float, list[str]]] = {}
    for a, b in combinations(profiles, 2):
        score, evidence, _ = score_pair(a, b, embedder=embedder)
        if score >= threshold:
            pair_scores[(a.key(), b.key())] = (score, evidence)

    if not pair_scores:
        return []

    admission_min = threshold * DEFAULT_ADMISSION_MIN_RATIO

    # Sort edges high-to-low so high-confidence pairs (mutual cross-links) seed
    # clusters before weaker edges try to merge things.
    edges_sorted = sorted(
        pair_scores.items(),
        key=lambda kv: kv[1][0],
        reverse=True,
    )

    # member_key -> cluster index in `clusters`
    membership: dict[str, int] = {}
    clusters_members: list[set[str]] = []

    def score_between(x: str, y: str) -> float | None:
        if x == y:
            return None
        key = (x, y) if (x, y) in pair_scores else (y, x)
        rec = pair_scores.get(key)
        return rec[0] if rec else None

    def majority_score_above(node: str, members: set[str]) -> bool:
        eligible = [m for m in members if m != node]
        if not eligible:
            return True
        passing = 0
        for m in eligible:
            s = score_between(node, m)
            if s is not None and s >= admission_min:
                passing += 1
        return (passing / len(eligible)) >= admission_majority

    def majority_score_above_for_each(merge_a: set[str], merge_b: set[str]) -> bool:
        """Every member of A must satisfy majority against B and vice versa."""
        for m in merge_a:
            if not majority_score_above(m, merge_b):
                return False
        for m in merge_b:
            if not majority_score_above(m, merge_a):
                return False
        return True

    for (u, v), (_score, _ev) in edges_sorted:
        cu = membership.get(u)
        cv = membership.get(v)
        if cu is None and cv is None:
            clusters_members.append({u, v})
            idx = len(clusters_members) - 1
            membership[u] = idx
            membership[v] = idx
        elif cu is not None and cv is None:
            if majority_score_above(v, clusters_members[cu]):
                clusters_members[cu].add(v)
                membership[v] = cu
        elif cu is None and cv is not None:
            if majority_score_above(u, clusters_members[cv]):
                clusters_members[cv].add(u)
                membership[u] = cv
        elif cu != cv:
            # Merge two clusters only if the merge is consistent on both sides.
            if majority_score_above_for_each(clusters_members[cu], clusters_members[cv]):
                merged = clusters_members[cu] | clusters_members[cv]
                clusters_members[cu] = merged
                for m in clusters_members[cv]:
                    membership[m] = cu
                clusters_members[cv] = set()

    out: list[Cluster] = []
    profile_by_key = {p.key(): p for p in profiles}
    cid = 0
    for nodes in clusters_members:
        if len(nodes) < 2:
            continue
        cid += 1
        # All edges that survived the threshold and live entirely within `nodes`.
        cluster_edges = [
            (u, v, s, ev)
            for (u, v), (s, ev) in pair_scores.items()
            if u in nodes and v in nodes
        ]
        if not cluster_edges:
            continue
        confidence = round(mean(s for _, _, s, _ in cluster_edges), 4)
        members = sorted(
            (profile_by_key[k] for k in nodes if k in profile_by_key),
            key=lambda p: p.key(),
        )
        evidence = _summarize_cluster(members)
        asserted = _collect_asserted(members)
        out.append(
            Cluster(
                cluster_id=cid,
                confidence=confidence,
                members=[f"{m.site}:{m.username}" for m in members],
                asserted=asserted,
                evidence=evidence,
            )
        )
    out.sort(key=lambda c: -c.confidence)
    for i, c in enumerate(out, 1):
        c.cluster_id = i
    return out


def _summarize_cluster(members: list[Profile]) -> list[str]:
    """Produce a short, human-readable evidence list for the cluster."""
    if not members:
        return []
    lines: list[str] = []

    # 1. Exact-username consensus
    handles = {m.username.lower() for m in members}
    if len(handles) == 1:
        u = members[0].username
        rarity = username_rarity(u)
        if rarity >= 0.30:
            tag = "rare" if rarity >= 0.55 else "uncommon"
            lines.append(
                f"Same {tag} username '{u}' across all {len(members)} profiles (rarity {rarity:.2f})"
            )
        else:
            lines.append(f"Same username '{u}' across all {len(members)} profiles")
    else:
        # multiple distinct usernames in cluster (e.g. crosslink-driven merge)
        sample = ", ".join(sorted(handles)[:5])
        more = "" if len(handles) <= 5 else f" (+{len(handles) - 5} more)"
        lines.append(f"Usernames present: {sample}{more}")

    # 2. Inside-cluster crosslinks (out-of-cluster ones become AssertedAccounts).
    crosslinks: list[str] = []
    member_keys = {m.key() for m in members}
    seen_pairs: set[tuple[str, str]] = set()
    for m in members:
        for h in m.extracted_handles:
            target = f"{h.site}:{h.handle}".lower()
            if target == m.key() or target not in member_keys:
                continue
            pair = tuple(sorted([m.key(), target]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            crosslinks.append(f"{m.site}:{m.username} ↔ {h.site}:{h.handle}")
    if crosslinks:
        for cl in crosslinks[:8]:
            lines.append(f"Crosslink: {cl}")
        if len(crosslinks) > 8:
            lines.append(f"… (+{len(crosslinks) - 8} more crosslinks)")

    # 3. Display-name variants
    names = sorted({m.display_name.strip() for m in members if m.display_name})
    if names:
        # Filter out per-platform page titles like "Profile" / "Dailymotion" / "Yandex Маркет".
        clean = [
            n for n in names
            if len(n) >= 3 and not _looks_like_page_title(n, [m.site for m in members])
        ]
        if clean:
            sample = ", ".join(f"'{n}'" for n in clean[:4])
            more = "" if len(clean) <= 4 else f" (+{len(clean) - 4} more)"
            lines.append(f"Display names seen: {sample}{more}")

    # 4. Bios — show the longest non-empty bio as evidence
    bios = sorted(
        ((m.bio.strip(), m.site) for m in members if m.bio and len(m.bio.strip()) >= 25),
        key=lambda b: -len(b[0]),
    )
    if bios:
        bio, site = bios[0]
        snippet = bio if len(bio) <= 160 else bio[:157] + "…"
        lines.append(f"Bio ({site}): \"{snippet}\"")

    # 5. Locations
    locs = sorted({m.location.strip() for m in members if m.location})
    if locs:
        sample = ", ".join(f"'{l}'" for l in locs[:3])
        lines.append(f"Locations: {sample}")

    # 6. Distinct outbound links seen
    all_links: Counter[str] = Counter()
    for m in members:
        for u in m.links:
            all_links[u] += 1
    if all_links:
        common = [u for u, _ in all_links.most_common(3)]
        lines.append(f"Outbound links collected: {len(all_links)} (top: {', '.join(common)})")

    return lines


def _collect_asserted(members: list[Profile]) -> list[AssertedAccount]:
    """Gather extracted_handles that don't match any cluster member as asserted accounts."""
    member_keys = {m.key() for m in members}
    by_target: dict[tuple[str, str], AssertedAccount] = {}
    for m in members:
        for h in m.extracted_handles:
            target_key = f"{h.site}:{h.handle}".lower()
            if target_key in member_keys:
                continue
            k = (h.site.lower(), h.handle.lower())
            asserter = f"{m.site}:{m.username}"
            if k in by_target:
                if asserter not in by_target[k].asserted_by:
                    by_target[k].asserted_by.append(asserter)
            else:
                by_target[k] = AssertedAccount(
                    site=h.site,
                    handle=h.handle,
                    url=h.source_url,
                    asserted_by=[asserter],
                )
    return sorted(by_target.values(), key=lambda a: (a.site.lower(), a.handle.lower()))


def _looks_like_page_title(name: str, sites: list[str]) -> bool:
    n = name.strip().lower()
    for s in sites:
        sl = s.strip().lower()
        if n == sl or n.startswith(sl + " ") or n.endswith(" " + sl):
            return True
        if n in {"profile", "dailymotion", "instagram", "trello", "imgur"}:
            return True
    return False
