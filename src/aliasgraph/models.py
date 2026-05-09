from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class PlatformConfig(BaseModel):
    name: str
    profile_url: str  # template containing "{username}"
    main_url: str | None = None
    check_type: str = "status_code"  # status_code | message | response_url
    presence_strings: list[str] = []
    absence_strings: list[str] = []
    regex_check: str | None = None
    headers: dict[str, str] = {}
    rate_limit_seconds: float = 0.0


class Profile(BaseModel):
    site: str
    url: HttpUrl
    username: str
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    links: list[str] = []
    avatar_url: str | None = None
    avatar_hash: str | None = None
    created_at: str | None = None
    followers: int | None = None
    following: int | None = None
    raw_html_hash: str | None = None


class SiteError(BaseModel):
    site: str
    username: str
    reason: str  # e.g. "timeout", "dns", "http_5xx", "connection"


class ScanResult(BaseModel):
    seed: str
    generated_usernames: list[str]
    profiles: list[Profile]
    errored_sites: list[SiteError] = []
