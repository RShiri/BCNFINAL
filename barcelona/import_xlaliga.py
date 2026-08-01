"""Import Barcelona match data from the XLALIGA dashboard dataset into elite_analytics.db.

XLALIGA (https://github.com/RShiri/XLALIGA) holds four finished La Liga seasons
(2022-23 .. 2025-26) as a static-site dataset:

  laliga_dashboard/data.js               window.LL_DATA   - season-keyed fixtures + team stats
  laliga_dashboard/players.js            window.LL_PLAYERS- season-keyed player aggregates
  laliga_dashboard/matches_detail/<id>.js window.MATCH_DETAIL - per-match shots/passes/
                                          dribbles/saves/goals/lineups

This script pulls every Barcelona fixture from those files and writes it into the
Elite Analytics SQLite database used by the rest of the barcelona/ subproject, so the
existing tooling (pass networks, shot maps, final-third entries) can read four seasons
instead of one.

Usage
-----
    py barcelona/import_xlaliga.py --source ../XLALIGA
    py barcelona/import_xlaliga.py --source ../XLALIGA --seasons 2022-23,2023-24
    py barcelona/import_xlaliga.py --source ../XLALIGA --dry-run

The importer is idempotent: re-running it replaces the rows it previously wrote for the
same fixtures. Matches already present from the native WhoScored scrape (which carry a
richer event taxonomy) are skipped by default -- pass --replace-existing to overwrite them.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys
from collections import defaultdict

DEFAULT_DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "EliteAnalytics", "data", "elite_analytics.db"
)
DEFAULT_SEASONS = ["2022-23", "2023-24", "2024-25", "2025-26"]
TEAM = "Barcelona"
COMPETITION = "La Liga"
SOURCE = "xlaliga"

# XLALIGA uses FotMob's club naming; the Elite Analytics DB was seeded from WhoScored.
TEAM_ALIASES = {
    "Atletico Madrid": "Atletico",
}

# WhoScored-style event types, matching what scraper.py already writes.
SHOT_GOAL = "Goal"
SHOT_SAVED = "SavedShot"
SHOT_MISSED = "MissedShots"
SHOT_BLOCKED = "BlockedShot"
SHOT_POST = "ShotOnPost"

FINAL_THIRD_X = 100.0 * 2.0 / 3.0  # pitch coordinates are 0-100, attacking left to right

# How far apart two records of the same fixture may be dated before they are treated as
# different matches (see find_existing).
FIXTURE_DAY_TOLERANCE = 10


# --------------------------------------------------------------------------- loading


def _load_window_js(path):
    """Read a `window.X = {...};` dashboard file and return the parsed object."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    _, _, payload = raw.partition("=")
    return json.loads(payload.strip().rstrip(";"))


def resolve_source(source):
    """Accept either the XLALIGA repo root or its laliga_dashboard/ folder."""
    candidates = [os.path.join(source, "laliga_dashboard"), source]
    for base in candidates:
        if os.path.isfile(os.path.join(base, "data.js")):
            return base
    raise SystemExit(
        f"Could not find data.js under {source!r}. Point --source at the XLALIGA repo root."
    )


# --------------------------------------------------------------------------- schema


def season_for_date(date):
    """'2026-01-11' -> '2025-26'. European seasons roll over in July."""
    try:
        day = datetime.date.fromisoformat((date or "")[:10])
    except ValueError:
        return None
    start = day.year if day.month >= 7 else day.year - 1
    return f"{start}-{str(start + 1)[2:]}"


