from __future__ import annotations

from html import escape
from pathlib import Path

from aliasgraph.models import Profile, ScanResult

CSS = """
:root {
  --bg: #0e1116;
  --panel: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --muted: #8b949e;
  --accent: #2ea043;
  --accent-soft: #238636;
  --link: #58a6ff;
  --warn: #d29922;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 24px;
  background: var(--bg); color: var(--text);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
header {
  display: flex; align-items: baseline; gap: 24px;
  border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 24px;
}
header h1 { margin: 0; font-size: 20px; }
header .seed { color: var(--accent); font-weight: 600; }
.stats { display: flex; gap: 18px; color: var(--muted); }
.stats b { color: var(--text); }
.cluster, .ungrouped, .errors {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  margin-bottom: 16px; overflow: hidden;
}
.cluster-header {
  padding: 12px 16px; border-bottom: 1px solid var(--border);
  display: flex; justify-content: space-between; align-items: center;
  background: rgba(46, 160, 67, 0.08);
}
.cluster-header h2 { margin: 0; font-size: 15px; color: var(--accent); }
.confidence { font-weight: 700; color: var(--accent); }
.cluster-body { padding: 12px 16px; }
table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
th, td {
  padding: 6px 8px; text-align: left; vertical-align: top;
  border-bottom: 1px solid var(--border);
}
th { color: var(--muted); font-weight: 500; }
td.site { color: var(--link); white-space: nowrap; }
td.user { font-weight: 600; }
td.bio { color: var(--muted); }
td.url a { color: var(--link); text-decoration: none; word-break: break-all; }
td.url a:hover { text-decoration: underline; }
tr.asserted { background: rgba(210, 153, 34, 0.06); }
tr.asserted td.user { color: var(--warn); }
.tag {
  display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 10px;
  background: rgba(46, 160, 67, 0.15); color: var(--accent); margin-right: 6px;
}
.tag.warn { background: rgba(210, 153, 34, 0.15); color: var(--warn); }
.evidence {
  margin-top: 12px; padding: 10px 12px; border-left: 3px solid var(--accent-soft);
  background: rgba(46, 160, 67, 0.05); border-radius: 4px;
}
.evidence h3 { margin: 0 0 6px; font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
.evidence ul { margin: 0; padding-left: 18px; }
.evidence li { margin: 2px 0; }
.errors { background: rgba(210, 153, 34, 0.06); border-color: rgba(210, 153, 34, 0.3); padding: 12px 16px; color: var(--muted); font-size: 13px; }
.muted { color: var(--muted); }
.thumb {
  width: 28px; height: 28px; border-radius: 50%; border: 1px solid var(--border);
  object-fit: cover; background: #000;
}
"""


