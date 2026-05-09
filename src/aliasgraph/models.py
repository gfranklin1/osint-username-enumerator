from __future__ import annotations

from pydantic import BaseModel, HttpUrl


class PlatformConfig(BaseModel):
    name: str
    profile_url: str  # template containing "{username}"
    rate_limit_seconds: float = 1.0
    not_found_status_codes: list[int] = [404]
    not_found_body_substrings: list[str] = []
    requires_javascript: bool = False


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


class ScanResult(BaseModel):
    seed: str
    generated_usernames: list[str]
    profiles: list[Profile]