def ensure_schema(conn):
    """Create the base tables if missing and add the columns this import needs."""
    cur = conn.cursor()

    # The four core tables normally come from EliteAnalytics/backend/database.py; create
    # them here too so the importer can bootstrap an empty database on its own.
    cur.execute(
        "CREATE TABLE IF NOT EXISTS teams (id INTEGER NOT NULL PRIMARY KEY, "
        "name VARCHAR, UNIQUE (name))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS matches (id INTEGER NOT NULL PRIMARY KEY, date VARCHAR, "
        "competition VARCHAR, home_team_id INTEGER, away_team_id INTEGER, "
        "home_score INTEGER, away_score INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS players (id INTEGER NOT NULL PRIMARY KEY, name VARCHAR, "
        "position VARCHAR, team_id INTEGER)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER NOT NULL PRIMARY KEY, match_id INTEGER, "
        "team_id INTEGER, player_id INTEGER, event_id INTEGER, minute INTEGER, second INTEGER, "
        "type_name VARCHAR, outcome VARCHAR, x FLOAT, y FLOAT, end_x FLOAT, end_y FLOAT, "
        "is_shot BOOLEAN, xg FLOAT, xt FLOAT, under_pressure BOOLEAN, is_big_chance BOOLEAN, "
        "is_penalty BOOLEAN, is_final_third_pass BOOLEAN, is_progressive_pass BOOLEAN, "
        "possession_chain_id INTEGER, qualifiers JSON)"
    )

    existing = {row[1] for row in cur.execute("PRAGMA table_info(matches)")}
    for column, decl in [
        ("season", "VARCHAR"),
        ("matchday", "INTEGER"),
        ("venue", "VARCHAR"),
        ("home_xg", "FLOAT"),
        ("away_xg", "FLOAT"),
        ("xg_estimated", "BOOLEAN"),
        ("source", "VARCHAR"),
        ("fotmob_id", "INTEGER"),
    ]:
        if column not in existing:
            cur.execute(f"ALTER TABLE matches ADD COLUMN {column} {decl}")

    cur.execute(
        """CREATE TABLE IF NOT EXISTS team_match_stats (
            match_id INTEGER, season VARCHAR, team_id INTEGER, opponent_id INTEGER,
            side VARCHAR, goals INTEGER, conceded INTEGER, xg FLOAT, xg_against FLOAT,
            possession INTEGER, shots INTEGER, sot INTEGER, passes INTEGER, pass_acc INTEGER,
            big_chances INTEGER, big_missed INTEGER, saves INTEGER, fouls INTEGER,
            duels_won INTEGER, corners INTEGER,
            PRIMARY KEY (match_id, team_id))"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS player_match_stats (
            match_id INTEGER, season VARCHAR, team_id INTEGER, player_id INTEGER,
            player VARCHAR, shirt_no INTEGER, position VARCHAR, started BOOLEAN,
            minutes INTEGER, on_minute INTEGER, off_minute INTEGER, goals INTEGER,
            assists INTEGER, xg FLOAT, xa FLOAT, rating FLOAT, yellow INTEGER, red INTEGER,
            motm BOOLEAN,
            PRIMARY KEY (match_id, team_id, player, shirt_no))"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS player_season_stats (
            season VARCHAR, player_id INTEGER, team_id INTEGER, player VARCHAR,
            position VARCHAR, matches INTEGER, starts INTEGER, minutes INTEGER,
            goals INTEGER, assists INTEGER, xg FLOAT, xa FLOAT, shots INTEGER, sot INTEGER,
            passes INTEGER, passes_completed INTEGER, pass_pct INTEGER, key_passes INTEGER,
            touches INTEGER, tackles INTEGER, interceptions INTEGER, aerials INTEGER,
            dribbles INTEGER, fouls INTEGER, clearances INTEGER, dispossessed INTEGER,
            saves INTEGER, yellow INTEGER, red INTEGER, rating FLOAT,
            PRIMARY KEY (season, player_id))"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS season_summary (
            season VARCHAR, team_id INTEGER, team VARCHAR, position INTEGER, played INTEGER,
            won INTEGER, drawn INTEGER, lost INTEGER, gf INTEGER, ga INTEGER, gd INTEGER,
            points INTEGER, xg_for FLOAT, xg_against FLOAT,
            PRIMARY KEY (season, team_id))"""
    )

    # Rows that predate this importer all came from the native WhoScored scrape; labelling
    # them makes the provenance of every match row explicit.
    cur.execute("UPDATE matches SET source = 'whoscored' WHERE source IS NULL")

    # Give the natively scraped cup and European fixtures a season too, so filtering by
    # season returns a club's whole campaign and not just its league matches.
    for mid, date in cur.execute(
        "SELECT id, date FROM matches WHERE season IS NULL AND date IS NOT NULL"
    ).fetchall():
        season = season_for_date(date)
        if season:
            cur.execute("UPDATE matches SET season = ? WHERE id = ?", (season, mid))

    for stmt in [
        "CREATE INDEX IF NOT EXISTS ix_events_match ON events (match_id)",
        "CREATE INDEX IF NOT EXISTS ix_events_type ON events (type_name)",
        "CREATE INDEX IF NOT EXISTS ix_events_player ON events (player_id)",
        "CREATE INDEX IF NOT EXISTS ix_matches_season ON matches (season)",
        "CREATE INDEX IF NOT EXISTS ix_pms_season ON player_match_stats (season)",
    ]:
        cur.execute(stmt)

    conn.commit()


