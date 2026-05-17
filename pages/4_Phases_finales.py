import streamlit as st
import db
import engine

st.set_page_config(page_title="Phases finales — Tournoi à 6", layout="wide")
st.title("🥅 Phases finales & Classement")

db.init_db()

all_teams = {t["id"]: t["name"] for t in db.get_teams()}
groups = db.get_groups()
all_group_matches = db.get_matches()

ROUND_LABELS = {
    1: "Finale",
    2: "Demi-finales",
    3: "Quarts de finale",
    4: "Huitièmes de finale",
    5: "Seizièmes de finale",
}


def team_name(tid):
    if tid is None:
        return "BYE"
    return all_teams.get(tid, "?")


def render_bracket_matches(bracket_matches: list[dict], bracket_label: str):
    """Affiche et permet la saisie des scores pour un bracket donné."""
    if not bracket_matches:
        return

    rounds = sorted(set(m["round"] for m in bracket_matches), reverse=True)
    st.subheader(bracket_label)

    for rnd in rounds:
        rnd_matches = sorted(
            [m for m in bracket_matches if m["round"] == rnd],
            key=lambda m: m["position"],
        )
        is_final_round = rnd == 1
        for match in rnd_matches:
            t1, t2 = team_name(match["team1_id"]), team_name(match["team2_id"])

            # Libellé du match
            if is_final_round:
                match_label = "🏆 Finale" if match["position"] == 1 else "🥉 Match 3e place"
            else:
                match_label = ROUND_LABELS.get(rnd, f"Tour {rnd}")

            st.markdown(f"**{match_label}**")

            if match["played"]:
                winner = engine.get_winner(match)
                col1, col2 = st.columns([4, 2])
                col1.write(f"**{t1}** {match['score1']} — {match['score2']} **{t2}**")
                col2.success(f"✅ {team_name(winner)}")
                if col2.button("✏️ Modifier", key=f"ko_edit_{match['id']}"):
                    st.session_state[f"ko_editing_{match['id']}"] = True
            else:
                col1, col2 = st.columns([4, 2])
                col1.write(f"**{t1}** vs **{t2}**")
                if match["team1_id"] and match["team2_id"]:
                    if col2.button("Saisir score", key=f"ko_score_{match['id']}"):
                        st.session_state[f"ko_editing_{match['id']}"] = True

            if st.session_state.get(f"ko_editing_{match['id']}"):
                with st.form(key=f"ko_form_{match['id']}"):
                    fc1, fc2, fc3 = st.columns([2, 2, 1])
                    s1 = fc1.number_input(t1, min_value=0, max_value=99,
                                          value=match["score1"] or 0)
                    s2 = fc2.number_input(t2, min_value=0, max_value=99,
                                          value=match["score2"] or 0)
                    st.caption("⚠️ Pas d'égalité en phases finales.")
                    if fc3.form_submit_button("💾"):
                        if int(s1) == int(s2):
                            st.error("Score nul non autorisé.")
                        else:
                            db.save_knockout_score(match["id"], int(s1), int(s2))
                            st.session_state.pop(f"ko_editing_{match['id']}", None)
                            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# GÉNÉRATION DES BRACKETS (si aucun n'existe encore)
# ═══════════════════════════════════════════════════════════════════

existing_bracket_ids = db.get_knockout_bracket_ids()

if not existing_bracket_ids:
    st.header("Générer les phases finales")

    unplayed = [m for m in all_group_matches if not m["played"]]
    if unplayed:
        st.warning(f"{len(unplayed)} match(s) de groupe non joué(s).")

    with st.sidebar:
        st.header("Paramètres")
        n_qualifiers = st.number_input(
            "Qualifiés par groupe (bracket principal)", min_value=1, max_value=8, value=2
        )

    if st.button("🚀 Générer tous les brackets", type="primary"):
        # Calculer les classements de chaque groupe
        standings_by_group: dict[int, list[dict]] = {}
        for group in groups:
            tids = [t["id"] for t in db.get_teams(group["id"])]
            gmatches = [m for m in all_group_matches if m["group_id"] == group["id"]]
            standings_by_group[group["id"]] = engine.compute_standings(tids, gmatches)

        n_groups = len(groups)

        # ── Bracket principal ──────────────────────────────────
        qualified = []
        for standings in standings_by_group.values():
            qualified.extend(s["team_id"] for s in standings[:n_qualifiers])

        if len(qualified) >= 2:
            for m in engine.generate_bracket(qualified, bracket_id=0):
                db.insert_knockout_match(m["round"], m["position"],
                                         m["team1_id"], m["team2_id"],
                                         bracket_id=0)

        # ── Brackets de consolation ────────────────────────────
        # Pour chaque rang non-qualifié (n_qualifiers+1, n_qualifiers+2, …)
        max_rank = max(
            len(s) for s in standings_by_group.values()
        ) if standings_by_group else 0

        for rank in range(n_qualifiers + 1, max_rank + 1):
            teams_at_rank = []
            for standings in standings_by_group.values():
                matches_at_rank = [s for s in standings if s["rank"] == rank]
                if matches_at_rank:
                    teams_at_rank.append(matches_at_rank[0]["team_id"])

            if len(teams_at_rank) >= 2:
                bid = engine.get_consolation_bracket_id(rank)
                for m in engine.generate_bracket(teams_at_rank, bracket_id=bid):
                    db.insert_knockout_match(m["round"], m["position"],
                                             m["team1_id"], m["team2_id"],
                                             bracket_id=bid)

        st.success("Brackets générés !")
        st.rerun()

    st.stop()


