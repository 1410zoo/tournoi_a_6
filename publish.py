"""
Génère un dashboard HTML statique et le pousse sur GitHub Pages via l'API GitHub.
"""
import base64
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime

import db
import engine


def _load_env() -> dict:
    env = {}
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


def generate_html() -> str:
    groups = db.get_groups()
    all_teams = {t["id"]: t["name"] for t in db.get_teams()}
    all_matches = db.get_matches()

    played = sum(1 for m in all_matches if m["played"])
    total = len(all_matches)
    upcoming_times = sorted(set(
        m["scheduled_time"] for m in all_matches
        if not m["played"] and m["scheduled_time"]
    ))
    next_slot = upcoming_times[0] if upcoming_times else "—"
    now = datetime.now().strftime("%H:%M")

    groups_html = ""
    for group in groups:
        team_ids = [t["id"] for t in db.get_teams(group["id"])]
        group_matches = [m for m in all_matches if m["group_id"] == group["id"]]
        standings = engine.compute_standings(team_ids, group_matches)

        rows_html = ""
        for s in standings:
            name = all_teams.get(s["team_id"], "?")
            gd_str = f"+{s['gd']}" if s["gd"] > 0 else str(s["gd"])
            cls = "leader" if s["rank"] == 1 else ""
            rows_html += (
                f'<div class="standing-row {cls}">'
                f'<span class="standing-rank">{s["rank"]}</span>'
                f'<span class="standing-name">{name}</span>'
                f'<span class="standing-pts">{s["pts"]}</span>'
                f'<span class="standing-gd">{gd_str}</span>'
                f'</div>'
            )

        # Derniers résultats (3 max)
        played_matches = sorted(
            [m for m in group_matches if m["played"]], key=lambda m: m["id"]
        )[-3:]
        results_html = ""
        for m in played_matches:
            t1 = all_teams.get(m["team1_id"], "?")
            t2 = all_teams.get(m["team2_id"], "?")
            results_html += (
                f'<div class="result-row">'
                f'<span class="rt">{t1}</span>'
                f'<span class="rs">{m["score1"]} – {m["score2"]}</span>'
                f'<span class="rt">{t2}</span>'
                f'</div>'
            )

        # Prochains matchs (4 max)
        upcoming = sorted(
            [m for m in group_matches if not m["played"]],
            key=lambda m: (m["scheduled_time"] or "99:99", m["id"]),
        )[:4]
        matches_html = ""
        if upcoming:
            for m in upcoming:
                t1 = all_teams.get(m["team1_id"], "?")
                t2 = all_teams.get(m["team2_id"], "?")
                tme = m.get("scheduled_time") or "—"
                ter = f"T{m['terrain_num']}" if m.get("terrain_num") else ""
                matches_html += (
                    f'<div class="match-row">'
                    f'<span class="match-time">{tme}</span>'
                    f'<span class="match-terrain">{ter}</span>'
                    f'<span class="match-teams">{t1} <span class="vs">vs</span> {t2}</span>'
                    f'</div>'
                )
        else:
            matches_html = '<div class="done-text">✅ Tous les matchs joués</div>'

        results_section = (
            f'<div class="section-label">Derniers résultats</div>{results_html}'
            if results_html else ""
        )

        groups_html += (
            f'<div class="group-card">'
            f'<div class="group-title">{group["name"]}</div>'
            f'<div class="section-label">Classement</div>'
            f'{rows_html}'
            f'{results_section}'
            f'<div class="section-label">Prochains matchs</div>'
            f'{matches_html}'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tournoi à 6 — FC Thierrens</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=Barlow:wght@400;600&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Barlow',sans-serif;background:#fff;color:#111;padding:12px}}
.header{{background:#CC2222;border-radius:8px;padding:16px 20px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.title{{font-family:'Barlow Condensed',sans-serif;font-weight:900;font-size:2rem;color:#fff;text-transform:uppercase;letter-spacing:2px}}
.subtitle{{font-family:'Barlow Condensed',sans-serif;color:rgba(255,255,255,.8);font-size:.95rem;letter-spacing:2px;text-transform:uppercase}}
.meta{{text-align:right;color:#fff}}
.meta-score{{font-family:'Barlow Condensed',sans-serif;font-size:1.6rem;font-weight:700}}
.meta-next{{font-size:.8rem;color:rgba(255,255,255,.75)}}
.updated{{text-align:right;font-size:.75rem;color:#999;margin-bottom:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}}
.group-card{{background:#f7f7f7;border:1px solid #e0e0e0;border-radius:8px;padding:14px}}
.group-title{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:1.2rem;color:#CC2222;text-transform:uppercase;letter-spacing:2px;border-bottom:2px solid #CC2222;padding-bottom:5px;margin-bottom:8px}}
.section-label{{font-family:'Barlow Condensed',sans-serif;font-size:.78rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:2px;margin:10px 0 4px}}
.standing-row{{display:flex;align-items:center;padding:4px 5px;border-radius:4px;margin-bottom:2px;font-size:.85rem}}
.standing-row.leader{{background:#CC2222;font-weight:700;color:#fff}}
.standing-rank{{width:18px;color:#999;font-size:.75rem}}
.leader .standing-rank{{color:rgba(255,255,255,.65)}}
.standing-name{{flex:1;padding:0 5px}}
.standing-pts{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.95rem;min-width:28px;text-align:right;color:#111}}
.leader .standing-pts{{color:#fff}}
.standing-gd{{font-size:.75rem;color:#777;min-width:32px;text-align:right;padding-left:5px}}
.leader .standing-gd{{color:rgba(255,255,255,.7)}}
.result-row{{display:flex;align-items:center;gap:4px;font-size:.8rem;padding:2px 4px;margin-bottom:2px;color:#555}}
.rt{{flex:1}}.rt:last-child{{text-align:right}}
.rs{{font-family:'Barlow Condensed',sans-serif;font-weight:700;font-size:.95rem;color:#111;text-align:center;min-width:40px}}
.match-row{{display:flex;align-items:center;gap:5px;padding:3px 5px;border-radius:4px;margin-bottom:2px;background:#efefef;font-size:.8rem;color:#333}}
.match-time{{font-family:'Barlow Condensed',sans-serif;font-weight:700;color:#CC2222;min-width:36px;font-size:.85rem}}
.match-terrain{{background:#ddd;border-radius:3px;padding:1px 4px;font-size:.7rem;color:#555;min-width:20px;text-align:center}}
.match-teams{{flex:1}}.vs{{color:#aaa}}
.done-text{{color:#2e7d32;font-size:.8rem;padding:3px 5px}}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="title">Tournoi à 6</div>
    <div class="subtitle">FC Thierrens &nbsp;·&nbsp; 11 Juillet 2026</div>
  </div>
  <div class="meta">
    <div class="meta-score">{played} <span style="font-size:1rem;opacity:.7">/ {total} matchs</span></div>
    <div class="meta-next">Prochain créneau : <b>{next_slot}</b></div>
  </div>
</div>
<div class="updated">Mis à jour à {now}</div>
<div class="grid">{groups_html}</div>
</body>
</html>"""


def push_to_github(html: str) -> str:
    """Pousse index.html sur GitHub Pages. Retourne l'URL publique."""
    env = _load_env()
    token = env.get("GITHUB_TOKEN", "")
    user = env.get("GITHUB_USER", "")
    repo = env.get("GITHUB_REPO", "")

    if not all([token, user, repo]):
        raise ValueError("GITHUB_TOKEN, GITHUB_USER ou GITHUB_REPO manquant dans .env")

    repo_encoded = urllib.parse.quote(repo, safe="")
    api_url = f"https://api.github.com/repos/{user}/{repo_encoded}/contents/index.html"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    # Récupérer le SHA du fichier existant (nécessaire pour le mettre à jour)
    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            sha = json.loads(resp.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise

    content_b64 = base64.b64encode(html.encode("utf-8")).decode()
    body: dict = {
        "message": f"Résultats {datetime.now().strftime('%H:%M')}",
        "content": content_b64,
        "branch": "main",
    }
    if sha:
        body["sha"] = sha

    req = urllib.request.Request(
        api_url,
        data=json.dumps(body).encode(),
        headers=headers,
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {e.code} — URL: {api_url}\n{msg}") from e

    return f"https://{user}.github.io/{repo}/"