# --------------------------------------------------------------------------- lookups


class TeamRegistry:
    """Maps XLALIGA club names onto teams.id, reusing existing rows where they match."""

    def __init__(self, conn):
        self.conn = conn
        self.by_name = {
            name: tid for tid, name in conn.execute("SELECT id, name FROM teams")
        }
        self._next = (
            max(self.by_name.values()) if self.by_name else 0
        ) + 1

    def get(self, raw_name):
        name = TEAM_ALIASES.get(raw_name, raw_name)
        if name not in self.by_name:
            tid = self._next
            self._next += 1
            self.conn.execute("INSERT INTO teams (id, name) VALUES (?, ?)", (tid, name))
            self.by_name[name] = tid
        return self.by_name[name]


class PlayerRegistry:
    """Resolves player names to ids.

    XLALIGA's per-match lineups carry no player id, but players.js does (they are the same
    WhoScored ids the Elite Analytics DB already uses), so names are resolved against the
    season aggregates first and against the existing players table second.
    """

    def __init__(self, conn, players_js):
        self.conn = conn
        self.rows = {}  # pid -> (name, position, team_id)
        self.by_season_team = defaultdict(dict)  # (season, team) -> {name: pid}
        self.by_name = {}
        for pid, name, team_id in conn.execute(
            "SELECT id, name, team_id FROM players"
        ):
            self.by_name.setdefault(name, pid)
        for season, entries in players_js.items():
            for entry in entries:
                pid = entry.get("pid")
                if pid is None:
                    continue
                self.by_season_team[(season, entry.get("team"))][entry["name"]] = pid
                self.by_name.setdefault(entry["name"], pid)

    def resolve(self, name, season, team_raw, position=None, team_id=None):
        if not name:
            return None
        pid = self.by_season_team.get((season, team_raw), {}).get(name)
        if pid is None:
            pid = self.by_name.get(name)
        if pid is None:
            return None
        if position and position != "Sub":
            self.rows[pid] = (name, position, team_id)
        else:
            self.rows.setdefault(pid, (name, position, team_id))
        return pid

    def flush(self):
        """Insert players we saw that the DB doesn't have yet (keeps existing rows intact)."""
        known = {pid for (pid,) in self.conn.execute("SELECT id FROM players")}
        new = [
            (pid, name, position, team_id)
            for pid, (name, position, team_id) in self.rows.items()
            if pid not in known
        ]
        self.conn.executemany(
            "INSERT INTO players (id, name, position, team_id) VALUES (?, ?, ?, ?)", new
        )
        return len(new)


# --------------------------------------------------------------------------- events


def _flag(value):
    return 1 if value else 0


def _shot_type(shot):
    if shot.get("goal"):
        return SHOT_GOAL
    if shot.get("blocked"):
        return SHOT_BLOCKED
    if shot.get("post"):
        return SHOT_POST
    if shot.get("onTarget"):
        return SHOT_SAVED
    return SHOT_MISSED


