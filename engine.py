"""
Logique métier pure — aucun accès BDD, aucun effet de bord Streamlit.
"""
import math


# ── Répartition équilibrée des équipes (snake draft) ─────────────────────────

def propose_groups(teams: list[dict], n_groups: int) -> list[list[int]]:
    """
    Retourne n_groups listes de team_id, équilibrées par niveau.
    Utilise un snake draft : les équipes triées par niveau (desc) sont
    distribuées en zigzag pour que chaque groupe ait un mix équitable.

    Exemple avec 12 équipes, 3 groupes, niveaux [3,3,3,3,2,2,2,2,1,1,1,1] :
      Rang 0→2 (forward) : G0, G1, G2
      Rang 3→5 (backward): G2, G1, G0
      Rang 6→8 (forward) : G0, G1, G2
      Rang 9→11 (backward): G2, G1, G0
    """
    sorted_teams = sorted(teams, key=lambda t: -t.get("level", 2))
    groups: list[list[int]] = [[] for _ in range(n_groups)]
    for i, team in enumerate(sorted_teams):
        row = i // n_groups
        col = i % n_groups
        group_idx = col if row % 2 == 0 else (n_groups - 1 - col)
        groups[group_idx].append(team["id"])
    return groups


# ── Génération du calendrier round-robin ──────────────────────────────────────