def render_html(result: ScanResult) -> str:
    profile_by_key = {p.key(): p for p in result.profiles}
    clustered_keys: set[str] = set()
    for c in result.clusters:
        clustered_keys.update(m.lower() for m in c.members)
    ungrouped = [p for p in result.profiles if p.key() not in clustered_keys]

    parts: list[str] = []
    parts.append("<!doctype html><html><head><meta charset='utf-8'>")
    parts.append(f"<title>AliasGraph — {escape(result.seed)}</title>")
    parts.append(f"<style>{CSS}</style></head><body>")
    parts.append(
        "<header>"
        f"<h1>AliasGraph · <span class='seed'>{escape(result.seed)}</span></h1>"
        "<div class='stats'>"
        f"<span>Variants <b>{len(result.generated_usernames)}</b></span>"
        f"<span>Profiles <b>{len(result.profiles)}</b></span>"
        f"<span>Clusters <b>{len(result.clusters)}</b></span>"
        f"<span>Errors <b>{len(result.errored_sites)}</b></span>"
        "</div></header>"
    )

    for cluster in result.clusters:
        members = [
            profile_by_key[m.lower()] for m in cluster.members if m.lower() in profile_by_key
        ]
        parts.append("<section class='cluster'>")
        parts.append(
            f"<div class='cluster-header'>"
            f"<h2>Cluster {cluster.cluster_id} · {len(members)} profile{'s' if len(members) != 1 else ''}</h2>"
            f"<span class='confidence'>{cluster.confidence:.0%} confidence</span>"
            f"</div>"
        )
        parts.append("<div class='cluster-body'>")
        parts.append(_profile_table(members, cluster.asserted))
        if cluster.evidence:
            parts.append("<div class='evidence'><h3>Evidence</h3><ul>")
            for line in cluster.evidence:
                parts.append(f"<li>{escape(line)}</li>")
            parts.append("</ul></div>")
        parts.append("</div></section>")

    if ungrouped:
        parts.append("<section class='ungrouped'>")
        parts.append(
            "<div class='cluster-header'>"
            f"<h2 style='color:var(--muted)'>Ungrouped profiles · {len(ungrouped)}</h2>"
            "</div><div class='cluster-body'>"
        )
        parts.append(_profile_table(ungrouped))
        parts.append("</div></section>")

    if result.unverified_profiles:
        parts.append("<section class='ungrouped'>")
        parts.append(
            "<div class='cluster-header'>"
            f"<h2 style='color:var(--warn)'>Weak hits · {len(result.unverified_profiles)} (skipped from clustering)</h2>"
            "</div><div class='cluster-body'>"
        )
        parts.append(
            "<p class='muted' style='margin-top:0;font-size:12px'>"
            "Sites returned 200 OK but the page had no real user signal "
            "(error pages, marketing copy, garbled text). Lower "
            "<code>--quality-threshold</code> to include them.</p>"
        )
        parts.append(_profile_table(result.unverified_profiles))
        parts.append("</div></section>")

    if result.errored_sites:
        from collections import Counter
        reasons = Counter(e.reason for e in result.errored_sites)
        sites_down = sorted({e.site for e in result.errored_sites})
        reason_summary = ", ".join(f"{r}={n}" for r, n in reasons.most_common())
        parts.append(
            "<section class='errors'>"
            f"<b>Errors:</b> {len(sites_down)} sites · {escape(reason_summary)}<br>"
            f"<span class='muted'>{escape(', '.join(sites_down))}</span>"
            "</section>"
        )

    parts.append("</body></html>")
    return "".join(parts)


def _profile_table(profiles: list[Profile], asserted=None) -> str:
    rows = ["<table>"]
    rows.append(
        "<tr><th></th><th>Source</th><th>Site</th><th>Username</th>"
        "<th>Display name</th><th>Bio</th><th>URL</th></tr>"
    )
    for p in profiles:
        avatar = (
            f"<img class='thumb' src='{escape(p.avatar_url)}' alt=''>"
            if p.avatar_url
            else ""
        )
        rows.append(
            "<tr>"
            f"<td>{avatar}</td>"
            "<td><span class='tag'>verified</span></td>"
            f"<td class='site'>{escape(p.site)}</td>"
            f"<td class='user'>{escape(p.username)}</td>"
            f"<td>{escape(p.display_name or '')}</td>"
            f"<td class='bio'>{escape((p.bio or '')[:160])}</td>"
            f"<td class='url'><a href='{escape(str(p.url))}' target='_blank' rel='noopener'>{escape(str(p.url))}</a></td>"
            "</tr>"
        )
    if asserted:
        for a in asserted:
            via = ", ".join(a.asserted_by)
            rows.append(
                "<tr class='asserted'>"
                "<td></td>"
                f"<td><span class='tag warn'>asserted</span><span class='muted' style='font-size:11px'>via {escape(via)}</span></td>"
                f"<td class='site'>{escape(a.site)}</td>"
                f"<td class='user'>{escape(a.handle)}</td>"
                "<td class='muted'><i>not scanned</i></td>"
                "<td></td>"
                f"<td class='url'><a href='{escape(a.url)}' target='_blank' rel='noopener'>{escape(a.url)}</a></td>"
                "</tr>"
            )
    rows.append("</table>")
    return "".join(rows)


def write_html(result: ScanResult, path: Path) -> None:
    path.write_text(render_html(result), encoding="utf-8")
