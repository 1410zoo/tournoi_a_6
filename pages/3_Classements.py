import streamlit as st
import pandas as pd
import db
import engine

st.set_page_config(page_title="Classements — Tournoi à 6", layout="wide")
st.title("🏆 Classements")

db.init_db()

groups = db.get_groups()
if not groups:
    st.info("Configure d'abord le tournoi (page Setup).")
    st.stop()

all_teams = {t["id"]: t["name"] for t in db.get_teams()}
all_matches = db.get_matches()

# Paramètre : nombre de qualifiés par poule (pour coloration)
with st.sidebar:
    st.header("Paramètres")
    qualifies_par_poule = st.number_input(
        "Équipes qualifiées par poule", min_value=1, max_value=8, value=2
    )

for group in groups:
    st.subheader(group["name"])

    team_ids = [t["id"] for t in db.get_teams(group["id"])]
    if not team_ids:
        st.write("_Aucune équipe dans cette poule._")
        continue

    group_matches = [m for m in all_matches if m["group_id"] == group["id"]]
    standings = engine.compute_standings(team_ids, group_matches)

    rows = []
    for s in standings:
        rows.append({
            "Rang": s["rank"],
            "Équipe": all_teams.get(s["team_id"], "?"),
            "J": s["played"],
            "V": s["wins"],
            "N": s["draws"],
            "D": s["losses"],
            "BP": s["gf"],
            "BC": s["ga"],
            "Diff": f"{s['gd']:+d}",
            "Pts": s["pts"],
        })

    df = pd.DataFrame(rows).set_index("Rang")

    # Coloration des qualifiés
    def highlight_qualifies(row):
        if row.name <= qualifies_par_poule:
            return ["background-color: #d4edda"] * len(row)
        return [""] * len(row)

    styled = df.style.apply(highlight_qualifies, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=False)

    total = len(group_matches)
    played = sum(1 for m in group_matches if m["played"])
    st.caption(f"{played}/{total} matchs joués dans cette poule")
    st.divider()
