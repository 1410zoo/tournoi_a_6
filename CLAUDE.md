# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Application de gestion d'un tournoi de football à 6 (6-a-side) organisé chaque été à Thierrens. Remplace un fichier Excel. Le nombre d'équipes et de groupes est variable d'une édition à l'autre (typiquement 4 groupes, ~28 équipes).

## Lancement

```bash
pip install -r requirements.txt
streamlit run app.py
```

Les données sont stockées dans `data/tournament.db` (SQLite, créé automatiquement au premier lancement). En cas de migration de schéma, `db._migrate()` ajoute les colonnes manquantes sans toucher aux données existantes.

## Architecture

```
app.py          Point d'entrée Streamlit, métriques globales
db.py           Couche SQLite : init_db(), _migrate(), fonctions CRUD (jamais de logique métier)
engine.py       Logique métier pure, sans effet de bord ni accès BDD
pages/
  1_Setup.py          Équipes (+ niveaux), groupes, répartition auto, génération calendrier
  2_Calendrier.py     Affichage par terrain ou groupe, saisie des scores
  3_Classements.py    Classements par groupe avec mise en évidence des qualifiés
  4_Phases_finales.py Brackets principal + consolation, avancement automatique
```

**Règle d'architecture :** toute la logique métier (calculs, algorithmes) vit dans `engine.py`. Les pages Streamlit n'ont accès qu'à `db.py` (données) et `engine.py` (calculs).

## Schéma SQLite

```sql
groups   (id, name)
teams    (id, name, group_id FK, level INTEGER DEFAULT 2)
matches  (id, group_id FK, team1_id FK, team2_id FK,
          score1, score2, played DEFAULT 0,
          terrain_num, scheduled_time TEXT, round_num)
knockout (id, round, position, team1_id FK, team2_id FK,
          score1, score2, played DEFAULT 0,
          bracket_id INTEGER DEFAULT 0)
```

## Niveaux d'équipes et répartition

Chaque équipe a un niveau 1 (débutant), 2 (intermédiaire), 3 (fort).
`engine.propose_groups(teams, n_groups)` utilise un **snake draft** sur les équipes triées par niveau décroissant pour produire des groupes équilibrés.

## Calendrier avec terrains

`engine.schedule_matches(group_rounds, n_terrains=4, match_duration=12, break_duration=3, ...)` :
- Assigne chaque groupe à un terrain par cyclage (groupe 0→T1, 1→T2…, groupe 4→T1 si >4 groupes)
- Les matchs d'un même terrain sont séquentiels, les 4 terrains tournent en parallèle
- `engine.generate_round_robin_rounds(team_ids)` retourne une liste de journées (chaque équipe joue une fois par journée)

## Règles de classement (par groupe)

1. **Points** (V=3, N=1, D=0)
2. **Confrontations directes** entre équipes à égalité — mini-classement interne (pts puis goal diff H2H)
3. **Goal difference général**
4. **Buts marqués général**

## Phases finales

`knockout.bracket_id` :
- `0` = bracket principal (équipes qualifiées)
- `N` = bracket de consolation pour les équipes terminant Nèmes dans leur groupe (ex: `5` = 5es de groupe → places 17-20 avec 4 groupes et 4 qualifiés)

`engine.generate_bracket(qualified, bracket_id)` crée le premier tour (complète avec None/bye jusqu'à la puissance de 2).
`engine.advance_knockout(ko_matches, bracket_id)` génère le tour suivant. Quand il avance depuis les demi-finales (2 matchs → round 1), il crée automatiquement `position=1` (finale) ET `position=2` (match pour la 3e place).

`engine.consolation_position_range(group_rank, n_qualifiers, n_groups)` retourne `(start, end)` des places déterminées par un bracket de consolation.
