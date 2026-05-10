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

    def add(u: str) -> bool:
        """Append `u` if new. Returns False once max_candidates is reached so
        callers can short-circuit."""
        if len(out) >= max_candidates:
            return False
        if not u or u in seen:
            return True
        seen.add(u)
        out.append(u)
        return True

    if not add(seed_c):
        return out
    for a in alias_list:
        if not add(a):
            return out

    if first_c and last_c:
        for sep in SEPARATORS:
            if not add(f"{first_c}{sep}{last_c}"):
                return out
            if not add(f"{last_c}{sep}{first_c}"):
                return out
        for u in (
            f"{first_c[0]}{last_c}",
            f"{first_c[0]}.{last_c}",
            f"{first_c}{last_c[0]}",
            f"{last_c}{first_c[0]}",
        ):
            if not add(u):
                return out
    elif first_c:
        if not add(first_c):
            return out
    elif last_c:
        if not add(last_c):
            return out

    bases = list(out)
    for base in bases:
        if base.isdigit():
            # Appending a numeric suffix to "2005" produces "20052005" — never
            # useful, always wastes a candidate slot.
            continue
        for suf in suffixes:
            if not add(f"{base}{suf}"):
                return out
            if not add(f"{base}_{suf}"):
                return out

    return out
