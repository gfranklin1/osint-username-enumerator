from __future__ import annotations

from collections.abc import Iterable

SEPARATORS = ("", ".", "_", "-")


def _clean(s: str | None) -> str:
    return (s or "").strip().lower()


def generate(
    seed: str,
    first: str | None = None,
    last: str | None = None,
    aliases: Iterable[str] = (),
    numeric_suffixes: Iterable[str] = (),
    max_candidates: int = 100,
) -> list[str]:
    """Generate a bounded, deterministic list of likely username variants."""
    seed_c = _clean(seed)
    first_c = _clean(first)
    last_c = _clean(last)
    alias_list = [_clean(a) for a in aliases if _clean(a)]
    suffixes = [s for s in numeric_suffixes if s]

    out: list[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or u in seen:
            return
        seen.add(u)
        out.append(u)

    add(seed_c)
    for a in alias_list:
        add(a)

    if first_c and last_c:
        for sep in SEPARATORS:
            add(f"{first_c}{sep}{last_c}")
            add(f"{last_c}{sep}{first_c}")
        add(f"{first_c[0]}{last_c}")
        add(f"{first_c[0]}.{last_c}")
        add(f"{first_c}{last_c[0]}")
        add(f"{last_c}{first_c[0]}")
    elif first_c:
        add(first_c)
    elif last_c:
        add(last_c)

    bases = list(out)
    for base in bases:
        for suf in suffixes:
            add(f"{base}{suf}")
            add(f"{base}_{suf}")

    return out[:max_candidates]