def build_events(detail, match_id, season, side_team, team_ids, players):
    """Turn one MATCH_DETAIL blob into rows for the events table.

    XLALIGA's detail files are derived from the same WhoScored match-centre feed as the
    native scrape, but only keep the on-ball attacking actions (passes, shots, take-ons,
    saves). Everything emitted here is therefore a subset of the native taxonomy, using
    the same type names so downstream queries do not need to special-case the source.
    """
    rows = []
    seq = 0

    def add(side, minute, second, type_name, outcome, **kw):
        nonlocal seq
        seq += 1
        team_raw = side_team[side]
        rows.append(
            {
                "match_id": match_id,
                "team_id": team_ids[side],
                "player_id": players.resolve(
                    kw.pop("player", None), season, team_raw, team_id=team_ids[side]
                ),
                "event_id": seq,
                "minute": minute,
                "second": second,
                "type_name": type_name,
                "outcome": outcome,
                "x": kw.pop("x", None),
                "y": kw.pop("y", None),
                "end_x": kw.pop("end_x", None),
                "end_y": kw.pop("end_y", None),
                "is_shot": _flag(kw.pop("is_shot", False)),
                "xg": kw.pop("xg", None),
                "xt": None,
                "under_pressure": 0,
                "is_big_chance": _flag(kw.pop("is_big_chance", False)),
                "is_penalty": _flag(kw.pop("is_penalty", False)),
                "is_final_third_pass": _flag(kw.pop("is_final_third_pass", False)),
                "is_progressive_pass": _flag(kw.pop("is_progressive_pass", False)),
                "possession_chain_id": None,
                "qualifiers": json.dumps(kw.pop("qualifiers")) if kw.get("qualifiers") else None,
            }
        )

    for p in detail.get("passes", []):
        quals = {k: True for k in ("key", "assist", "cross", "through") if p.get(k)}
        if p.get("recv"):
            quals["recv"] = p["recv"]
        add(
            p["team"],
            p.get("min"),
            p.get("sec"),
            "Pass",
            "Successful" if p.get("ok") else "Unsuccessful",
            player=p.get("player"),
            x=p.get("x"),
            y=p.get("y"),
            end_x=p.get("ex"),
            end_y=p.get("ey"),
            is_final_third_pass=(
                p.get("ok")
                and p.get("x") is not None
                and p.get("ex") is not None
                and p["x"] < FINAL_THIRD_X <= p["ex"]
            ),
            is_progressive_pass=p.get("prog"),
            qualifiers=quals,
        )

    for s in detail.get("shots", []):
        situation = s.get("sit") or ""
        quals = {k: v for k, v in (("body", s.get("body")), ("sit", situation)) if v}
        for key in ("gy", "gz"):
            if s.get(key) is not None:
                quals[key] = s[key]
        add(
            s["team"],
            s.get("min"),
            s.get("sec"),
            _shot_type(s),
            "Goal" if s.get("goal") else ("OnTarget" if s.get("onTarget") else "OffTarget"),
            player=s.get("player"),
            x=s.get("x"),
            y=s.get("y"),
            is_shot=True,
            xg=s.get("xg"),
            is_big_chance=s.get("big"),
            is_penalty=situation.lower().startswith("pen"),
            qualifiers=quals,
        )

    for d in detail.get("dribbles", []):
        add(
            d["team"],
            d.get("min"),
            d.get("sec"),
            "TakeOn",
            "Successful" if d.get("ok") else "Unsuccessful",
            player=d.get("player"),
            x=d.get("x"),
            y=d.get("y"),
        )

    for s in detail.get("saves", []):
        add(
            s["team"],
            s.get("min"),
            s.get("sec"),
            "Save",
            "Successful",
            player=s.get("player"),
            x=s.get("x"),
            y=s.get("y"),
        )

    # Own goals and penalties never appear in the shot list of the team credited with the
    # goal, so replay the goal feed for anything the shots above did not already cover.
    scored = {
        (r["team_id"], r["minute"], r["type_name"]) for r in rows if r["type_name"] == SHOT_GOAL
    }
    for g in detail.get("goals", []):
        team_id = team_ids[g["team"]]
        if (team_id, g.get("min"), SHOT_GOAL) in scored:
            continue
        quals = {k: True for k in ("pen", "own") if g.get(k)}
        if g.get("assist"):
            quals["assist_by"] = g["assist"]
        add(
            g["team"],
            g.get("min"),
            None,
            SHOT_GOAL,
            "Goal",
            player=g.get("scorer"),
            is_shot=True,
            is_penalty=g.get("pen"),
            qualifiers=quals,
        )

    rows.sort(key=lambda r: (r["minute"] or 0, r["second"] or 0))
    for i, row in enumerate(rows, start=1):
        row["event_id"] = i
    return rows


# --------------------------------------------------------------------------- import


EVENT_COLUMNS = [
    "id", "match_id", "team_id", "player_id", "event_id", "minute", "second", "type_name",
    "outcome", "x", "y", "end_x", "end_y", "is_shot", "xg", "xt", "under_pressure",
    "is_big_chance", "is_penalty", "is_final_third_pass", "is_progressive_pass",
    "possession_chain_id", "qualifiers",
]


def existing_fixtures(conn):
    """Every fixture already in the DB as (id, date, home, away, source) tuples."""
    query = (
        "SELECT m.id, m.date, h.name, a.name, m.source FROM matches m "
        "LEFT JOIN teams h ON h.id = m.home_team_id "
        "LEFT JOIN teams a ON a.id = m.away_team_id"
    )
    rows = []
    for mid, date, home, away, source in conn.execute(query):
        try:
            day = datetime.date.fromisoformat((date or "")[:10])
        except ValueError:
            continue
        rows.append((mid, day, home, away, source))
    return rows


