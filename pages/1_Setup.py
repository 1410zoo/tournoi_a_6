import streamlit as st
import pandas as pd
import db
import engine

st.set_page_config(page_title="Setup — Tournoi à 6", layout="wide")
st.title("⚙️ Configuration du tournoi")

db.init_db()

LEVEL_LABELS = {1: "★ Débutant", 2: "★★ Intermédiaire", 3: "★★★ Fort"}

tab1, tab2, tab3 = st.tabs(["⚽ Équipes", "🏆 Répartition", "📅 Calendrier"])

# ═══════════════════════════════════════════════════════════════════
# TAB 1 : Équipes
# ═══════════════════════════════════════════════════════════════════
with tab1:
    teams = db.get_teams()

    # ── Import bulk ──────────────────────────────────────────────
    with st.expander("📋 Importer plusieurs équipes d'un coup", expanded=not bool(teams)):
        st.caption('Une équipe par ligne. Ajouter "1", "2" ou "3" à la fin pour le niveau (ex: "FC Thierrens 3"). Sans suffixe → niveau 2.')
        bulk_text = st.text_area(
            "Équipes",
            height=150,
            placeholder="FC Thierrens\nLes Bisons 3\nTeam Alpha 1\n...",
            label_visibility="collapsed",
        )
        if st.button("Importer", type="primary"):
            added, skipped = 0, []
            for raw in bulk_text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                parts = line.rsplit(" ", 1)
                if len(parts) == 2 and parts[1] in ("1", "2", "3"):
                    name, level = parts[0].strip(), int(parts[1])
                else:
                    name, level = line, 2
                if name:
                    try:
                        db.add_team(name, level=level)
                        added += 1
                    except Exception:
                        skipped.append(name)
            msg = f"{added} équipe(s) importée(s)."
            if skipped:
                msg += f" Ignorées (doublons) : {', '.join(skipped)}"
            st.success(msg)
            st.rerun()

    # ── Tableau des équipes ───────────────────────────────────────
    teams = db.get_teams()
    if teams:
        st.write(f"**{len(teams)} équipe(s) enregistrée(s)**")
        hc1, hc2, _ = st.columns([4, 2, 1])
        hc1.markdown("**Nom**")
        hc2.markdown("**Niveau**")
        for t in teams:
            c1, c2, c3 = st.columns([4, 2, 1])
            c1.write(t["name"])
            new_level = c2.selectbox(
                "Niveau",
                options=[1, 2, 3],
                format_func=lambda x: LEVEL_LABELS[x],
                index=t["level"] - 1,
                key=f"level_{t['id']}",
                label_visibility="collapsed",
            )
            if new_level != t["level"]:
                db.update_team_level(t["id"], new_level)
                st.rerun()
            if c3.button("🗑️", key=f"del_{t['id']}"):
                db.delete_team(t["id"])
                st.rerun()
    else:
        st.info("Aucune équipe. Utilise l'import ci-dessus ou le formulaire ci-dessous.")

    # ── Ajout individuel ─────────────────────────────────────────
    st.divider()
    with st.form("add_team_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([4, 2, 1])
        new_name = c1.text_input("Nom de l'équipe")
        new_level = c2.selectbox("Niveau", [1, 2, 3], index=1, format_func=lambda x: LEVEL_LABELS[x])
        if c3.form_submit_button("＋", use_container_width=True) and new_name.strip():
            try:
                db.add_team(new_name.strip(), level=new_level)
                st.rerun()
            except Exception:
                st.error("Ce nom existe déjà.")

    # ── Reset ────────────────────────────────────────────────────
    if teams:
        with st.expander("⚠️ Réinitialiser"):
            if st.button("Supprimer toutes les équipes et les matchs", type="primary"):
                db.reset_teams()
                st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 2 : Répartition
# ═══════════════════════════════════════════════════════════════════
with tab2:
    teams = db.get_teams()
    if not teams:
        st.info("Ajoute d'abord des équipes dans l'onglet Équipes.")
        st.stop()

    groups = db.get_groups()

    # ── Répartition actuelle (DB) ────────────────────────────────
    if groups:
        st.write("**Répartition actuelle en base :**")
        n_cols = min(len(groups), 4)
        cur_cols = st.columns(n_cols)
        for i, g in enumerate(groups):
            gt = db.get_teams(g["id"])
            lines = f"**{g['name']}** ({len(gt)} éq.)\n\n" + "\n\n".join(
                f"- {t['name']} {'★' * t['level']}" for t in gt
            )
            cur_cols[i % n_cols].markdown(lines)
        st.divider()

    # ── Nouvelle proposition ─────────────────────────────────────
    col_a, col_b = st.columns([1, 2])
    default_n = max(len(groups), 4) if groups else 4
    n_groups = col_a.number_input("Nombre de groupes", min_value=1, max_value=12, value=default_n, key="n_groups")

    if col_b.button("🎲 Proposer une répartition équilibrée", type="primary"):
        proposal = engine.propose_groups(teams, n_groups)
        glabels = [f"Groupe {i + 1}" for i in range(n_groups)]
        tmap = {t["id"]: t for t in teams}
        st.session_state["proposal_data"] = [
            (tid, tmap[tid]["name"], tmap[tid]["level"], glabels[gi])
            for gi, tids in enumerate(proposal)
            for tid in tids
        ]
        st.session_state["proposal_n_groups"] = n_groups
        st.session_state["proposal_version"] = st.session_state.get("proposal_version", 0) + 1

    # ── Éditeur de proposition ───────────────────────────────────
    if "proposal_data" in st.session_state:
        proposal_data: list[tuple] = st.session_state["proposal_data"]
        n_prop: int = st.session_state["proposal_n_groups"]
        glabels = [f"Groupe {i + 1}" for i in range(n_prop)]

        df = pd.DataFrame([
            {"Équipe": name, "Niveau": "★" * level, "Groupe": glabel}
            for _, name, level, glabel in proposal_data
        ])

        st.write("**Proposition — modifiez la colonne Groupe si besoin :**")
        edited_df = st.data_editor(
            df,
            column_config={
                "Groupe": st.column_config.SelectboxColumn(options=glabels, required=True),
            },
            disabled=["Équipe", "Niveau"],
            hide_index=True,
            use_container_width=True,
            key=f"group_editor_v{st.session_state.get('proposal_version', 0)}",
        )

        # Résumé des niveaux par groupe
        tmap = {t["id"]: t for t in teams}
        current_groups: list[list[int]] = [[] for _ in range(n_prop)]
        for i, row in edited_df.iterrows():
            tid = proposal_data[i][0]
            gi = glabels.index(row["Groupe"]) if row["Groupe"] in glabels else 0
            current_groups[gi].append(tid)

        for lvl, label in [(3, "Forts ★★★"), (2, "Intermédiaires ★★"), (1, "Débutants ★")]:
            counts = [sum(1 for tid in g if tmap[tid]["level"] == lvl) for g in current_groups]
            if any(c > 0 for c in counts):
                st.caption(f"**{label}** : " + " · ".join(f"G{i+1}={c}" for i, c in enumerate(counts)))

        if st.button("✅ Appliquer cette répartition", type="primary"):
            final_groups: list[list[int]] = [[] for _ in range(n_prop)]
            for i, row in edited_df.iterrows():
                tid = proposal_data[i][0]
                gi = glabels.index(row["Groupe"]) if row["Groupe"] in glabels else 0
                final_groups[gi].append(tid)

            db.reset_groups()
            for gi, tids in enumerate(final_groups):
                gid = db.add_group(f"Groupe {gi + 1}")
                for tid in tids:
                    db.assign_team_group(tid, gid)

            del st.session_state["proposal_data"]
            del st.session_state["proposal_n_groups"]
            st.success("Répartition appliquée !")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# TAB 3 : Calendrier
# ═══════════════════════════════════════════════════════════════════
with tab3:
    teams = db.get_teams()
    groups = db.get_groups()

    unassigned = [t for t in teams if t["group_id"] is None]
    if unassigned:
        st.warning(f"{len(unassigned)} équipe(s) sans groupe : " + ", ".join(t["name"] for t in unassigned))

    if not groups:
        st.info("Configure d'abord les groupes dans l'onglet Répartition.")
        st.stop()

    col_h, col_m, col_d = st.columns(3)
    start_h   = col_h.number_input("Heure début", 6, 23, 9, key="start_h")
    start_m   = col_m.number_input("Minute", 0, 59, 0, step=5, key="start_m")
    match_dur = col_d.number_input("Durée match (min)", 5, 30, 12, key="match_dur")

    existing_matches = db.get_matches()
    if existing_matches:
        st.info(f"Calendrier existant : {len(existing_matches)} matchs.")

    btn_label = "🔄 Regénérer (efface les scores)" if existing_matches else "✅ Générer le calendrier"
    btn_type  = "secondary" if existing_matches else "primary"

    if not unassigned and st.button(btn_label, type=btn_type):
        db.reset_matches()
        group_rounds: dict[int, list[list[tuple[int, int]]]] = {}
        for g in groups:
            gteams = db.get_teams(g["id"])
            if len(gteams) >= 2:
                group_rounds[g["id"]] = engine.generate_round_robin_rounds([t["id"] for t in gteams])

        assignments = engine.schedule_matches(
            group_rounds,
            n_terrains=4,
            match_duration=int(match_dur),
            break_duration=3,
            start_hour=int(start_h),
            start_minute=int(start_m),
        )

        key_to_a = {(a["group_id"], a["team1_id"], a["team2_id"]): a for a in assignments}
        for gid, rounds in group_rounds.items():
            for rnum, round_matches in enumerate(rounds, start=1):
                for t1, t2 in round_matches:
                    a = key_to_a.get((gid, t1, t2), {})
                    db.insert_match(gid, t1, t2,
                                    terrain_num=a.get("terrain_num"),
                                    scheduled_time=a.get("scheduled_time"),
                                    round_num=rnum)

        total = sum(len(r) for rounds in group_rounds.values() for r in rounds)
        st.success(f"{total} matchs générés ! Rends-toi sur la page Calendrier.")
        st.rerun()
