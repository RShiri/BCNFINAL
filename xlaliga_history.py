"""Earlier Barcelona seasons, sourced from the XLALIGA dataset.

The dashboard's own pipeline is built on raw WhoScored `matchCentreData` caches
(`assets/data/match_*_cache.json`), and those only exist for 2025/26 — a full season of
them is ~770 MB, so the earlier ones were never kept here.

[XLALIGA](https://github.com/RShiri/XLALIGA) already publishes four finished La Liga
seasons, derived from the same WhoScored match-centre feed by the same lineage of builder
code. This module reads that dataset and produces exactly the structures
`build_dashboard.py` would have produced from raw caches, so the seasons before 2025/26
can appear in the season switcher without carrying gigabytes of raw JSON in this repo.

Point it at a clone of XLALIGA:

    git clone https://github.com/RShiri/XLALIGA ../XLALIGA
    py build_dashboard.py --xlaliga ../XLALIGA     # or set XLALIGA_DIR

What it can and cannot provide
------------------------------
XLALIGA's per-match files keep the on-ball attacking actions — shots, passes, dribbles,
saves, goals and the lineup sheet — which is what the Match Centre, the shot maps and the
Player Lab's shot/pass/dribble graphs draw. They do **not** carry the defensive event
stream, so for the imported seasons:

* the Player Lab's tackle map is empty (season tackle *totals* are still shown, they come
  from XLALIGA's season aggregates);
* per-match "duels won" comes from XLALIGA's own match stats rather than being recounted
  from events.

XLALIGA is a La Liga dataset, so the imported seasons cover the league only — no Copa del
Rey or Champions League ties. The competition table for those seasons shows one row.
"""

from __future__ import annotations

import json
import os

# Every season XLALIGA holds is offered, oldest first (read from its data.js, so a new
# season such as 2026/27 appears as soon as XLALIGA publishes it). build_dashboard skips
# any season this repo's own WhoScored caches already cover (2025/26): those carry the
# richer event stream, and they win.

TEAM = "Barcelona"
BARCA_COL = "#e0224e"
OPP_COL = "#4ea1ff"


def _load_window_js(path):
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    _, _, payload = raw.partition("=")
    return json.loads(payload.strip().rstrip(";"))


def season_label(season):
    """XLALIGA's '2024-25' -> the dashboard's '2024/25'."""
    return season.replace("-", "/")


def resolve(base):
    """Accept the XLALIGA repo root or its laliga_dashboard/ folder; None if not usable."""
    if not base:
        return None
    for candidate in (os.path.join(base, "laliga_dashboard"), base):
        if os.path.isfile(os.path.join(candidate, "data.js")):
            return candidate
    return None


