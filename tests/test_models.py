from aliasgraph.models import Profile, ScanResult


def test_profile_minimal():
    p = Profile(site="github", url="https://github.com/testuser1", username="testuser1")
    assert p.bio is None
    assert p.links == []


def test_scan_result_roundtrip():
    p = Profile(site="github", url="https://github.com/testuser1", username="testuser1")
    r = ScanResult(seed="testuser1", generated_usernames=["testuser1"], profiles=[p])
    payload = r.model_dump_json()
    restored = ScanResult.model_validate_json(payload)
    assert restored.profiles[0].username == "testuser1"
    assert restored.seed == "testuser1"
