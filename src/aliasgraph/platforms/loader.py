from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files

from aliasgraph.models import PlatformConfig

SITES_RESOURCE = "sites.json"

# Match any {placeholder} not equal to {username}. We substitute these from the
# site definition (urlMain) when we can; otherwise the entry is skipped to avoid
# a runtime KeyError in str.format.
_OTHER_PLACEHOLDER_RE = re.compile(r"\{(?!username\})([^{}]+)\}")


class _UnresolvedPlaceholder(Exception):
    pass


def _resolve_placeholder(name: str, site: dict, url_main: str) -> str:
    name = name.strip()
    if name == "urlMain":
        if not url_main:
            raise _UnresolvedPlaceholder("urlMain")
        return url_main.rstrip("/") + "/"
    val = site.get(name)
    if isinstance(val, str):
        return val
    raise _UnresolvedPlaceholder(name)


def _raw_sites() -> dict[str, dict]:
    text = files("aliasgraph.resources").joinpath(SITES_RESOURCE).read_text(encoding="utf-8")
    data = json.loads(text)
    return data.get("sites", data)


@lru_cache(maxsize=1)
def load_all_sites() -> list[PlatformConfig]:
    """Load every site definition from the vendored maigret sites.json."""
    out: list[PlatformConfig] = []
    for name, v in _raw_sites().items():
        if v.get("disabled"):
            continue
        url = v.get("url")
        if not url or "{username}" not in url:
            continue
        url_main = v.get("urlMain") or ""
        # Substitute any non-{username} placeholders from the site dict.
        # Currently the only common one is {urlMain}.
        try:
            resolved_url = _OTHER_PLACEHOLDER_RE.sub(
                lambda m: _resolve_placeholder(m.group(1), v, url_main),
                url,
            )
        except _UnresolvedPlaceholder:
            continue
        if "{username}" not in resolved_url:
            continue
        out.append(
            PlatformConfig(
                name=name,
                profile_url=resolved_url,
                main_url=v.get("urlMain"),
                check_type=v.get("checkType", "status_code"),
                presence_strings=list(v.get("presenseStrs", [])),
                absence_strings=list(v.get("absenceStrs", [])),
                regex_check=v.get("regexCheck"),
                headers=dict(v.get("headers", {})),
            )
        )
    return out


def filter_sites(
    sites: list[PlatformConfig],
    names: list[str] | None = None,
    limit: int | None = None,
) -> list[PlatformConfig]:
    out = sites
    if names:
        wanted = {n.lower() for n in names}
        out = [s for s in out if s.name.lower() in wanted]
    if limit is not None and limit > 0:
        out = out[:limit]
    return out