def generate_round_robin_rounds(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    """
    Retourne une liste de journées. Chaque journée est une liste de (t1, t2).
    Garantit qu'une équipe n'apparaît qu'une fois par journée (utile pour le
    calcul des repos dans le calendrier).
    """
    teams = list(team_ids)
    if len(teams) % 2 == 1:
        teams.append(None)  # BYE
    n = len(teams)
    rounds = []
    for _ in range(n - 1):
        round_matches = [
            (teams[i], teams[n - 1 - i])
            for i in range(n // 2)
            if teams[i] is not None and teams[n - 1 - i] is not None
        ]
        if round_matches:
            rounds.append(round_matches)
        # Rotation : teams[0] fixe, le reste tourne
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


def generate_round_robin(team_ids: list[int]) -> list[tuple[int, int]]:
    """Version plate (sans journées) — rétrocompatibilité."""
    return [pair for round_ in generate_round_robin_rounds(team_ids) for pair in round_]


# ── Calcul du calendrier avec terrains ───────────────────────────────────────

def schedule_matches(
    group_rounds: dict[int, list[list[tuple[int, int]]]],
    n_terrains: int = 4,
    match_duration: int = 12,
    break_duration: int = 3,
    start_hour: int = 9,
    start_minute: int = 0,
) -> list[dict]:
    """
    Distribue les matchs sur n_terrains de façon à ce que tous les groupes
    terminent au même créneau, quelle que soit leur taille.

    Algorithme :
      1. Calculer T = ceil(total_matchs / n_terrains) — nombre total de créneaux.
      2. Pour chaque groupe G (n_G matchs), attribuer à son match k un
         "créneau idéal" = k × (T-1) / (n_G-1), qui étale linéairement
         les matchs de 0 à T-1. Les groupes plus petits jouent moins souvent
         mais finissent en même temps que les grands.
      3. Trier tous les matchs par créneau idéal, puis regrouper par paquets
         de n_terrains → chaque paquet = un créneau réel, terrain = position
         dans le paquet.
    """
    slot_dur = match_duration + break_duration
    group_ids = list(group_rounds.keys())

    # Aplatir chaque groupe en liste ordonnée (respect de l'ordre des journées)
    per_group: dict[int, list[tuple[int, int, int]]] = {
        gid: [
            (rnum, t1, t2)
            for rnum, round_matches in enumerate(group_rounds[gid], 1)
            for t1, t2 in round_matches
        ]
        for gid in group_ids
    }

    total_matches = sum(len(v) for v in per_group.values())
    if total_matches == 0:
        return []

    T = math.ceil(total_matches / n_terrains)  # nombre de créneaux nécessaires

    # Attribuer un créneau idéal (flottant) à chaque match
    tagged: list[tuple[float, int, int, int, int]] = []  # (ideal_slot, gid, rnum, t1, t2)
    for gid, matches in per_group.items():
        n = len(matches)
        for k, (rnum, t1, t2) in enumerate(matches):
            ideal = k * (T - 1) / (n - 1) if n > 1 else 0.0
            tagged.append((ideal, gid, rnum, t1, t2))

    # Trier par créneau idéal (à égalité : ordre groupe pour la reproductibilité)
    tagged.sort(key=lambda x: (x[0], x[1]))

    # Assigner terrain et heure réelle
    assignments = []
    for i, (_, gid, rnum, t1, t2) in enumerate(tagged):
        slot = i // n_terrains
        terrain = (i % n_terrains) + 1
        total_min = start_hour * 60 + start_minute + slot * slot_dur
        assignments.append({
            "group_id": gid,
            "team1_id": t1,
            "team2_id": t2,
            "terrain_num": terrain,
            "scheduled_time": f"{total_min // 60:02d}:{total_min % 60:02d}",
            "round_num": rnum,
        })

    return assignments


# ── Calcul des classements ────────────────────────────────────────────────────

def _team_stats(team_id: int, matches: list[dict]) -> dict:
    played = wins = draws = losses = gf = ga = pts = 0
    for m in matches:
        if not m["played"]:
            continue
        if m["team1_id"] == team_id:
            s, c = m["score1"], m["score2"]
        elif m["team2_id"] == team_id:
            s, c = m["score2"], m["score1"]
        else:
            continue
        played += 1
        gf += s
        ga += c
        if s > c:
            wins += 1; pts += 3
        elif s == c:
            draws += 1; pts += 1
        else:
            losses += 1
    return {"played": played, "wins": wins, "draws": draws, "losses": losses,
            "gf": gf, "ga": ga, "gd": gf - ga, "pts": pts}


def _h2h_stats(team_ids: list[int], matches: list[dict]) -> dict[int, dict]:
    id_set = set(team_ids)
    h2h = [m for m in matches
           if m["played"] and m["team1_id"] in id_set and m["team2_id"] in id_set]
    return {tid: _team_stats(tid, h2h) for tid in team_ids}


def compute_standings(team_ids: list[int], matches: list[dict]) -> list[dict]:
    """
    Classement par poule selon :
      1. Points
      2. Confrontations directes (pts puis gd entre équipes à égalité)
      3. Goal difference général
      4. Buts marqués général
    """
    stats = {tid: _team_stats(tid, matches) for tid in team_ids}

    sorted_ids = sorted(team_ids, key=lambda t: (-stats[t]["pts"], -stats[t]["gd"], -stats[t]["gf"]))

    result = []
    i = 0
    while i < len(sorted_ids):
        j = i + 1
        while j < len(sorted_ids) and stats[sorted_ids[j]]["pts"] == stats[sorted_ids[i]]["pts"]:
            j += 1
        group = sorted_ids[i:j]
        if len(group) > 1:
            h2h = _h2h_stats(group, matches)
            group.sort(key=lambda t: (
                -h2h[t]["pts"], -h2h[t]["gd"],
                -stats[t]["gd"], -stats[t]["gf"],
            ))
        result.extend(group)
        i = j

    return [{"rank": r + 1, "team_id": tid, **stats[tid]} for r, tid in enumerate(result)]


# ── Phases finales : bracket d'élimination ───────────────────────────────────

def generate_bracket(qualified: list[int], bracket_id: int = 0) -> list[dict]:
    """
    Construit le premier tour d'un bracket d'élimination directe.
    `qualified` : team_ids ordonnés du meilleur au moins bon.
    Complète avec None (bye) jusqu'à la puissance de 2 supérieure.
    Les meilleures équipes reçoivent les byes.
    """
    n = len(qualified)
    if n < 2:
        raise ValueError("Il faut au moins 2 équipes.")
    bracket_size = 2 ** math.ceil(math.log2(n))
    seeds = qualified + [None] * (bracket_size - n)

    total_rounds = int(math.log2(bracket_size))
    matches = []
    for i in range(bracket_size // 2):
        matches.append({
            "round": total_rounds,
            "position": i + 1,
            "team1_id": seeds[i],
            "team2_id": seeds[bracket_size - 1 - i],
            "bracket_id": bracket_id,
        })
    return matches


def get_winner(match: dict) -> int | None:
    if not match.get("played"):
        return None
    if match["score1"] > match["score2"]:
        return match["team1_id"]
    if match["score2"] > match["score1"]:
        return match["team2_id"]
    return None


def get_loser(match: dict) -> int | None:
    if not match.get("played"):
        return None
    if match["score1"] > match["score2"]:
        return match["team2_id"]
    if match["score2"] > match["score1"]:
        return match["team1_id"]
    return None


def advance_knockout(ko_matches: list[dict], bracket_id: int = 0) -> list[dict]:
    """
    À partir des matchs KO d'un bracket, génère les matchs du tour suivant.
    Quand on avance depuis les demi-finales (2 matchs → round final),
    crée automatiquement le match pour la 3e place (position 2 du round final).
    Retourne [] si le bracket est terminé ou si des matchs sont encore en attente.
    """
    bracket = [m for m in ko_matches if m.get("bracket_id", 0) == bracket_id]
    if not bracket:
        return []

    rounds = sorted(set(m["round"] for m in bracket))
    current_round = rounds[-1]
    current = sorted([m for m in bracket if m["round"] == current_round],
                     key=lambda m: m["position"])

    if any(not m["played"] for m in current):
        return []
    if len(current) == 1:
        return []  # finale (ou match 3e place) déjà joué(e)

    next_round = current_round - 1
    if next_round < 1:
        return []

    winners = [get_winner(m) for m in current]
    next_matches = []

    # Matchs des gagnants (demi-finale → finale, quart → demi, etc.)
    for i in range(0, len(winners), 2):
        next_matches.append({
            "round": next_round,
            "position": i // 2 + 1,
            "team1_id": winners[i],
            "team2_id": winners[i + 1] if i + 1 < len(winners) else None,
            "bracket_id": bracket_id,
        })

    # Match pour la 3e place : uniquement quand on arrive au round final (2 semis → final)
    if len(current) == 2 and next_round == 1:
        loser1 = get_loser(current[0])
        loser2 = get_loser(current[1])
        next_matches.append({
            "round": next_round,
            "position": 2,  # position 2 = match pour la 3e place
            "team1_id": loser1,
            "team2_id": loser2,
            "bracket_id": bracket_id,
        })

    return next_matches


# ── Consolation : brackets pour les non-qualifiés ────────────────────────────

def get_consolation_bracket_id(group_rank: int) -> int:
    """
    Convertit le rang de groupe (3, 4, 5, 6...) en bracket_id de consolation.
    bracket_id 0 = main. bracket_id = group_rank pour les consolations.
    """
    return group_rank


def consolation_position_range(group_rank: int, n_qualifiers: int, n_groups: int) -> tuple[int, int]:
    """
    Retourne (start, end) des positions déterminées par le bracket de consolation
    pour les équipes ayant terminé `group_rank`e dans leur groupe.

    Exemples avec n_qualifiers=2, n_groups=4 :
      group_rank=3 → positions 9–12
      group_rank=5 → positions 17–20
    """
    k = group_rank - n_qualifiers - 1  # 0-indexed consolation rank
    start = n_qualifiers * n_groups + k * n_groups + 1
    return start, start + n_groups - 1