def find_existing(fixtures, date, home, away, tolerance=FIXTURE_DAY_TOLERANCE):
    """Locate an already-stored row for the same fixture.

    The two providers disagree on the calendar date by up to a few days (FotMob stores the
    UTC kick-off, the native scrape the local match day, and one 2025/26 fixture differs by
    six), so matching on the exact date alone would re-import fixtures the DB already holds.
    A home/away pairing occurs once per La Liga season, so the club pair plus a nearest-date
    tie-break identifies the fixture unambiguously -- and keeps a league fixture from being
    confused with a cup or European tie between the same clubs weeks later.
    """
    try:
        target = datetime.date.fromisoformat((date or "")[:10])
    except ValueError:
        return None
    candidates = [
        (abs((day - target).days), mid, source)
        for mid, day, h, a, source in fixtures
        if h == home and a == away and abs((day - target).days) <= tolerance
    ]
    if not candidates:
        return None
    _, mid, source = min(candidates)
    return mid, source


def import_season(conn, base, season, season_data, players, teams, args, stats):
    matches = [
        m
        for m in season_data.get("matches", [])
        if TEAM in (m.get("home"), m.get("away")) and m.get("played")
    ]
    matches.sort(key=lambda m: m.get("date") or "")
    fixtures = existing_fixtures(conn)
    cur = conn.cursor()
    next_event_id = (cur.execute("SELECT COALESCE(MAX(id), 0) FROM events").fetchone()[0]) + 1

    for m in matches:
        home_raw, away_raw = m["home"], m["away"]
        home_id, away_id = teams.get(home_raw), teams.get(away_raw)
        prior = find_existing(
            fixtures,
            m.get("date"),
            TEAM_ALIASES.get(home_raw, home_raw),
            TEAM_ALIASES.get(away_raw, away_raw),
        )
        # A fixture the native WhoScored scrape already covers keeps its own (richer) event
        # stream and match id; it still picks up the season metadata and the per-match
        # team/player stat layers, which the Elite Analytics schema never had.
        keep_native = bool(prior) and prior[1] != SOURCE and not args.replace_existing
        match_id = prior[0] if keep_native else int(m["id"])

        detail_path = os.path.join(base, "matches_detail", f"{m['id']}.js")
        detail = _load_window_js(detail_path) if os.path.isfile(detail_path) else None
        if detail is None:
            stats["missing_detail"] += 1

        if args.dry_run:
            stats["matches" if not keep_native else "annotated"] += 1
            if detail and not keep_native:
                stats["events"] += len(
                    build_events(
                        detail,
                        match_id,
                        season,
                        {"home": home_raw, "away": away_raw},
                        {"home": home_id, "away": away_id},
                        players,
                    )
                )
            continue

        # Idempotency: drop anything a previous run of this importer wrote for the fixture.
        cur.execute("DELETE FROM team_match_stats WHERE match_id = ?", (match_id,))
        cur.execute("DELETE FROM player_match_stats WHERE match_id = ?", (match_id,))

        if keep_native:
            cur.execute(
                """UPDATE matches SET season = ?, matchday = ?, venue = COALESCE(venue, ?),
                       home_xg = ?, away_xg = ?, xg_estimated = ?, fotmob_id = ?
                   WHERE id = ?""",
                (
                    season,
                    m.get("matchday"),
                    m.get("venue") or None,
                    m.get("xg_home"),
                    m.get("xg_away"),
                    _flag(m.get("xg_estimated")),
                    m.get("fotmob_id"),
                    match_id,
                ),
            )
            stats["annotated"] += 1
        else:
            cur.execute("DELETE FROM events WHERE match_id = ?", (match_id,))
            if prior and prior[0] != match_id:
                # Same fixture stored under a different provider id (--replace-existing).
                for table in ("events", "team_match_stats", "player_match_stats"):
                    cur.execute(f"DELETE FROM {table} WHERE match_id = ?", (prior[0],))
                cur.execute("DELETE FROM matches WHERE id = ?", (prior[0],))
            cur.execute(
                """INSERT OR REPLACE INTO matches
                   (id, date, competition, home_team_id, away_team_id, home_score, away_score,
                    season, matchday, venue, home_xg, away_xg, xg_estimated, source, fotmob_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    match_id,
                    m.get("kickoff") or m.get("date"),
                    COMPETITION,
                    home_id,
                    away_id,
                    m.get("hs"),
                    m.get("as"),
                    season,
                    m.get("matchday"),
                    m.get("venue") or None,
                    m.get("xg_home"),
                    m.get("xg_away"),
                    _flag(m.get("xg_estimated")),
                    SOURCE,
                    m.get("fotmob_id"),
                ),
            )
            stats["matches"] += 1

        st = m.get("stats") or {}

        def stat(name, idx):
            values = st.get(name)
            return values[idx] if isinstance(values, list) and len(values) > idx else None

        for idx, (side, tid, opp_id) in enumerate(
            [("home", home_id, away_id), ("away", away_id, home_id)]
        ):
            cur.execute(
                """INSERT OR REPLACE INTO team_match_stats
                   (match_id, season, team_id, opponent_id, side, goals, conceded, xg,
                    xg_against, possession, shots, sot, passes, pass_acc, big_chances,
                    big_missed, saves, fouls, duels_won, corners)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    match_id,
                    season,
                    tid,
                    opp_id,
                    side,
                    m.get("hs") if idx == 0 else m.get("as"),
                    m.get("as") if idx == 0 else m.get("hs"),
                    stat("xg", idx),
                    stat("xg", 1 - idx),
                    stat("possession", idx),
                    stat("shots", idx),
                    stat("sot", idx),
                    stat("passes", idx),
                    stat("pass_acc", idx),
                    stat("big_chances", idx),
                    stat("big_missed", idx),
                    stat("saves", idx),
                    stat("fouls", idx),
                    stat("duels_won", idx),
                    stat("corners", idx),
                ),
            )

        if not detail:
            continue

        if not keep_native:
            rows = build_events(
                detail,
                match_id,
                season,
                {"home": home_raw, "away": away_raw},
                {"home": home_id, "away": away_id},
                players,
            )
            cur.executemany(
                f"INSERT INTO events ({', '.join(EVENT_COLUMNS)}) "
                f"VALUES ({', '.join('?' for _ in EVENT_COLUMNS)})",
                [
                    tuple([next_event_id + i] + [r[c] for c in EVENT_COLUMNS[1:]])
                    for i, r in enumerate(rows)
                ],
            )
            next_event_id += len(rows)
            stats["events"] += len(rows)

        lineups = detail.get("lineups") or {}
        for side, tid, team_raw in [
            ("home", home_id, home_raw),
            ("away", away_id, away_raw),
        ]:
            group = lineups.get(side) or {}
            for started, entries in (
                (1, group.get("starters") or []),
                (0, group.get("subs") or []),
            ):
                for entry in entries:
                    pid = players.resolve(
                        entry.get("name"),
                        season,
                        team_raw,
                        position=entry.get("pos"),
                        team_id=tid,
                    )
                    cur.execute(
                        """INSERT OR REPLACE INTO player_match_stats
                           (match_id, season, team_id, player_id, player, shirt_no, position,
                            started, minutes, on_minute, off_minute, goals, assists, xg, xa,
                            rating, yellow, red, motm)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            match_id,
                            season,
                            tid,
                            pid,
                            entry.get("name"),
                            entry.get("num"),
                            entry.get("pos"),
                            started,
                            entry.get("mins"),
                            entry.get("on"),
                            entry.get("off"),
                            entry.get("g"),
                            entry.get("a"),
                            entry.get("xg"),
                            entry.get("xa"),
                            entry.get("rating"),
                            entry.get("yc"),
                            entry.get("rc"),
                            _flag(entry.get("motm")),
                        ),
                    )
                    stats["player_rows"] += 1

    return matches


def import_season_aggregates(conn, season, season_data, players_js, teams, players, stats):
    """Barcelona's league position and its squad's season totals for one season."""
    cur = conn.cursor()
    team_id = teams.get(TEAM)

    row = next(
        (s for s in season_data.get("standings", []) if s.get("team") == TEAM), None
    )
    if row:
        xg_for = xg_against = 0.0
        for rec in season_data.get("xgRecords", []):
            if rec.get("team") == TEAM:
                xg_for += rec.get("xgf") or 0.0
                xg_against += rec.get("xga") or 0.0
        cur.execute(
            """INSERT OR REPLACE INTO season_summary
               (season, team_id, team, position, played, won, drawn, lost, gf, ga, gd,
                points, xg_for, xg_against)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                season,
                team_id,
                TEAM,
                row.get("rank"),
                row.get("P"),
                row.get("W"),
                row.get("D"),
                row.get("L"),
                row.get("GF"),
                row.get("GA"),
                row.get("GD"),
                row.get("Pts"),
                round(xg_for, 2),
                round(xg_against, 2),
            ),
        )
        stats["seasons"] += 1

    for entry in players_js.get(season, []):
        if entry.get("team") != TEAM:
            continue
        pid = entry.get("pid")
        players.resolve(entry.get("name"), season, TEAM, position=entry.get("pos"), team_id=team_id)
        cur.execute(
            """INSERT OR REPLACE INTO player_season_stats
               (season, player_id, team_id, player, position, matches, starts, minutes,
                goals, assists, xg, xa, shots, sot, passes, passes_completed, pass_pct,
                key_passes, touches, tackles, interceptions, aerials, dribbles, fouls,
                clearances, dispossessed, saves, yellow, red, rating)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                season,
                pid,
                team_id,
                entry.get("name"),
                entry.get("pos"),
                entry.get("mp"),
                entry.get("starts"),
                entry.get("mins"),
                entry.get("g"),
                entry.get("a"),
                entry.get("xg"),
                entry.get("xa"),
                entry.get("shots"),
                entry.get("sot"),
                entry.get("passes"),
                entry.get("passAcc"),
                entry.get("pass_pct"),
                entry.get("keyPasses"),
                entry.get("touches"),
                entry.get("tackles"),
                entry.get("interceptions"),
                entry.get("aerials"),
                entry.get("dribbles"),
                entry.get("fouls"),
                entry.get("clearances"),
                entry.get("dispossessed"),
                entry.get("saves"),
                entry.get("yc"),
                entry.get("rc"),
                entry.get("rating"),
            ),
        )
        stats["season_players"] += 1


# --------------------------------------------------------------------------- cli


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--source",
        default=os.environ.get("XLALIGA_DIR", os.path.join("..", "XLALIGA")),
        help="Path to the XLALIGA repo (or its laliga_dashboard/ folder).",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Target SQLite database.")
    parser.add_argument(
        "--seasons",
        default=",".join(DEFAULT_SEASONS),
        help="Comma-separated seasons to import (default: the last four finished ones).",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Overwrite fixtures already imported by the native WhoScored scrape.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts, write nothing.")
    args = parser.parse_args(argv)

    base = resolve_source(args.source)
    seasons = [s.strip() for s in args.seasons.split(",") if s.strip()]

    data = _load_window_js(os.path.join(base, "data.js"))
    players_js = _load_window_js(os.path.join(base, "players.js"))

    unknown = [s for s in seasons if s not in data.get("seasons", {})]
    if unknown:
        raise SystemExit(f"Season(s) not present in {base}/data.js: {', '.join(unknown)}")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = OFF")
    ensure_schema(conn)

    teams = TeamRegistry(conn)
    players = PlayerRegistry(conn, players_js)

    stats = defaultdict(int)
    for season in seasons:
        season_data = data["seasons"][season]
        imported = import_season(conn, base, season, season_data, players, teams, args, stats)
        if not args.dry_run:
            import_season_aggregates(
                conn, season, season_data, players_js, teams, players, stats
            )
        print(f"  {season}: {len(imported)} {TEAM} fixtures")

    if args.dry_run:
        conn.rollback()
        print(
            f"\nDry run: {stats['matches']} new matches / {stats['events']} events, plus "
            f"{stats['annotated']} existing fixtures annotated in place."
        )
        return 0

    new_players = players.flush()
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

    print(
        f"\nImported {stats['matches']} matches, {stats['events']} events, "
        f"{stats['player_rows']} player-match rows, {stats['season_players']} player-season rows, "
        f"{stats['seasons']} season summaries ({new_players} new players)."
    )
    if stats["annotated"]:
        print(
            f"{stats['annotated']} fixtures already scraped natively kept their richer event "
            f"stream and gained season metadata + stat rows "
            f"(--replace-existing swaps them for the XLALIGA version)."
        )
    if stats["missing_detail"]:
        print(f"{stats['missing_detail']} matches had no detail file (result only).")
    print(f"Database: {args.db} ({os.path.getsize(args.db) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