# ═══════════════════════════════════════════════════════════════════
# AFFICHAGE ET SAISIE DES BRACKETS
# ═══════════════════════════════════════════════════════════════════

# Récupérer le n_qualifiers depuis la sidebar (pour calcul des positions)
with st.sidebar:
    st.header("Paramètres")
    n_qualifiers_display = st.number_input(
        "Qualifiés par groupe (pour calcul positions)", min_value=1, max_value=8, value=2
    )

n_groups = len(groups)
all_ko_matches = db.get_knockout_matches()

# Trier les brackets : 0 en premier, puis les consolations par ordre croissant
for bid in sorted(existing_bracket_ids):
    bracket_matches = [m for m in all_ko_matches if m["bracket_id"] == bid]

    if bid == 0:
        label = "🏆 Bracket principal"
    else:
        start, end = engine.consolation_position_range(bid, n_qualifiers_display, n_groups)
        label = f"📋 Consolation — Places {start}–{end} (groupes : {bid}e de groupe)"

    render_bracket_matches(bracket_matches, label)

    # Avancement automatique au tour suivant pour ce bracket
    next_round = engine.advance_knockout(all_ko_matches, bracket_id=bid)
    if next_round:
        st.info(f"Tour suivant disponible pour **{label}**.")
        if st.button(f"➡️ Générer le tour suivant ({label})", key=f"advance_{bid}"):
            for m in next_round:
                db.insert_knockout_match(m["round"], m["position"],
                                         m["team1_id"], m["team2_id"],
                                         bracket_id=bid)
            st.rerun()

    # Vainqueur final
    finale = next(
        (m for m in bracket_matches if m["round"] == 1 and m["position"] == 1 and m["played"]),
        None,
    )
    if finale:
        winner = engine.get_winner(finale)
        loser = engine.get_loser(finale)
        if bid == 0:
            if winner:
                st.balloons()
                st.success(f"🏆 **Vainqueur du tournoi : {team_name(winner)} !**")
            if loser:
                st.info(f"🥈 Finaliste : {team_name(loser)}")
        else:
            start, _ = engine.consolation_position_range(bid, n_qualifiers_display, n_groups)
            if winner:
                st.success(f"🎖️ {start}e place : **{team_name(winner)}**")
            if loser:
                st.info(f"{start + 1}e place : {team_name(loser)}")

    # Petite finale (position 2 du round 1)
    petite_finale = next(
        (m for m in bracket_matches if m["round"] == 1 and m["position"] == 2 and m["played"]),
        None,
    )
    if petite_finale:
        winner_3 = engine.get_winner(petite_finale)
        loser_3 = engine.get_loser(petite_finale)
        if bid == 0:
            if winner_3:
                st.info(f"🥉 3e place : {team_name(winner_3)}")
            if loser_3:
                st.info(f"4e place : {team_name(loser_3)}")
        else:
            start, _ = engine.consolation_position_range(bid, n_qualifiers_display, n_groups)
            if winner_3:
                st.info(f"{start + 2}e place : {team_name(winner_3)}")
            if loser_3:
                st.info(f"{start + 3}e place : {team_name(loser_3)}")

    st.divider()

# Reset global
with st.expander("⚠️ Réinitialiser toutes les phases finales"):
    if st.button("Effacer tous les brackets et recommencer", type="secondary"):
        db.reset_knockout()
        st.rerun()
