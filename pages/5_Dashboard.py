import streamlit as st
import db
import engine
import publish

st.set_page_config(page_title="Tournoi à 6 — Thierrens", layout="wide")

# ── CSS inspiré de l'affiche : rouge vif, blanc, noir, typo bold ──────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=Barlow:wght@400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Barlow', sans-serif;
}

/* Fond général : géré par config.toml */

/* Cacher la toolbar Streamlit */
#MainMenu, footer, header,
div[data-testid="stToolbar"] { visibility: hidden; }

.block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

/* ── Header principal ── */
.tournament-header {
    background: #CC2222;
    border-radius: 8px;
    padding: 18px 28px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.tournament-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 2.8rem;
    color: #ffffff;
    letter-spacing: 2px;
    text-transform: uppercase;
    line-height: 1;
}
.tournament-subtitle {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 400;
    font-size: 1.1rem;
    color: rgba(255,255,255,0.8);
    letter-spacing: 3px;
    text-transform: uppercase;
}
.tournament-meta {
    text-align: right;
    color: rgba(255,255,255,0.85);
    font-size: 0.95rem;
}
.big-six {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 900;
    font-size: 5rem;
    color: #ffffff;
    line-height: 1;
    margin-left: 16px;
}

/* ── Métriques ── */
.metric-bar {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
}
.metric-box {
    background: #f7f7f7;
    border-left: 4px solid #CC2222;
    border-radius: 6px;
    padding: 10px 20px;
    flex: 1;
    text-align: center;
}
.metric-value {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: #111111;
}
.metric-label {
    font-size: 0.75rem;
    color: #666666;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Colonnes groupe ── */
.group-card {
    background: #f7f7f7;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    height: 100%;
}
.group-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 1.3rem;
    color: #CC2222;
    text-transform: uppercase;
    letter-spacing: 2px;
    border-bottom: 2px solid #CC2222;
    padding-bottom: 6px;
    margin-bottom: 10px;
}
.standing-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 6px;
    border-radius: 4px;
    margin-bottom: 2px;
    font-size: 0.88rem;
}
.standing-row.leader {
    background: #CC2222;
    font-weight: 700;
}
.standing-row.normal { color: #222222; }
.standing-rank { width: 20px; color: #888888; font-size: 0.78rem; }
.standing-row.leader .standing-rank { color: rgba(255,255,255,0.7); }
.standing-name { flex: 1; padding: 0 6px; }
.standing-pts {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    font-size: 1rem;
    color: #111111;
    min-width: 32px;
    text-align: right;
}
.standing-row.leader .standing-pts { color: #ffffff; }
.standing-gd {
    font-size: 0.78rem;
    color: #666666;
    min-width: 36px;
    text-align: right;
    padding-left: 6px;
}
.standing-row.leader .standing-gd { color: rgba(255,255,255,0.7); }

/* ── Section prochains matchs ── */
.next-title {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 0.85rem;
    font-weight: 700;
    color: #666666;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-top: 12px;
    margin-bottom: 6px;
}
.match-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 6px;
    border-radius: 4px;
    margin-bottom: 3px;
    background: #f0f0f0;
    font-size: 0.82rem;
    color: #333333;
}
.match-time {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 700;
    color: #CC2222;
    min-width: 38px;
    font-size: 0.88rem;
}
.match-terrain {
    background: #dddddd;
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 0.72rem;
    color: #555555;
    min-width: 22px;
    text-align: center;
}
.match-teams { flex: 1; }
.done-text { color: #2e7d32; font-size: 0.82rem; padding: 4px 6px; }
</style>
""", unsafe_allow_html=True)

# ── Données ───────────────────────────────────────────────────────────────────
db.init_db()
groups      = db.get_groups()
all_teams   = {t["id"]: t["name"] for t in db.get_teams()}
all_matches = db.get_matches()

if not groups:
    st.info("Le tournoi n'est pas encore configuré.")
    st.stop()

played = sum(1 for m in all_matches if m["played"])
total  = len(all_matches)
upcoming_times = sorted(set(
    m["scheduled_time"] for m in all_matches
    if not m["played"] and m["scheduled_time"]
))

# ── Header ────────────────────────────────────────────────────────────────────
next_slot = upcoming_times[0] if upcoming_times else "—"
st.markdown(f"""
<div class="tournament-header">
    <div>
        <div class="tournament-title">Tournoi à <span class="big-six">6</span></div>
        <div class="tournament-subtitle">FC Thierrens &nbsp;·&nbsp; 11 Juillet 2026</div>
    </div>
    <div class="tournament-meta">
        <div style="font-size:1.8rem;font-weight:700;color:#fff">{played} <span style="font-size:1rem;color:rgba(255,255,255,0.6)">/ {total} matchs</span></div>
        <div style="font-size:0.85rem;color:rgba(255,255,255,0.7)">Prochain : <b>{next_slot}</b></div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Bouton de publication ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Publication")
    env = publish._load_env()
    public_url = f"https://{env.get('GITHUB_USER','')}.github.io/{env.get('GITHUB_REPO','')}/"

    if st.button("🌐 Publier les résultats", type="primary", use_container_width=True):
        try:
            html = publish.generate_html()
            publish.push_to_github(html)
            st.success("Publié !")
        except Exception as e:
            st.error(f"Erreur : {e}")

    # QR code vers la page publique
    try:
        import qrcode, io
        qr = qrcode.make(public_url)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        st.image(buf.getvalue(), caption=public_url, use_container_width=True)
    except Exception:
        st.caption(public_url)

# ── Colonnes par groupe ───────────────────────────────────────────────────────
cols = st.columns(len(groups))

for col, group in zip(cols, groups):
    with col:
        team_ids      = [t["id"] for t in db.get_teams(group["id"])]
        group_matches = [m for m in all_matches if m["group_id"] == group["id"]]
        standings     = engine.compute_standings(team_ids, group_matches)

        # Classement
        rows_html = ""
        for s in standings:
            name   = all_teams.get(s["team_id"], "?")
            gd_str = f"+{s['gd']}" if s["gd"] > 0 else str(s["gd"])
            cls    = "leader" if s["rank"] == 1 else "normal"
            rows_html += f"""
            <div class="standing-row {cls}">
                <span class="standing-rank">{s['rank']}</span>
                <span class="standing-name">{name}</span>
                <span class="standing-pts">{s['pts']}</span>
                <span class="standing-gd">{gd_str}</span>
            </div>"""

        # Prochains matchs
        upcoming = sorted(
            [m for m in group_matches if not m["played"]],
            key=lambda m: (m["scheduled_time"] or "99:99", m["id"]),
        )[:4]

        matches_html = ""
        if upcoming:
            for m in upcoming:
                t1  = all_teams.get(m["team1_id"], "?")
                t2  = all_teams.get(m["team2_id"], "?")
                tme = m.get("scheduled_time") or "—"
                ter = f"T{m['terrain_num']}" if m.get("terrain_num") else ""
                matches_html += f"""
                <div class="match-row">
                    <span class="match-time">{tme}</span>
                    <span class="match-terrain">{ter}</span>
                    <span class="match-teams">{t1} <span style="color:#666">vs</span> {t2}</span>
                </div>"""
        else:
            matches_html = '<div class="done-text">✅ Tous les matchs joués</div>'

        st.markdown(
            f'<div class="group-card">'
            f'<div class="group-title">{group["name"]}</div>'
            f'<div style="height:280px;overflow-y:auto">{rows_html}</div>'
            f'<div class="next-title">Prochains matchs</div>'
            f'{matches_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
