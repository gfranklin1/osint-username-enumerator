"""HTML report safety — see ITER3 §2.2."""
from __future__ import annotations

from aliasgraph.models import AssertedAccount, Cluster, Profile, ScanResult
from aliasgraph.reporting.html_report import _safe_url, render_html


def _profile(**kw) -> Profile:
    base = dict(site="GitHub", url="https://github.com/testuser1", username="testuser1")
    base.update(kw)
    return Profile(**base)


def test_safe_url_blanks_javascript_scheme():
    assert _safe_url("javascript:alert(1)") == ""
    assert _safe_url("JAVASCRIPT:alert(1)") == ""
    assert _safe_url("data:text/html,<script>") == ""
    assert _safe_url("vbscript:msgbox(1)") == ""


def test_safe_url_keeps_http_and_https():
    assert _safe_url("https://example.com") == "https://example.com"
    assert _safe_url("http://example.com/x?y=1") == "http://example.com/x?y=1"


def test_safe_url_handles_none_and_empty():
    assert _safe_url(None) == ""
    assert _safe_url("") == ""
    assert _safe_url("   ") == ""


def test_render_html_strips_javascript_avatar():
    p = _profile(avatar_url="javascript:alert(1)")
    result = ScanResult(seed="testuser1", generated_usernames=["testuser1"], profiles=[p])
    html = render_html(result)
    assert "javascript:" not in html.lower()
    assert "<script" not in html.lower()


def test_render_html_strips_javascript_asserted_url():
    p = _profile()
    cluster = Cluster(
        cluster_id=1,
        confidence=0.99,
        members=["GitHub:testuser1"],
        asserted=[
            AssertedAccount(
                site="Twitter",
                handle="evil",
                url="javascript:alert('asserted')",
                asserted_by=["GitHub:testuser1"],
            )
        ],
        evidence=[],
    )
    result = ScanResult(
        seed="testuser1",
        generated_usernames=["testuser1"],
        profiles=[p],
        clusters=[cluster],
    )
    html = render_html(result)
    assert "javascript:" not in html.lower()
