import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tournament.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS teams (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                name     TEXT NOT NULL UNIQUE,
                group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
                level    INTEGER NOT NULL DEFAULT 2
            );
            CREATE TABLE IF NOT EXISTS matches (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id       INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                team1_id       INTEGER NOT NULL REFERENCES teams(id),
                team2_id       INTEGER NOT NULL REFERENCES teams(id),
                score1         INTEGER,
                score2         INTEGER,
                played         INTEGER NOT NULL DEFAULT 0,
                terrain_num    INTEGER,
                scheduled_time TEXT,
                round_num      INTEGER
            );
            CREATE TABLE IF NOT EXISTS knockout (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                round      INTEGER NOT NULL,
                position   INTEGER NOT NULL,
                team1_id   INTEGER REFERENCES teams(id),
                team2_id   INTEGER REFERENCES teams(id),
                score1     INTEGER,
                score2     INTEGER,
                played     INTEGER NOT NULL DEFAULT 0,
                bracket_id INTEGER NOT NULL DEFAULT 0
            );
        """)
    _migrate()


def _migrate():
    """Add columns introduced after initial schema without breaking existing DBs."""
    additions = [
        ("teams",   "level INTEGER NOT NULL DEFAULT 2"),
        ("matches", "terrain_num INTEGER"),
        ("matches", "scheduled_time TEXT"),
        ("matches", "round_num INTEGER"),
        ("knockout","bracket_id INTEGER NOT NULL DEFAULT 0"),
    ]
    with get_conn() as conn:
        for table, col_def in additions:
            col_name = col_def.split()[0]
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except sqlite3.OperationalError:
                pass  # column already exists


# ── Groups ────────────────────────────────────────────────────────────────────

def get_groups():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM groups ORDER BY id")]


def add_group(name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
        return cur.lastrowid


def delete_group(group_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))


def reset_groups():
    with get_conn() as conn:
        conn.execute("DELETE FROM knockout")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM groups")


# ── Teams ─────────────────────────────────────────────────────────────────────

def get_teams(group_id: int | None = None):
    with get_conn() as conn:
        if group_id is None:
            return [dict(r) for r in conn.execute("SELECT * FROM teams ORDER BY id")]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM teams WHERE group_id = ? ORDER BY id", (group_id,)
        )]


def add_team(name: str, group_id: int | None = None, level: int = 2) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO teams (name, group_id, level) VALUES (?, ?, ?)",
            (name, group_id, level),
        )
        return cur.lastrowid


def update_team_level(team_id: int, level: int):
    with get_conn() as conn:
        conn.execute("UPDATE teams SET level = ? WHERE id = ?", (level, team_id))


def assign_team_group(team_id: int, group_id: int | None):
    with get_conn() as conn:
        conn.execute("UPDATE teams SET group_id = ? WHERE id = ?", (group_id, team_id))


def delete_team(team_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))


def reset_teams():
    with get_conn() as conn:
        conn.execute("DELETE FROM knockout")
        conn.execute("DELETE FROM matches")
        conn.execute("DELETE FROM teams")


# ── Matches ───────────────────────────────────────────────────────────────────

def get_matches(group_id: int | None = None):
    with get_conn() as conn:
        if group_id is None:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM matches ORDER BY terrain_num, scheduled_time, id"
            )]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM matches WHERE group_id = ? ORDER BY round_num, id",
            (group_id,),
        )]


def insert_match(group_id: int, team1_id: int, team2_id: int,
                 terrain_num: int | None = None, scheduled_time: str | None = None,
                 round_num: int | None = None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO matches
               (group_id, team1_id, team2_id, terrain_num, scheduled_time, round_num)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (group_id, team1_id, team2_id, terrain_num, scheduled_time, round_num),
        )


def save_score(match_id: int, score1: int, score2: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE matches SET score1=?, score2=?, played=1 WHERE id=?",
            (score1, score2, match_id),
        )


def reset_matches():
    with get_conn() as conn:
        conn.execute("DELETE FROM matches")


# ── Knockout ──────────────────────────────────────────────────────────────────

def get_knockout_matches(bracket_id: int | None = None):
    with get_conn() as conn:
        if bracket_id is None:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM knockout ORDER BY bracket_id, round, position"
            )]
        return [dict(r) for r in conn.execute(
            "SELECT * FROM knockout WHERE bracket_id=? ORDER BY round, position",
            (bracket_id,),
        )]


def get_knockout_bracket_ids():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT bracket_id FROM knockout ORDER BY bracket_id"
        ).fetchall()
        return [r["bracket_id"] for r in rows]


def insert_knockout_match(round_: int, position: int,
                          team1_id: int | None, team2_id: int | None,
                          bracket_id: int = 0):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO knockout (round, position, team1_id, team2_id, bracket_id)
               VALUES (?, ?, ?, ?, ?)""",
            (round_, position, team1_id, team2_id, bracket_id),
        )


def save_knockout_score(match_id: int, score1: int, score2: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE knockout SET score1=?, score2=?, played=1 WHERE id=?",
            (score1, score2, match_id),
        )


def reset_knockout():
    with get_conn() as conn:
        conn.execute("DELETE FROM knockout")