class History:
    """Barcelona's seasons from XLALIGA, in the shapes build_dashboard.py expects."""

    def __init__(self, base):
        self.base = base
        self._data = _load_window_js(os.path.join(base, "data.js"))
        self._players = _load_window_js(os.path.join(base, "players.js"))
        self._detail_cache = {}

    # ---------------------------------------------------------------- matches

    def seasons(self):
        """XLALIGA's season keys ('2022-23', ...), oldest first."""
        return sorted(self._data.get("seasons", {}))

    def matches(self):
        """Barcelona fixtures in the shape build_website.load_matches() returns."""
        out = []
        for season in self.seasons():
            block = self._data.get("seasons", {}).get(season)
            if not block:
                continue
            for m in block.get("matches", []):
                if TEAM not in (m.get("home"), m.get("away")) or not m.get("played"):
                    continue
                out.append(self._match_record(m, season))
        out.sort(key=lambda m: m["date"])
        return out

    def _match_record(self, m, season):
        st = m.get("stats") or {}

        def pair(name, default=0):
            v = st.get(name)
            if isinstance(v, list) and len(v) == 2:
                return [default if v[0] is None else v[0], default if v[1] is None else v[1]]
            return [default, default]

        hn, an = m["home"], m["away"]
        hs, aws = m.get("hs") or 0, m.get("as") or 0
        xg_h, xg_a = pair("xg", 0.0)
        h_shots, a_shots = pair("shots")
        h_sot, a_sot = pair("sot")
        h_poss, a_poss = pair("possession")
        h_passes, a_passes = pair("passes")
        h_pacc_pct, a_pacc_pct = pair("pass_acc")
        h_bcc, a_bcc = pair("big_chances")
        h_bcm, a_bcm = pair("big_missed")
        h_saves, a_saves = pair("saves")
        h_fouls, a_fouls = pair("fouls")
        h_duel, a_duel = pair("duels_won")

        bcn_is_home = hn == TEAM
        bcn_goals, opp_goals = (hs, aws) if bcn_is_home else (aws, hs)
        result = "W" if bcn_goals > opp_goals else ("D" if bcn_goals == opp_goals else "L")

        return {
            "mid": str(m["id"]),
            "home": hn, "away": an,
            "home_score": hs, "away_score": aws,
            "date": str(m.get("date"))[:10],
            "comp": "La Liga",
            "season": season_label(season),
            "src": "xlaliga",
            "bcn_is_home": bcn_is_home,
            "opp_name": an if bcn_is_home else hn,
            "bcn_goals": bcn_goals, "opp_goals": opp_goals,
            "result": result,
            "bcn_xg": xg_h if bcn_is_home else xg_a,
            "opp_xg": xg_a if bcn_is_home else xg_h,
            "h_shots": h_shots, "a_shots": a_shots,
            "h_sot": h_sot, "a_sot": a_sot,
            "h_passes": h_passes, "a_passes": a_passes,
            "h_pacc": round(h_passes * h_pacc_pct / 100), "a_pacc": round(a_passes * a_pacc_pct / 100),
            "h_poss": h_poss, "a_poss": a_poss,
            "h_bcc": h_bcc, "a_bcc": a_bcc,
            "h_bcm": h_bcm, "a_bcm": a_bcm,
            "h_duel": h_duel, "a_duel": a_duel,
            "h_saves": h_saves, "a_saves": a_saves,
            "h_fouls": h_fouls, "a_fouls": a_fouls,
            "h_pacc_pct": h_pacc_pct, "a_pacc_pct": a_pacc_pct,
            "xg_h": xg_h, "xg_a": xg_a,
            "xg_source": "Model (est.)" if m.get("xg_estimated") else "FotMob",
            "venue": m.get("venue") or "",
            "referee": "",
            "attendance": "",
            "matchday": m.get("matchday"),
        }

    # ----------------------------------------------------------------- detail

    def detail(self, mid):
        """The raw XLALIGA MATCH_DETAIL blob for one fixture (cached)."""
        if mid not in self._detail_cache:
            path = os.path.join(self.base, "matches_detail", f"{mid}.js")
            self._detail_cache[mid] = _load_window_js(path) if os.path.isfile(path) else None
        return self._detail_cache[mid]

    def match_detail(self, m):
        """A match-centre file in this dashboard's format.

        XLALIGA's per-match format is the same builder lineage as ours, so the event lists
        pass straight through; what differs is the `rec` stats block (ours) versus the
        `stage`/`shootout`/`png` fields (theirs).
        """
        d = self.detail(m["mid"])
        if not d:
            return None

        hcol = BARCA_COL if m["bcn_is_home"] else OPP_COL
        acol = OPP_COL if m["bcn_is_home"] else BARCA_COL

        def lineup(side):
            group = (d.get("lineups") or {}).get(side) or {}
            starters, subs = [], []
            for entry in group.get("starters", []):
                starters.append(self._lineup_row(entry))
            for entry in group.get("subs", []):
                row = self._lineup_row(entry)
                row["on"] = entry.get("on")
                # A named substitute who never came on has no minutes — the match centre
                # lists them, greyed, exactly as it does for a WhoScored-sourced match.
                subs.append(row)
            subs.sort(key=lambda x: (x.get("on") is None, x.get("on") or 0))
            return {"starters": starters, "subs": subs}

        rec = {"stats": {
            "possession": [m["h_poss"], m["a_poss"]],
            "xg": [round(m["xg_h"], 2), round(m["xg_a"], 2)],
            "shots": [m["h_shots"], m["a_shots"]],
            "sot": [m["h_sot"], m["a_sot"]],
            "big_chances": [m["h_bcc"], m["a_bcc"]],
            "passes": [m["h_passes"], m["a_passes"]],
            "pass_acc": [m["h_pacc_pct"], m["a_pacc_pct"]],
            "saves": [m["h_saves"], m["a_saves"]],
            "duels_won": [m["h_duel"], m["a_duel"]],
            "fouls": [m["h_fouls"], m["a_fouls"]],
        }, "sources": ["xlaliga"]}

        return {
            "id": m["mid"], "date": m["date"], "stage": "La Liga", "venue": m.get("venue", ""),
            "maxMin": d.get("maxMin") or 90,
            "home": {"name": m["home"], "score": m["home_score"], "color": hcol},
            "away": {"name": m["away"], "score": m["away_score"], "color": acol},
            "shots": d.get("shots", []),
            "passes": d.get("passes", []),
            "dribbles": d.get("dribbles", []),
            "goals": d.get("goals", []),
            "saves": d.get("saves", []),
            "lineups": {"home": lineup("home"), "away": lineup("away")},
            "rec": rec,
        }

    @staticmethod
    def _lineup_row(entry):
        rating = entry.get("rating")
        return {
            "name": entry.get("name"), "num": entry.get("num"), "pos": entry.get("pos") or "",
            "mins": entry.get("mins") or 0,
            "rating": round(rating, 1) if rating else None,
            "g": entry.get("g") or 0, "a": entry.get("a") or 0,
            "yc": entry.get("yc") or 0, "rc": entry.get("rc") or 0,
            "motm": bool(entry.get("motm")),
        }

    # ---------------------------------------------------------------- players

    def season_player_accumulators(self, season):
        """Barcelona's squad totals for one season, as aggregate_players() accumulators.

        Returned in the *raw* accumulator shape (pacc_num / rating_sum / rating_n rather
        than the finished pacc / rating) so build_dashboard can merge these totals with the
        match-by-match ones it derives for 2025/26 before working out the derived columns.

        Every column but `prog` comes straight from XLALIGA's season aggregates — including
        tackles, interceptions, aerials and touches, which the per-match files do not carry.
        Progressive passes are counted from the match files.
        """
        prog = self._progressive_passes(season)
        out = {}
        for entry in self._players.get(season, []):
            if entry.get("team") != TEAM:
                continue
            name = entry["name"]
            apps = entry.get("mp") or 0
            rating = entry.get("rating") or 0.0
            out[name] = {
                "name": name, "pos": entry.get("pos") or "",
                "apps": apps, "starts": entry.get("starts") or 0,
                "mins": entry.get("mins") or 0,
                "goals": entry.get("g") or 0, "assists": entry.get("a") or 0,
                "shots": entry.get("shots") or 0, "sot": entry.get("sot") or 0,
                "keyp": entry.get("keyPasses") or 0,
                "passes": entry.get("passes") or 0,
                "pacc_num": entry.get("passAcc") or 0,
                "drib": entry.get("dribbles") or 0,
                "tackles": entry.get("tackles") or 0,
                "intc": entry.get("interceptions") or 0,
                "prog": prog.get(name, 0),
                "aerials": entry.get("aerials") or 0,
                "touches": entry.get("touches") or 0,
                "fouls": entry.get("fouls") or 0,
                "yellow": entry.get("yc") or 0, "red": entry.get("rc") or 0,
                # aggregate_players averages rating over appearances; season aggregates
                # already carry the average, so weight it back up by games played.
                "rating_sum": rating * apps, "rating_n": apps,
                "xg": entry.get("xg") or 0.0, "xa": entry.get("xa") or 0.0,
            }
        return out

    def _progressive_passes(self, season):
        """Progressive passes per Barcelona player, counted from the match files."""
        counts = {}
        for m in self.matches():
            if m["season"] != season_label(season):
                continue
            d = self.detail(m["mid"])
            if not d:
                continue
            side = "home" if m["bcn_is_home"] else "away"
            for p in d.get("passes", []):
                if p.get("team") == side and p.get("prog") and p.get("ok"):
                    name = p.get("player")
                    if name:
                        counts[name] = counts.get(name, 0) + 1
        return counts

    def player_shots(self, m):
        """Barcelona's shots in one match, in the Player Lab's playerShots shape.

        Coordinates are converted from WhoScored's 0-100 pitch to the 120x80 one the
        shot-map component draws on, matching what build_website's shot model emits.
        """
        d = self.detail(m["mid"])
        if not d:
            return {}
        side = "home" if m["bcn_is_home"] else "away"
        out = {}
        for s in d.get("shots", []):
            if s.get("team") != side:
                continue
            name = s.get("player")
            if not name:
                continue
            out.setdefault(name, []).append({
                "x": round((s.get("x") or 0) * 1.2, 2),
                "y": round((s.get("y") or 0) * 0.8, 2),
                "xg": round(float(s.get("xg") or 0), 3),
                "goal": bool(s.get("goal")),
                "ot": bool(s.get("onTarget")),
                "min": s.get("min") or 0,
                "sit": s.get("sit") or "Open Play",
                "body": s.get("body") or "",
                "big": bool(s.get("big")),
                "opp": m["opp_name"],
                "date": m["date"],
                "mid": m["mid"],
            })
        return out

    # --------------------------------------------------------- player events

    def player_events(self, m, rec, gi):
        """Add one match's Barcelona events to the Player Lab store.

        `rec(name)` returns that player's {shots, dribbles, tackles, passes} lists and `gi`
        is the match's index in the games table — same contract as the WhoScored path.
        Tackles are not emitted: XLALIGA's files carry no defensive events.
        """
        d = self.detail(m["mid"])
        if not d:
            return
        side = "home" if m["bcn_is_home"] else "away"

        def ri(v):
            return int(round(v or 0))

        for s in d.get("shots", []):
            if s.get("team") != side or not s.get("player"):
                continue
            rec(s["player"])["shots"].append([
                ri(s.get("x")), ri(s.get("y")), ri(s.get("gy")) if s.get("gy") is not None else 50,
                round(float(s.get("xg") or 0), 3),
                1 if s.get("goal") else 0,
                1 if s.get("onTarget") else 0,
                s.get("min") or 0, gi,
            ])

        for p in d.get("passes", []):
            if p.get("team") != side or not p.get("player"):
                continue
            x, y = p.get("x") or 0, p.get("y") or 0
            ex = p.get("ex") if p.get("ex") is not None else x
            ey = p.get("ey") if p.get("ey") is not None else y
            rec(p["player"])["passes"].append([
                ri(x), ri(y), ri(ex), ri(ey),
                1 if p.get("ok") else 0,
                1 if p.get("prog") else 0,
                p.get("min") or 0, gi,
            ])

        # The carry destination of a take-on is the player's next touch, same rule the
        # WhoScored path uses (next on-ball action within 8 seconds).
        touches = {}
        for group, key in ((d.get("passes", []), "player"), (d.get("shots", []), "player")):
            for e in group:
                if e.get("team") != side or not e.get(key):
                    continue
                tt = (e.get("min") or 0) * 60 + (e.get("sec") or 0)
                touches.setdefault(e[key], []).append((tt, e.get("x") or 0, e.get("y") or 0))
        for lst in touches.values():
            lst.sort()

        for dr in d.get("dribbles", []):
            if dr.get("team") != side or not dr.get("player"):
                continue
            x, y = dr.get("x") or 0, dr.get("y") or 0
            tt = (dr.get("min") or 0) * 60 + (dr.get("sec") or 0)
            exy = (-1, -1)
            for (t2, x2, y2) in touches.get(dr["player"], []):
                if t2 > tt and t2 - tt <= 8 and (abs(x2 - x) > 0.8 or abs(y2 - y) > 0.8):
                    exy = (ri(x2), ri(y2))
                    break
            rec(dr["player"])["dribbles"].append([
                ri(x), ri(y), exy[0], exy[1],
                1 if dr.get("ok") else 0,
                dr.get("min") or 0, gi,
            ])
