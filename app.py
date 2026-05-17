import streamlit as st
import db

db.init_db()

st.set_page_config(
    page_title="Tournoi à 6 — Thierrens",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ Tournoi à 6 — Thierrens")
st.write("Utilise le menu à gauche pour naviguer entre les étapes du tournoi.")

groups = db.get_groups()
teams = db.get_teams()
matches = db.get_matches()
played = sum(1 for m in matches if m["played"])

col1, col2, col3 = st.columns(3)
col1.metric("Poules", len(groups))
col2.metric("Équipes", len(teams))
col3.metric("Matchs joués", f"{played} / {len(matches)}")
