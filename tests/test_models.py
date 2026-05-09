from aliasgraph.models import Profile, ScanResult


def test_profile_minimal():
    p = Profile(site="github", url="https://github.com/jhauptman", username="jhauptman")
    assert p.bio is None
    assert p.links == []


def test_scan_result_roundtrip():
    p = Profile(site="github", url="https://github.com/jhauptman", username="jhauptman")
    r = ScanResult(seed="jhauptman", generated_usernames=["jhauptman"], profiles=[p])
    payload = r.model_dump_json()
    restored = ScanResult.model_validate_json(payload)
    assert restored.profiles[0].username == "jhauptman"
    assert restored.seed == "jhauptman"
