import streamlit as st
import db
import engine

st.set_page_config(page_title="Setup — Tournoi à 6", layout="wide")
st.title("⚙️ Configuration du tournoi")

db.init_db()

LEVEL_LABELS = {1: "1 — Débutant", 2: "2 — Intermédiaire", 3: "3 — Fort"}

# ═══════════════════════════════════════════════════════════════════
# ÉTAPE 1 : Équipes
# ═══════════════════════════════════════════════════════════════════
st.header("1. Équipes")

teams = db.get_teams()

if teams:
    st.write(f"**{len(teams)} équipe(s) enregistrée(s)**")
    cols_header = st.columns([4, 2, 1])
    cols_header[0].markdown("**Nom**")
    cols_header[1].markdown("**Niveau**")
    for t in teams:
        col1, col2, col3 = st.columns([4, 2, 1])
        col1.write(t["name"])
        new_level = col2.selectbox(
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
        if col3.button("🗑️", key=f"del_{t['id']}"):
            db.delete_team(t["id"])
            st.rerun()

with st.form("add_team_form", clear_on_submit=True):
    c1, c2, c3 = st.columns([4, 2, 1])
    new_name = c1.text_input("Nom de l'équipe", label_visibility="visible")
    new_level = c2.selectbox("Niveau", [1, 2, 3], index=1,
                             format_func=lambda x: LEVEL_LABELS[x])
    submitted = c3.form_submit_button("＋", use_container_width=True)
    if submitted and new_name.strip():
        try:
            db.add_team(new_name.strip(), level=new_level)
            st.rerun()
        except Exception:
            st.error("Ce nom existe déjà.")

if teams:
    with st.expander("⚠️ Réinitialiser toutes les équipes"):
        if st.button("Supprimer toutes les équipes (et les matchs)", type="primary"):
            db.reset_teams()
            st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════
# ÉTAPE 2 : Groupes
# ═══════════════════════════════════════════════════════════════════
st.header("2. Groupes")

teams = db.get_teams()
if not teams:
    st.info("Ajoute d'abord des équipes.")
    st.stop()

groups = db.get_groups()

# ── Proposition automatique ──────────────────────────────────────
st.subheader("Répartition automatique (snake draft par niveau)")

col_a, col_b = st.columns([1, 2])
n_groups_auto = col_a.number_input(
    "Nombre de groupes", min_value=1, max_value=12, value=4, key="n_groups_auto"
)

if col_b.button("🎲 Proposer une répartition équilibrée", type="primary"):
    proposal = engine.propose_groups(teams, n_groups_auto)
    st.session_state["group_proposal"] = proposal
    st.session_state["n_groups_proposal"] = n_groups_auto
    # Effacer TOUS les anciens états de menus déroulants (sinon ils écrasent la nouvelle proposition)
    for k in list(st.session_state.keys()):
        if k.startswith("prop_"):
            del st.session_state[k]

if "group_proposal" in st.session_state:
    proposal = st.session_state["group_proposal"]
    n_prop = st.session_state["n_groups_proposal"]
    team_map = {t["id"]: t for t in teams}
    group_labels = [f"Groupe {i + 1}" for i in range(n_prop)]

    # Assignation initiale depuis la proposition (fallback si la clé session n'existe pas encore)
    initial_assign = {tid: gi for gi, tids in enumerate(proposal) for tid in tids}

    # Lire l'assignation courante depuis l'état des menus déroulants
    current_assign = {
        tid: st.session_state.get(f"prop_{tid}", gi)
        for gi, tids in enumerate(proposal) for tid in tids
    }

    # Construire les groupes depuis l'assignation courante
    current_groups: list[list[int]] = [[] for _ in range(n_prop)]
    for tid, gi in current_assign.items():
        if 0 <= gi < n_prop:
            current_groups[gi].append(tid)

    st.write("**Proposition — modifiez si besoin :**")
    cols_per_row = min(n_prop, 4)
    for row_start in range(0, n_prop, cols_per_row):
        row_slice = list(range(row_start, min(row_start + cols_per_row, n_prop)))
        row_cols = st.columns(len(row_slice))
        for col, gi in zip(row_cols, row_slice):
            tids = current_groups[gi]
            col.markdown(f"**Groupe {gi + 1}** ({len(tids)} éq.)")
            for tid in tids:
                t = team_map[tid]
                col.selectbox(
                    t["name"],
                    options=list(range(n_prop)),
                    format_func=lambda i, gl=group_labels: gl[i],
                    index=current_assign[tid],
                    key=f"prop_{tid}",
                )

    # Vérification de la répartition par niveau
    level_labels = {3: "Forts (★★★)", 2: "Intermédiaires (★★)", 1: "Débutants (★)"}
    for lvl in [3, 2, 1]:
        counts = [sum(1 for tid in g if team_map[tid]["level"] == lvl) for g in current_groups]
        if any(c > 0 for c in counts):
            st.caption(f"**{level_labels[lvl]}** : " + " · ".join(
                f"G{i+1}={c}" for i, c in enumerate(counts)
            ))

    if st.button("✅ Appliquer cette répartition", type="primary"):
        # Lire l'assignation finale directement depuis les menus déroulants
        final_assign = {tid: st.session_state.get(f"prop_{tid}", initial_assign[tid])
                        for tid in initial_assign}
        final_groups: list[list[int]] = [[] for _ in range(n_prop)]
        for tid, gi in final_assign.items():
            if 0 <= gi < n_prop:
                final_groups[gi].append(tid)

        db.reset_groups()
        for gi, tids in enumerate(final_groups):
            gid = db.add_group(f"Groupe {gi + 1}")
            for tid in tids:
                db.assign_team_group(tid, gid)
        for k in list(st.session_state.keys()):
            if k in ("group_proposal", "n_groups_proposal") or k.startswith("prop_"):
                del st.session_state[k]
        st.success("Répartition appliquée !")
        st.rerun()

st.divider()

# ── Gestion manuelle des groupes ─────────────────────────────────
st.subheader("Gestion manuelle des groupes")

col_left, col_right = st.columns(2)
with col_left:
    with st.form("add_group_form", clear_on_submit=True):
        group_name = st.text_input("Nom du groupe", placeholder="ex: Terrain 1")
        if st.form_submit_button("Créer") and group_name.strip():
            try:
                db.add_group(group_name.strip())
                st.rerun()
            except Exception:
                st.error("Ce nom existe déjà.")

with col_right:
    if groups:
        grp_to_del = st.selectbox("Supprimer", [g["name"] for g in groups])
        if st.button("Supprimer ce groupe", type="secondary"):
            gid = next(g["id"] for g in groups if g["name"] == grp_to_del)
            db.delete_group(gid)
            st.rerun()

groups = db.get_groups()
if not groups:
    st.info("Crée au moins un groupe ou utilise la répartition automatique.")
    st.stop()

st.divider()

# ── Assignation manuelle équipes → groupes ────────────────────────
st.subheader("Assignation manuelle")

group_options = {g["name"]: g["id"] for g in groups}
group_options_with_none = {"— Sans groupe —": None, **group_options}
keys = list(group_options_with_none.keys())

for team in teams:
    current = next((g["name"] for g in groups if g["id"] == team["group_id"]), "— Sans groupe —")
    sel = st.selectbox(
        f"{team['name']} ({'★' * team['level']})",
        keys,
        index=keys.index(current) if current in keys else 0,
        key=f"assign_{team['id']}",
    )
    new_gid = group_options_with_none[sel]
    if new_gid != team["group_id"]:
        db.assign_team_group(team["id"], new_gid)
        st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════
# ÉTAPE 3 : Génération du calendrier
# ═══════════════════════════════════════════════════════════════════
st.header("3. Générer le calendrier")

unassigned = [t for t in teams if t["group_id"] is None]
if unassigned:
    st.warning(f"{len(unassigned)} équipe(s) sans groupe : " + ", ".join(t["name"] for t in unassigned))

col_h, col_m, col_d, col_b = st.columns([1, 1, 1, 2])
start_h = col_h.number_input("Heure début", 6, 23, 9, key="start_h")
start_m = col_m.number_input("Minute", 0, 59, 0, step=5, key="start_m")
match_dur = col_d.number_input("Durée match (min)", 5, 30, 12, key="match_dur")
break_dur = 3  # fixe

existing_matches = db.get_matches()
if existing_matches:
    st.info(f"Calendrier existant : {len(existing_matches)} matchs.")

if not unassigned:
    btn_label = "🔄 Regénérer (efface les scores)" if existing_matches else "✅ Générer le calendrier"
    btn_type  = "secondary" if existing_matches else "primary"
    if st.button(btn_label, type=btn_type):
        db.reset_matches()
        # Générer les journées par groupe
        groups = db.get_groups()
        group_rounds: dict[int, list[list[tuple[int, int]]]] = {}
        for g in groups:
            gteams = db.get_teams(g["id"])
            if len(gteams) >= 2:
                group_rounds[g["id"]] = engine.generate_round_robin_rounds(
                    [t["id"] for t in gteams]
                )

        # Calculer le calendrier avec terrains et horaires
        assignments = engine.schedule_matches(
            group_rounds,
            n_terrains=4,
            match_duration=int(match_dur),
            break_duration=break_dur,
            start_hour=int(start_h),
            start_minute=int(start_m),
        )

        # Insérer les matchs
        key_to_assignment = {(a["group_id"], a["team1_id"], a["team2_id"]): a for a in assignments}
        for gid, rounds in group_rounds.items():
            for rnum, round_matches in enumerate(rounds, start=1):
                for t1, t2 in round_matches:
                    a = key_to_assignment.get((gid, t1, t2), {})
                    db.insert_match(
                        gid, t1, t2,
                        terrain_num=a.get("terrain_num"),
                        scheduled_time=a.get("scheduled_time"),
                        round_num=rnum,
                    )

        total = sum(len(r) for rounds in group_rounds.values() for r in rounds)
        st.success(f"{total} matchs générés ! Rends-toi sur la page Calendrier.")
        st.rerun()
