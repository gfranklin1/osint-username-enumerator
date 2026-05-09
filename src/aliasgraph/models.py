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


class ExtractedHandle(BaseModel):
    site: str  # canonical platform name (must match a PlatformConfig.name when possible)
    handle: str
    source_url: str  # the raw link this handle was parsed from


class Profile(BaseModel):
    site: str
    url: HttpUrl
    username: str
    display_name: str | None = None
    bio: str | None = None
    location: str | None = None
    links: list[str] = []  # normalized outbound URLs
    extracted_handles: list[ExtractedHandle] = []
    avatar_url: str | None = None
    avatar_hash: str | None = None
    created_at: str | None = None
    followers: int | None = None
    following: int | None = None
    raw_html_hash: str | None = None
    quality: float = 0.0  # post-scrape signal richness, [0, 1]

    def key(self) -> str:
        return f"{self.site}:{self.username}".lower()


class SiteError(BaseModel):
    site: str
    username: str
    reason: str  # e.g. "timeout", "dns", "http_5xx", "connection", "scrape_*"


class MatchFeatures(BaseModel):
    username_similarity: float
    display_name_similarity: float
    bio_similarity: float
    link_overlap_score: float
    location_similarity: float
    avatar_similarity: float = 0.0
    crosslink_strength: str  # "mutual" | "one_way" | "none"


class AssertedAccount(BaseModel):
    """A handle asserted by a discovered profile but not directly scanned/verified."""
    site: str
    handle: str
    url: str
    asserted_by: list[str]  # "site:username" of profiles that link to this one


class Cluster(BaseModel):
    cluster_id: int
    confidence: float
    members: list[str]  # "site:username"
    asserted: list[AssertedAccount] = []
    evidence: list[str]


class ScanResult(BaseModel):
    seed: str
    generated_usernames: list[str]
    profiles: list[Profile]
    errored_sites: list[SiteError] = []
    clusters: list[Cluster] = []
    unverified_profiles: list[Profile] = []  # found but too low-signal to cluster
