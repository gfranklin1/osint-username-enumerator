from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files

from aliasgraph.models import PlatformConfig

SITES_RESOURCE = "sites.json"


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
        out.append(
            PlatformConfig(
                name=name,
                profile_url=url,
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
