import streamlit as st
import db

st.set_page_config(page_title="Calendrier — Tournoi à 6", layout="wide")
st.title("📅 Calendrier & Scores")

db.init_db()


def _render_matches(matches: list[dict], all_teams: dict):
    for match in matches:
        t1 = all_teams.get(match["team1_id"], "?")
        t2 = all_teams.get(match["team2_id"], "?")
        time_str = match.get("scheduled_time") or "—"
        terrain_str = f"T{match['terrain_num']}" if match.get("terrain_num") else ""
        key1, key2 = f"s1_{match['id']}", f"s2_{match['id']}"
        editing = st.session_state.get(f"editing_{match['id']}", False)

        c_time, c_ter, c_t1, c_s1, c_dash, c_s2, c_t2, c_btn = st.columns(
            [1, 0.7, 3, 1, 0.4, 1, 3, 1]
        )
        c_time.caption(time_str)
        c_ter.caption(terrain_str)

        if match["played"] and not editing:
            # Affichage du score enregistré
            c_t1.write(f"**{t1}**")
            c_s1.write(f"**{match['score1']}**")
            c_dash.write("—")
            c_s2.write(f"**{match['score2']}**")
            c_t2.write(f"**{t2}**")
            if c_btn.button("✏️", key=f"edit_btn_{match['id']}"):
                st.session_state[f"editing_{match['id']}"] = True
                st.rerun()

        elif editing:
            # Modification d'un score existant — cases pré-remplies + bouton 💾
            c_t1.write(t1)
            v1 = c_s1.number_input(
                t1, min_value=0, max_value=99,
                value=match["score1"], label_visibility="collapsed", key=key1,
            )
            c_dash.write("—")
            v2 = c_s2.number_input(
                t2, min_value=0, max_value=99,
                value=match["score2"], label_visibility="collapsed", key=key2,
            )
            c_t2.write(t2)
            if c_btn.button("💾", key=f"save_btn_{match['id']}"):
                db.save_score(match["id"], int(v1), int(v2))
                st.session_state.pop(f"editing_{match['id']}", None)
                st.rerun()

        else:
            # Nouveau score — cases vides, auto-save dès que les deux sont remplies
            c_t1.write(t1)
            v1 = c_s1.number_input(
                t1, min_value=0, max_value=99,
                value=None, label_visibility="collapsed", key=key1,
            )
            c_dash.write("—")
            v2 = c_s2.number_input(
                t2, min_value=0, max_value=99,
                value=None, label_visibility="collapsed", key=key2,
            )
            c_t2.write(t2)

            if v1 is not None and v2 is not None:
                db.save_score(match["id"], int(v1), int(v2))
                st.session_state.pop(key1, None)
                st.session_state.pop(key2, None)
                st.rerun()


# ── Données ───────────────────────────────────────────────────────────────────

groups = db.get_groups()
if not groups:
    st.info("Configure d'abord le tournoi (page Setup).")
    st.stop()

all_teams = {t["id"]: t["name"] for t in db.get_teams()}
all_matches = db.get_matches()

if not all_matches:
    st.info("Aucun match généré. Va sur la page Setup pour générer le calendrier.")
    st.stop()

played_count = sum(1 for m in all_matches if m["played"])
st.caption(f"{played_count} / {len(all_matches)} matchs joués")

# ── Vue ───────────────────────────────────────────────────────────────────────

view = st.radio("Afficher par", ["Calendrier", "Terrain", "Groupe"], horizontal=True)

if view == "Calendrier":
    # Vue chronologique : tous les créneaux dans l'ordre, 4 matchs par créneau
    from itertools import groupby
    slots = sorted(set(m["scheduled_time"] or "—" for m in all_matches))
    for slot_time in slots:
        slot_matches = sorted(
            [m for m in all_matches if (m["scheduled_time"] or "—") == slot_time],
            key=lambda m: m["terrain_num"] or 0,
        )
        played_in_slot = sum(1 for m in slot_matches if m["played"])
        label = f"🕐 {slot_time}"
        if played_in_slot == len(slot_matches):
            label += " ✅"
        st.subheader(label)
        _render_matches(slot_matches, all_teams)
        st.divider()

elif view == "Terrain":
    terrains = sorted(set(m["terrain_num"] for m in all_matches if m["terrain_num"]))
    if not terrains:
        st.info("Les terrains ne sont pas encore assignés. Regénère le calendrier depuis Setup.")
    for terrain in terrains:
        terrain_matches = sorted(
            [m for m in all_matches if m["terrain_num"] == terrain],
            key=lambda m: (m["scheduled_time"] or "", m["id"]),
        )
        st.subheader(f"🟩 Terrain {terrain}")
        _render_matches(terrain_matches, all_teams)
        st.divider()

else:
    for group in groups:
        matches = sorted(
            [m for m in all_matches if m["group_id"] == group["id"]],
            key=lambda m: (m["round_num"] or 0, m["id"]),
        )
        if not matches:
            continue
        st.subheader(group["name"])
        _render_matches(matches, all_teams)
        st.divider()
