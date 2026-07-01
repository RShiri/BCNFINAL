"""
BCNProject – Single-Page Dashboard Builder (WC2026-style, one team)
====================================================================
Generates a single-page app modelled on the World Cup 2026 dashboard, but for
one club (FC Barcelona):

  assets/html/index.html   – SPA shell (static, written by write_static_shell)
  assets/html/app.js       – SPA logic  (static, written by write_static_shell)
  assets/html/styles.css   – WC2026 stylesheet (copied verbatim)
  assets/html/data.js      – GENERATED here: window.DATA = {...}
  assets/html/match_*.html – per-match detail pages (shot maps, pass networks …)

The detailed match pages keep every graph/stat; the SPA links into them from the
"Shot Maps" tab and each match row, so nothing is removed.

Run:  py build_dashboard.py
"""

import json, glob, os, re, sys, shutil, datetime

ROOT     = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(ROOT, "assets", "html")
DATA_DIR = os.path.join(ROOT, "assets", "data")
LOGO_SRC = os.path.join(ROOT, "team_logos")
LOGO_DST = os.path.join(HTML_DIR, "logos")

sys.path.insert(0, ROOT)
import build_website as bw   # reuse load_matches + shot model + colours

# design tokens (mirror styles.css)
ACC, BLUE, WARN, BAD, MUTED, TEXT = "#3ddc97", "#4ea1ff", "#ffb454", "#ff6b81", "#93a0bd", "#e8edf7"
CARD, CARD2, LINE, BG, BG2 = "#161d31", "#1b2440", "#26304d", "#0b0f1a", "#121829"


# ---------------------------------------------------------------------------
# SEASON HELPERS  – derive the football season a match belongs to from its date.
# A season runs Jul->Jun, so any match_*_cache.json dated 2026-07 or later is
# automatically bucketed into 2026/27 (see DEVELOPER_GUIDE for the 26/27 pipeline).
# ---------------------------------------------------------------------------
def season_of(date):
    """'YYYY-MM-DD' -> 'YYYY/YY'. e.g. '2025-08-16' -> '2025/26', '2026-06-14' -> '2025/26'."""
    try:
        y, m = int(str(date)[:4]), int(str(date)[5:7])
    except (ValueError, TypeError):
        return ""
    start = y if m >= 7 else y - 1
    return f"{start}/{(start + 1) % 100:02d}"


def next_season(season):
    """'2025/26' -> '2026/27' (the upcoming season, offered in the UI before data exists)."""
    try:
        start = int(str(season)[:4]) + 1
    except (ValueError, TypeError):
        return ""
    return f"{start}/{(start + 1) % 100:02d}"


# ---------------------------------------------------------------------------
# TEAM BADGES  – resolve a team name to a logo file, copy into assets/html/logos
# ---------------------------------------------------------------------------
_LOGO_FILES = os.listdir(LOGO_SRC) if os.path.isdir(LOGO_SRC) else []
_LOGO_ALIAS = {
    "psg": "paris", "paris saint-germain": "paris", "atletico": "atletico madrid",
    "atletico madrid": "atletico madrid", "athletic club": "athletic club",
    "inter": "inter", "inter milan": "inter", "man city": "manchester city",
    "spurs": "tottenham", "wolves": "wolverhampton", "newcastle": "newcastle",
    "real betis": "betis", "betis": "betis", "fc copenhagen": "copenhagen",
    "sk slavia prague": "slavia", "slavia prague": "slavia", "club brugge": "brugge",
    "olympiacos": "olympiacos", "eintracht frankfurt": "eint frankfurt",
    "deportivo alaves": "alaves", "alaves": "alaves", "real oviedo": "oviedo",
    "rayo vallecano": "rayo vallecano", "celta vigo": "celta vigo",
    "real sociedad": "real sociedad", "real madrid": "real madrid",
}
_logo_cache = {}


def _slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def team_logo(name):
    """Return a relative logo path (logos/xxx.png) for a team name, or ''. Copies the
       matched source PNG into assets/html/logos on first use."""
    if not name:
        return ""
    if name in _logo_cache:
        return _logo_cache[name]
    key = name.lower().strip()
    cand = _LOGO_ALIAS.get(key, key)
    match = None
    for f in _LOGO_FILES:
        base = f.lower().replace("_logo.png", "").replace(".png", "")
        if base == cand or cand in base or base in cand:
            match = f
            break
    if match is None:
        # loose: any word overlap
        words = set(re.split(r"\s+", cand))
        for f in _LOGO_FILES:
            base = f.lower().replace("_logo.png", "").replace(".png", "")
            if words & set(re.split(r"[\s_]+", base)):
                match = f
                break
    if match is None:
        _logo_cache[name] = ""
        return ""
    os.makedirs(LOGO_DST, exist_ok=True)
    safe = _slugify(match.replace("_logo.png", "").replace(".png", "")) + ".png"
    dst = os.path.join(LOGO_DST, safe)
    if not os.path.exists(dst):
        try:
            shutil.copyfile(os.path.join(LOGO_SRC, match), dst)
        except Exception:
            pass
    rel = "logos/" + safe
    _logo_cache[name] = rel
    return rel


# ---------------------------------------------------------------------------
# PLAYER + SHOT AGGREGATION
# ---------------------------------------------------------------------------
def _sumdict(st, key):
    v = st.get(key)
    if isinstance(v, dict):
        return sum(v.values())
    return v or 0


def _final_rating(st):
    r = st.get("ratings")
    if isinstance(r, dict) and r:
        k = max(r, key=lambda x: int(x))
        return float(r[k])
    return None


def _player_minutes(d, player, max_minute):
    """Reconstruct minutes played from Substitution events."""
    pid = player.get("playerId")
    on = off = None
    for ev in d.get("events", []):
        if ev.get("playerId") != pid:
            continue
        t = ev.get("type", {}).get("displayName", "")
        if t == "SubstitutionOn":
            on = ev.get("minute")
        elif t == "SubstitutionOff":
            off = ev.get("minute")
    if player.get("isFirstEleven"):
        start, end = 0, (off if off is not None else max_minute)
    else:
        if on is None:
            return 0
        start, end = on, (off if off is not None else max_minute)
    return max(0, (end if end is not None else max_minute) - start)


def _quals(ev):
    return {q.get("type", {}).get("displayName", "") for q in ev.get("qualifiers", [])}


def aggregate_players(matches):
    """Aggregate Barcelona player season stats + per-player shot lists."""
    files = {os.path.basename(f).split("_")[1]: f
             for f in glob.glob(os.path.join(DATA_DIR, "match_*_cache.json"))}

    players = {}        # name -> aggregate dict
    pshots  = {}        # name -> list of shot dicts (for Player Lab)

    def rec(name, pos):
        e = players.get(name)
        if e is None:
            e = players[name] = {
                "name": name, "pos": pos, "apps": 0, "starts": 0, "mins": 0,
                "goals": 0, "assists": 0, "shots": 0, "sot": 0, "keyp": 0,
                "passes": 0, "pacc_num": 0, "drib": 0, "tackles": 0, "intc": 0, "prog": 0,
                "aerials": 0, "touches": 0, "fouls": 0, "yellow": 0, "red": 0,
                "rating_sum": 0.0, "rating_n": 0, "xg": 0.0,
            }
        return e

    for m in matches:
        f = files.get(m["mid"])
        if not f:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        max_minute = d.get("maxMinute") or 90
        side = "home" if m["bcn_is_home"] else "away"
        team = d.get(side, {})
        team_id = team.get("teamId")
        team_name = team.get("name", "Barcelona")
        pid2name = {p.get("playerId"): p.get("name") for p in team.get("players", [])}

        # --- per-shot xG (geometry model) attributed by player name ---
        xg_by_name = {}
        try:
            sdf = bw._build_shot_df(d, team_name) if bw._build_shot_df else None
        except Exception:
            sdf = None
        if sdf is not None and len(sdf):
            for r in sdf.to_dict("records"):
                nm = r.get("full_name") or r.get("player")
                if not nm:
                    continue
                xg_by_name[nm] = xg_by_name.get(nm, 0.0) + float(r.get("xG", 0) or 0)
                pshots.setdefault(nm, []).append({
                    "x": round(float(r.get("x", 0) or 0), 2),
                    "y": round(float(r.get("y", 0) or 0), 2),
                    "xg": round(float(r.get("xG", 0) or 0), 3),
                    "goal": bool(r.get("is_goal")),
                    "ot": bool(r.get("is_on_target")),
                    "min": int(r.get("minute", 0) or 0),
                    "sit": r.get("situation", ""),
                    "body": r.get("body_part", ""),
                    "big": bool(r.get("big_chance")),
                    "opp": m["opp_name"], "date": m["date"], "mid": m["mid"],
                })

        # --- goals / assists / cards / progressive passes from the event stream ---
        goals_by, assist_by, yel_by, red_by, prog_by = {}, {}, {}, {}, {}
        for ev in d.get("events", []):
            if ev.get("teamId") != team_id:
                continue
            pid = ev.get("playerId")
            nm = pid2name.get(pid)
            if not nm:
                continue
            etype = ev.get("type", {}).get("displayName", "")
            qs = _quals(ev)
            if etype == "Goal" and "OwnGoal" not in qs:
                goals_by[nm] = goals_by.get(nm, 0) + 1
            if "IntentionalGoalAssist" in qs:
                assist_by[nm] = assist_by.get(nm, 0) + 1
            if etype == "Card":
                if "Red" in qs or "SecondYellow" in qs:
                    red_by[nm] = red_by.get(nm, 0) + 1
                elif "Yellow" in qs:
                    yel_by[nm] = yel_by.get(nm, 0) + 1
            ex_ok = etype == "Pass" and ev.get("outcomeType", {}).get("displayName") == "Successful"
            if ex_ok:
                x = ev.get("x", 0) or 0
                ex = None
                for q in ev.get("qualifiers", []):
                    if q.get("type", {}).get("displayName") == "PassEndX":
                        try:
                            ex = float(q.get("value"))
                        except (TypeError, ValueError):
                            ex = None
                        break
                if ex is None:
                    ex = ev.get("endX", x) or x
                if (ex - x) >= 15 and ex >= 50:
                    prog_by[nm] = prog_by.get(nm, 0) + 1

        # --- stat-sheet aggregation ---
        for p in team.get("players", []):
            st = p.get("stats", {})
            if not st:
                continue
            nm = p.get("name")
            e = rec(nm, p.get("position", ""))
            e["apps"] += 1
            if p.get("isFirstEleven"):
                e["starts"] += 1
            e["mins"]    += _player_minutes(d, p, max_minute)
            e["shots"]   += _sumdict(st, "shotsTotal")
            e["sot"]     += _sumdict(st, "shotsOnTarget")
            e["keyp"]    += _sumdict(st, "passesKey")
            e["passes"]  += _sumdict(st, "passesTotal")
            e["pacc_num"]+= _sumdict(st, "passesAccurate")
            e["drib"]    += _sumdict(st, "dribblesWon")
            e["tackles"] += _sumdict(st, "tacklesTotal")
            e["intc"]    += _sumdict(st, "interceptions")
            e["aerials"] += _sumdict(st, "aerialsWon")
            e["touches"] += _sumdict(st, "touches")
            e["fouls"]   += _sumdict(st, "foulsCommited")
            fr = _final_rating(st)
            if fr:
                e["rating_sum"] += fr
                e["rating_n"]   += 1
            e["goals"]   += goals_by.get(nm, 0)
            e["assists"] += assist_by.get(nm, 0)
            e["prog"]    += prog_by.get(nm, 0)
            e["yellow"]  += yel_by.get(nm, 0)
            e["red"]     += red_by.get(nm, 0)
            e["xg"]      += xg_by_name.get(nm, 0.0)

    # finalise derived fields
    out = []
    for e in players.values():
        apps = e["apps"] or 1
        rating = round(e["rating_sum"] / e["rating_n"], 2) if e["rating_n"] else 0
        pacc = round(100 * e["pacc_num"] / e["passes"]) if e["passes"] else 0
        out.append({
            "name": e["name"], "pos": e["pos"], "apps": e["apps"], "starts": e["starts"],
            "mins": e["mins"], "goals": e["goals"], "assists": e["assists"],
            "ga": e["goals"] + e["assists"], "shots": e["shots"], "sot": e["sot"],
            "keyp": e["keyp"], "passes": e["passes"], "pacc": pacc, "drib": e["drib"],
            "tackles": e["tackles"], "intc": e["intc"], "aerials": e["aerials"], "prog": e["prog"],
            "touches": e["touches"], "fouls": e["fouls"], "yellow": e["yellow"],
            "red": e["red"], "rating": rating,
            "xg": round(e["xg"], 2), "xgd": round(e["goals"] - e["xg"], 2),
        })
    out.sort(key=lambda p: (-p["ga"], -p["goals"], -p["rating"]))
    # round shot xg lists already done
    return out, pshots


# ---------------------------------------------------------------------------
# PER-PLAYER EVENT LOCATIONS  (for the Player Lab match-centre-style graphs)
# ---------------------------------------------------------------------------
def aggregate_player_events(matches):
    """For each Barcelona player, collect season event locations (raw WhoScored
    0-100 coords) so the Player Lab can draw the same graphs as the match centre:
      shots    -> [x, y, gy, xg, goal, ontarget]
      dribbles -> [x, y, ex, ey, ok]     (ex/ey = next touch; -1 if none)
      tackles  -> [x, y, ok]
      passes   -> [x, y, ex, ey, ok, prog]
    """
    files = {os.path.basename(f).split("_")[1]: f
             for f in glob.glob(os.path.join(DATA_DIR, "match_*_cache.json"))}
    ev = {}
    games = []          # index -> [opponent, date]
    game_idx = {}       # mid -> index

    def rec(nm):
        e = ev.get(nm)
        if e is None:
            e = ev[nm] = {"shots": [], "dribbles": [], "tackles": [], "passes": []}
        return e

    def ri(v):
        return int(round(v or 0))

    for m in matches:
        f = files.get(m["mid"])
        if not f:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        mid = m["mid"]
        if mid not in game_idx:
            game_idx[mid] = len(games)
            # [opponent, date, season] — season lets the client filter events per season
            games.append([m["opp_name"], m["date"], season_of(m["date"])])
        gi = game_idx[mid]
        side = "home" if m["bcn_is_home"] else "away"
        team = d.get(side, {})
        tid = team.get("teamId"); tname = team.get("name", "")
        pid2name = {p.get("playerId"): p.get("name") for p in team.get("players", [])}
        events = d.get("events", [])

        # shots (+ model xG, zipped in event order)
        raw_sh = [e for e in events if e.get("teamId") == tid
                  and e.get("type", {}).get("displayName", "") in _SHOT_TYPES]
        try:
            df = bw._build_shot_df(d, tname) if bw._build_shot_df else None
            xrows = df.to_dict("records") if df is not None else []
        except Exception:
            xrows = []
        for i, e in enumerate(raw_sh):
            nm = pid2name.get(e.get("playerId"))
            if not nm:
                continue
            qs = _qset(e)
            et = e.get("type", {}).get("displayName", "")
            xg = round(float(xrows[i].get("xG", 0) or 0), 3) if (len(xrows) == len(raw_sh) and i < len(xrows)) else 0.05
            goal = 1 if (et == "Goal" and "OwnGoal" not in qs) else 0
            ot = 1 if (et in ("Goal", "SavedShot") and "Blocked" not in qs) else 0
            gy = _qval(e, "GoalMouthY")
            rec(nm)["shots"].append([ri(e.get("x")), ri(e.get("y")),
                                     ri(gy) if gy is not None else 50, xg, goal, ot,
                                     e.get("minute") or 0, gi])

        # per-player on-ball timeline (for dribble carry direction)
        touches = {}
        for e in events:
            if e.get("teamId") != tid:
                continue
            t = e.get("type", {}).get("displayName", "")
            if t == "Pass" or t == "TakeOn" or t in _SHOT_TYPES:
                nm = pid2name.get(e.get("playerId"))
                if nm:
                    tt = (e.get("minute") or 0) * 60 + (e.get("second") or 0)
                    touches.setdefault(nm, []).append((tt, e.get("x") or 0, e.get("y") or 0))
        for nm in touches:
            touches[nm].sort()

        for e in events:
            if e.get("teamId") != tid:
                continue
            t = e.get("type", {}).get("displayName", "")
            nm = pid2name.get(e.get("playerId"))
            if not nm:
                continue
            ok = e.get("outcomeType", {}).get("displayName") == "Successful"
            x = e.get("x") or 0; y = e.get("y") or 0
            if t == "TakeOn":
                tt = (e.get("minute") or 0) * 60 + (e.get("second") or 0)
                exy = (-1, -1)
                for (t2, x2, y2) in touches.get(nm, []):
                    if t2 > tt and t2 - tt <= 8 and (abs(x2 - x) > 0.8 or abs(y2 - y) > 0.8):
                        exy = (ri(x2), ri(y2)); break
                rec(nm)["dribbles"].append([ri(x), ri(y), exy[0], exy[1], 1 if ok else 0, e.get("minute") or 0, gi])
            elif t == "Tackle":
                rec(nm)["tackles"].append([ri(x), ri(y), 1 if ok else 0, e.get("minute") or 0, gi])
            elif t == "Pass":
                exq = _qval(e, "PassEndX"); eyq = _qval(e, "PassEndY")
                ex = exq if exq is not None else (e.get("endX") or x)
                ey = eyq if eyq is not None else (e.get("endY") or y)
                prog = 1 if (ok and (ex - x) >= 15 and ex >= 50) else 0
                rec(nm)["passes"].append([ri(x), ri(y), ri(ex), ri(ey), 1 if ok else 0, prog, e.get("minute") or 0, gi])

    ev["_games"] = games
    return ev


# ---------------------------------------------------------------------------
# SEASON / COMPETITION AGGREGATES
# ---------------------------------------------------------------------------
def _season_totals(matches):
    n = len(matches)
    w = sum(1 for m in matches if m["result"] == "W")
    d = sum(1 for m in matches if m["result"] == "D")
    l = sum(1 for m in matches if m["result"] == "L")
    gf = sum(m["bcn_goals"] for m in matches)
    ga = sum(m["opp_goals"] for m in matches)
    n_xg = sum(1 for m in matches if m["bcn_xg"])
    return {
        "p": n, "w": w, "d": d, "l": l, "gf": gf, "ga": ga, "gd": gf - ga,
        "cs": sum(1 for m in matches if m["opp_goals"] == 0),
        "fs": sum(1 for m in matches if m["bcn_goals"] == 0),
        "xgf": round(sum(m["bcn_xg"] for m in matches), 1),
        "xga": round(sum(m["opp_xg"] for m in matches), 1),
        "avg_xg": round(sum(m["bcn_xg"] for m in matches if m["bcn_xg"]) / max(n_xg, 1), 2),
        "ppg": round((3 * w + d) / n, 2) if n else 0,
        "win_pct": round(100 * w / n) if n else 0,
    }


def _season_by_comp(matches):
    comps = {}
    for m in matches:
        c = comps.setdefault(m["comp"], {"comp": m["comp"], "p": 0, "w": 0, "d": 0,
                                         "l": 0, "gf": 0, "ga": 0})
        c["p"] += 1
        c["w"] += m["result"] == "W"
        c["d"] += m["result"] == "D"
        c["l"] += m["result"] == "L"
        c["gf"] += m["bcn_goals"]
        c["ga"] += m["opp_goals"]
    order = {"La Liga": 0, "UCL": 1, "Copa": 2, "Supercopa": 3}
    by_comp = sorted(comps.values(), key=lambda c: order.get(c["comp"], 9))
    for c in by_comp:
        c["pts"] = 3 * c["w"] + c["d"]
        c["gd"] = c["gf"] - c["ga"]
    return by_comp


def build_data(matches):
    # Seasons present in the data, plus the upcoming one so the UI can offer 2026/27
    # even before any fixture data exists for it.
    data_seasons = sorted({m["season"] for m in matches if m.get("season")})
    upcoming = next_season(data_seasons[-1]) if data_seasons else ""
    season_keys = list(data_seasons)
    if upcoming and upcoming not in season_keys:
        season_keys.append(upcoming)

    # Per-season totals / competition table / player aggregates, plus a combined
    # 'all'. Player shots stay a single global dict — each shot carries its date, so
    # the client filters them by season without duplicating this data.
    players_all, pshots = aggregate_players(matches)
    seasons = {"all": {"totals": _season_totals(matches),
                       "byComp": _season_by_comp(matches),
                       "players": players_all}}
    for s in season_keys:
        sub = [m for m in matches if m.get("season") == s]
        players_s, _ = aggregate_players(sub)
        seasons[s] = {"totals": _season_totals(sub),
                      "byComp": _season_by_comp(sub),
                      "players": players_s}

    # slim per-match records for the app (now carrying the season tag)
    keep = ("mid", "date", "season", "comp", "home", "away", "home_score", "away_score",
            "bcn_is_home", "opp_name", "bcn_goals", "opp_goals", "result",
            "bcn_xg", "opp_xg", "xg_h", "xg_a", "xg_source", "venue", "referee",
            "attendance", "h_shots", "a_shots", "h_sot", "a_sot", "h_poss", "a_poss",
            "h_bcc", "a_bcc", "h_bcm", "a_bcm", "h_duel", "a_duel", "h_saves",
            "a_saves", "h_fouls", "a_fouls", "h_pacc_pct", "a_pacc_pct")
    match_recs = []
    for m in matches:
        rec = {k: m.get(k) for k in keep}
        rec["home_logo"] = team_logo(m["home"])
        rec["away_logo"] = team_logo(m["away"])
        match_recs.append(rec)

    season_labels = {s: s for s in season_keys}
    season_labels["all"] = "All seasons"

    return {
        "team": "FC Barcelona",
        # Default to the latest season that actually has data (2025/26 for now).
        "defaultSeason": data_seasons[-1] if data_seasons else "all",
        "seasonList": season_keys + ["all"],
        "seasonLabels": season_labels,
        "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "bcnLogo": team_logo("Barcelona"),
        "seasons": seasons,
        "matches": match_recs,
        "playerShots": pshots,
    }


# ---------------------------------------------------------------------------
# SVG MATCH PAGE  (WC2026 style — no PNGs, no Plotly)
# ---------------------------------------------------------------------------
def _match_shots(d, team_name, mirror):
    try:
        df = bw._build_shot_df(d, team_name) if bw._build_shot_df else None
    except Exception:
        df = None
    out = []
    if df is not None and len(df):
        for r in df.to_dict("records"):
            x = float(r.get("x", 0) or 0); y = float(r.get("y", 0) or 0)
            if mirror:
                x = 120 - x; y = 80 - y
            out.append({
                "x": x, "y": y, "xg": float(r.get("xG", 0) or 0),
                "goal": bool(r.get("is_goal")), "ot": bool(r.get("is_on_target")),
                "min": int(r.get("minute", 0) or 0),
                "player": r.get("full_name") or r.get("player") or "",
                "sit": r.get("situation", ""),
            })
    return out


def _pitch_svg(home_shots, away_shots, hn, an):
    """Full horizontal pitch. Home attacks right, away (mirrored) attacks left."""
    W, H, pad = 900, 560, 12
    pw, ph = W - pad * 2, H - pad * 2
    def px(x): return pad + max(0, min(120, x)) / 120 * pw
    def py(y): return pad + max(0, min(80, y)) / 80 * ph
    s = ['<svg viewBox="0 0 %d %d" width="100%%" style="display:block">' % (W, H)]
    s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" fill="#101a2e" stroke="%s"/>' % (pad, pad, pw, ph, LINE))
    s.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s"/>' % (px(60), py(0), px(60), py(80), LINE))
    s.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s"/>' % (px(60), py(40), 9.15 / 120 * pw, LINE))
    for bx0, bx1 in [(102, 120), (0, 18)]:
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="%s"/>' % (px(bx0), py(18), abs(px(bx1) - px(bx0)), py(62) - py(18), LINE))
    for gx0, gx1 in [(114, 120), (0, 6)]:
        s.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="none" stroke="%s"/>' % (px(gx0), py(30), abs(px(gx1) - px(gx0)), py(50) - py(30), LINE))
    def dot(sh):
        col = "#ff3d8b" if sh["goal"] else (BLUE if sh["ot"] else "#7e8bb0")
        r = 4 + (sh["xg"] ** 0.5) * 16
        tip = "%s %d' - xG %.2f%s%s" % (sh["player"], sh["min"], sh["xg"],
              " - GOAL" if sh["goal"] else "", (" - " + sh["sit"]) if sh["sit"] else "")
        return ('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" fill-opacity="0.72" stroke="#0b0f1a" stroke-width="1">'
                '<title>%s</title></circle>') % (px(sh["x"]), py(sh["y"]), r, col, bw_escape(tip))
    for sh in away_shots:
        s.append(dot(sh))
    for sh in home_shots:
        s.append(dot(sh))
    s.append("</svg>")
    return "".join(s)


def bw_escape(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _sc_row(hv, av, label):
    try:
        h = float(str(hv).replace("%", "")); a = float(str(av).replace("%", ""))
        t = (h + a) or 1; hp = round(100 * h / t); ap = 100 - hp
    except Exception:
        hp = ap = 50; h = a = 0
    win_h = " win" if h >= a else ""; win_a = " win" if a > h else ""
    return ('<div class="stat-cmp"><div class="sc-val%s">%s</div>'
            '<div><div class="sc-label">%s</div><div class="sc-bar">'
            '<div class="sc-fill h" style="width:%d%%"></div><div class="sc-fill a" style="width:%d%%"></div>'
            '</div></div><div class="sc-val%s">%s</div></div>') % (win_h, hv, label, hp, ap, win_a, av)


def _ratings_list(d, side, color):
    players = sorted(d.get(side, {}).get("players", []),
                     key=lambda p: (0 if p.get("isFirstEleven") else 1))
    rows = []
    for p in players:
        st = p.get("stats", {})
        if not st:
            continue
        r = _final_rating(st)
        mins = _player_minutes(d, p, d.get("maxMinute") or 90)
        if not r and not mins:
            continue
        rows.append('<div class="fin-row"><div class="nm"><span>%s</span></div>'
                    '<div class="fin-stat"><span class="sub">%d\'</span>'
                    '<span class="lb-val" style="color:%s">%s</span></div></div>'
                    % (bw_escape(p.get("name", "")), mins, color, ("%.2f" % r) if r else "-"))
    return "".join(rows)


def build_match_svg(m, d, prev_mid, next_mid):
    hn, an = m["home"], m["away"]
    hs, aws = m["home_score"], m["away_score"]
    is_home = m["bcn_is_home"]
    h_logo, a_logo = team_logo(hn), team_logo(an)
    h_col = ACC if is_home else MUTED
    a_col = ACC if not is_home else MUTED
    res_col = {"W": ACC, "D": WARN, "L": BAD}[m["result"]]

    home_shots = _match_shots(d, hn, mirror=False)
    away_shots = _match_shots(d, an, mirror=True)
    h_xg = m["xg_h"]; a_xg = m["xg_a"]
    xg_lbl = "xG" if m.get("xg_source") == "Understat" else "xG (est.)"

    stats = (
        _sc_row("%.2f" % h_xg, "%.2f" % a_xg, xg_lbl) +
        _sc_row(str(m["h_poss"]) + "%", str(m["a_poss"]) + "%", "Possession") +
        _sc_row(m["h_sot"], m["a_sot"], "Shots on Target") +
        _sc_row(m["h_shots"], m["a_shots"], "Shots") +
        _sc_row(m["h_bcc"], m["a_bcc"], "Big Chances") +
        _sc_row(str(m["h_pacc_pct"]) + "%", str(m["a_pacc_pct"]) + "%", "Pass Accuracy") +
        _sc_row(m["h_duel"], m["a_duel"], "Duels Won") +
        _sc_row(m["h_saves"], m["a_saves"], "Saves") +
        _sc_row(m["h_fouls"], m["a_fouls"], "Fouls")
    )

    def badge_img(logo, col):
        return ('<img src="%s" alt="" style="width:44px;height:44px;object-fit:contain">' % logo) if logo else \
               ('<div style="width:44px;height:44px;border-radius:50%%;background:%s;opacity:.4"></div>' % col)

    comp_lbl = {"UCL": "Champions League", "Copa": "Copa del Rey"}.get(m["comp"], m["comp"])
    venue = m.get("venue", ""); ref = m.get("referee", "")
    meta = " &middot; ".join([x for x in [comp_lbl, m["date"], venue, ("Ref: " + ref) if ref else ""] if x])

    prev_a = ('<a href="match_%s.html">&larr; Prev</a>' % prev_mid) if prev_mid else "<span></span>"
    next_a = ('<a href="match_%s.html">Next &rarr;</a>' % next_mid) if next_mid else "<span></span>"

    return (
"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + bw_escape("%s %d-%d %s" % (hn, hs, aws, an)) + """ | FC Barcelona</title>
<link rel="stylesheet" href="styles.css">
<style>
.mhdr{max-width:1180px;margin:0 auto;padding:26px 20px 6px}
.mscore{display:flex;align-items:center;justify-content:center;gap:26px;margin:6px 0}
.mteam{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:150px}
.mteam .nm{font-size:17px;font-weight:800;text-align:center}
.mbig{font-size:46px;font-weight:800;letter-spacing:-1px;font-variant-numeric:tabular-nums}
.mmeta{text-align:center;color:var(--muted);font-size:12.5px;margin-top:6px}
.mnav{max-width:1180px;margin:0 auto;padding:10px 20px;display:flex;justify-content:space-between;font-size:13px}
.mnav a{color:var(--muted)} .mnav a:hover{color:var(--accent)}
.legend-dot{display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:12px;color:var(--muted)}
.legend-dot i{width:11px;height:11px;border-radius:50%}
</style></head><body>
<header class="site"><div class="header-inner"><div class="brand">
  <div class="title">FC <span>Barcelona</span> &middot; Match Centre</div>
  <div class="sub">""" + bw_escape(comp_lbl + " · " + m["date"]) + """</div></div>
  <nav class="tabs"><a href="index.html"><button>&larr; Back to Dashboard</button></a></nav>
</div></header>
<div class="mnav">""" + prev_a + "<span></span>" + next_a + """</div>
<main>
<div class="mhdr">
  <div class="mscore">
    <div class="mteam">""" + badge_img(h_logo, h_col) + '<span class="nm" style="color:' + h_col + '">' + bw_escape(hn) + """</span></div>
    <div style="text-align:center"><div class="mbig">""" + ("%d &ndash; %d" % (hs, aws)) + """</div>
      <span class="badge badge-""" + m["result"] + '" style="font-size:12px">' + m["result"] + """</span></div>
    <div class="mteam">""" + badge_img(a_logo, a_col) + '<span class="nm" style="color:' + a_col + '">' + bw_escape(an) + """</span></div>
  </div>
  <div class="mmeta">""" + meta + """</div>
</div>

<div class="section-head" style="max-width:760px;margin:22px auto 10px"><h2 style="text-align:center;font-size:16px">Match stats</h2></div>
<div class="card" style="max-width:760px;margin:0 auto">""" + stats + """</div>

<div class="section-head" style="margin-top:30px"><h2>Shot map</h2>
  <p>Every shot this match, sized by xG. """ + bw_escape(hn) + """ attacks &rarr;, """ + bw_escape(an) + """ &larr;.
  <span style="color:#ff3d8b;font-weight:700">Goals pink</span>,
  <span style="color:#4ea1ff;font-weight:700">on-target blue</span>, off-target grey. Hover a dot for details.</p></div>
<div class="card">""" + _pitch_svg(home_shots, away_shots, hn, an) + """
  <div style="margin-top:12px">
    <span class="legend-dot"><i style="background:#ff3d8b"></i>Goal</span>
    <span class="legend-dot"><i style="background:#4ea1ff"></i>On target</span>
    <span class="legend-dot"><i style="background:#7e8bb0"></i>Off target</span>
    <span class="legend-dot">Total: """ + bw_escape("%s %.2f xG (%d shots)  ·  %s %.2f xG (%d shots)" % (hn, h_xg, len(home_shots), an, a_xg, len(away_shots))) + """</span>
  </div>
</div>

<div class="section-head" style="margin-top:30px"><h2>Player ratings</h2>
  <p>Average match rating and minutes for every player who featured.</p></div>
<div class="grid-2">
  <div class="card"><h3 style="color:""" + h_col + '">' + bw_escape(hn) + "</h3>" + (_ratings_list(d, "home", h_col) or '<p class="hint">No player data.</p>') + """</div>
  <div class="card"><h3 style="color:""" + a_col + '">' + bw_escape(an) + "</h3>" + (_ratings_list(d, "away", a_col) or '<p class="hint">No player data.</p>') + """</div>
</div>
<div class="footer-note">FC Barcelona 2025/26 &middot; Match """ + str(m["mid"]) + """ &middot; WhoScored + Understat</div>
</main></body></html>""")


# ---------------------------------------------------------------------------
# MATCH CENTRE DETAIL  (window.MATCH_DETAIL for the ported WC2026 match.js)
# ---------------------------------------------------------------------------
MC_LOGO_DST = os.path.join(HTML_DIR, "mclogos")
BARCA_COL, OPP_COL = "#e0224e", "#4ea1ff"
_SHOT_TYPES = {"Goal", "MissedShots", "SavedShot", "ShotOnPost"}


def _qset(ev):
    return {q.get("type", {}).get("displayName", "") for q in ev.get("qualifiers", [])}


def _qval(ev, name):
    for q in ev.get("qualifiers", []):
        if q.get("type", {}).get("displayName") == name:
            v = q.get("value")
            try:
                return float(v)
            except (TypeError, ValueError):
                return v
    return None


def mc_logo(name):
    """Ensure assets/html/mclogos/<name>.png exists (match.js expects name-keyed files)."""
    rel = team_logo(name)              # copies into logos/<slug>.png and returns that path
    if not rel:
        return
    os.makedirs(MC_LOGO_DST, exist_ok=True)
    dst = os.path.join(MC_LOGO_DST, name + ".png")
    if not os.path.exists(dst):
        try:
            shutil.copyfile(os.path.join(HTML_DIR, rel), dst)
        except Exception:
            pass


def build_match_detail(m, d):
    hid = d.get("home", {}).get("teamId")
    aid = d.get("away", {}).get("teamId")
    pid2name = {}
    for side in ("home", "away"):
        for p in d.get(side, {}).get("players", []):
            pid2name[p.get("playerId")] = p.get("name")
    for k, v in (d.get("playerIdNameDictionary") or {}).items():
        try:
            pid2name.setdefault(int(k), v)
        except (TypeError, ValueError):
            pass
    maxmin = d.get("maxMinute") or 90
    events = d.get("events", [])

    def sd(tid):
        return "home" if tid == hid else ("away" if tid == aid else None)

    # ---- per-player goals / assists / cards / sub minutes (both teams) ----
    goals_by, assist_by, yc_by, rc_by, subon = {}, {}, {}, {}, {}
    for ev in events:
        pid = ev.get("playerId")
        et = ev.get("type", {}).get("displayName", "")
        qs = _qset(ev)
        if et == "Goal" and "OwnGoal" not in qs:
            goals_by[pid] = goals_by.get(pid, 0) + 1
        if "IntentionalGoalAssist" in qs:
            assist_by[pid] = assist_by.get(pid, 0) + 1
        if et == "Card":
            if "Red" in qs or "SecondYellow" in qs:
                rc_by[pid] = rc_by.get(pid, 0) + 1
            elif "Yellow" in qs:
                yc_by[pid] = yc_by.get(pid, 0) + 1
        if et == "SubstitutionOn":
            subon[pid] = ev.get("minute")

    # ---- shots (raw WhoScored coords 0-100) + model xG ----
    def raw_shots(side_key, team_id, team_name):
        rs = []
        for ev in events:
            if ev.get("teamId") != team_id:
                continue
            et = ev.get("type", {}).get("displayName", "")
            if et not in _SHOT_TYPES:
                continue
            qs = _qset(ev)
            blocked = "Blocked" in qs
            goal = et == "Goal" and "OwnGoal" not in qs
            ot = (et in ("Goal", "SavedShot")) and not blocked
            rs.append({
                "team": side_key, "x": round(ev.get("x", 0) or 0, 1), "y": round(ev.get("y", 0) or 0, 1),
                "min": ev.get("minute"), "sec": ev.get("second"),
                "player": pid2name.get(ev.get("playerId"), ""),
                "goal": goal, "onTarget": bool(ot), "blocked": blocked,
                "big": "BigChance" in qs,
                "gy": _qval(ev, "GoalMouthY"), "gz": _qval(ev, "GoalMouthZ"), "xg": 0.05,
            })
        # attach model xG in event order (build_shot_df iterates events in the same order)
        try:
            df = bw._build_shot_df(d, team_name) if bw._build_shot_df else None
            rows = df.to_dict("records") if df is not None else []
        except Exception:
            rows = []
        if len(rows) == len(rs):
            for r, srow in zip(rs, rows):
                r["xg"] = round(float(srow.get("xG", 0) or 0), 3)
        else:
            used = [False] * len(rows)
            for r in rs:
                for i, srow in enumerate(rows):
                    if not used[i] and srow.get("minute") == r["min"]:
                        r["xg"] = round(float(srow.get("xG", 0) or 0), 3)
                        used[i] = True
                        break
        return rs

    shots = raw_shots("home", hid, d["home"]["name"]) + raw_shots("away", aid, d["away"]["name"])

    # ---- passes ----
    passes = []
    n = len(events)
    for i, ev in enumerate(events):
        if ev.get("type", {}).get("displayName") != "Pass":
            continue
        side = sd(ev.get("teamId"))
        if not side:
            continue
        ok = ev.get("outcomeType", {}).get("displayName") == "Successful"
        qs = _qset(ev)
        x = round(ev.get("x", 0) or 0, 1); y = round(ev.get("y", 0) or 0, 1)
        ex = _qval(ev, "PassEndX"); ey = _qval(ev, "PassEndY")
        ex = round(ex, 1) if ex is not None else round(ev.get("endX", x) or x, 1)
        ey = round(ey, 1) if ey is not None else round(ev.get("endY", y) or y, 1)
        recv = ""
        if ok:
            for j in range(i + 1, min(i + 4, n)):
                ne = events[j]
                if ne.get("teamId") == ev.get("teamId") and ne.get("playerId"):
                    recv = pid2name.get(ne.get("playerId"), ""); break
        passes.append({
            "team": side, "player": pid2name.get(ev.get("playerId"), ""), "recv": recv,
            "ok": ok, "x": x, "y": y, "ex": ex, "ey": ey,
            "min": ev.get("minute"), "sec": ev.get("second"),
            "prog": bool(ok and (ex - x) >= 15 and ex >= 50),
            "key": "KeyPass" in qs, "assist": "IntentionalGoalAssist" in qs, "cross": "Cross" in qs,
        })

    # ---- dribbles (take-ons) ----
    dribbles = []
    for ev in events:
        if ev.get("type", {}).get("displayName") != "TakeOn":
            continue
        side = sd(ev.get("teamId"))
        if not side:
            continue
        dribbles.append({
            "team": side, "player": pid2name.get(ev.get("playerId"), ""),
            "x": round(ev.get("x", 0) or 0, 1), "y": round(ev.get("y", 0) or 0, 1),
            "ok": ev.get("outcomeType", {}).get("displayName") == "Successful",
            "min": ev.get("minute"), "sec": ev.get("second"),
        })

    # ---- goals ----
    goals = []
    for i, ev in enumerate(events):
        if ev.get("type", {}).get("displayName") != "Goal":
            continue
        side = sd(ev.get("teamId"))
        qs = _qset(ev)
        own = "OwnGoal" in qs
        gteam = side if not own else ("away" if side == "home" else "home")
        assist = ""
        for j in range(max(0, i - 4), i):
            pe = events[j]
            if pe.get("teamId") == ev.get("teamId") and "IntentionalGoalAssist" in _qset(pe):
                assist = pid2name.get(pe.get("playerId"), ""); break
        goals.append({
            "team": gteam, "min": ev.get("minute"), "scorer": pid2name.get(ev.get("playerId"), ""),
            "assist": assist, "pen": "Penalty" in qs, "own": own,
        })

    # ---- saves ----
    saves = []
    for ev in events:
        if ev.get("type", {}).get("displayName") != "Save":
            continue
        side = sd(ev.get("teamId"))
        if not side:
            continue
        saves.append({"team": side, "min": ev.get("minute"), "sec": ev.get("second"),
                      "x": round(ev.get("x", 0) or 0, 1), "y": round(ev.get("y", 0) or 0, 1)})

    # ---- line-ups ----
    def lineup(side_key):
        starters, subs = [], []
        for p in d.get(side_key, {}).get("players", []):
            st = p.get("stats", {})
            mins = _player_minutes(d, p, maxmin)
            if not st and not mins and not p.get("isFirstEleven"):
                continue
            r = _final_rating(st)
            pid = p.get("playerId")
            rec = {
                "name": p.get("name"), "num": p.get("shirtNo"), "pos": p.get("position", ""),
                "mins": mins, "rating": round(r, 1) if r else None,
                "g": goals_by.get(pid, 0), "a": assist_by.get(pid, 0),
                "yc": yc_by.get(pid, 0), "rc": rc_by.get(pid, 0),
                "motm": bool(p.get("isManOfTheMatch")),
            }
            if p.get("isFirstEleven"):
                starters.append(rec)
            else:
                rec["on"] = subon.get(pid)
                subs.append(rec)
        subs.sort(key=lambda x: (x.get("on") is None, x.get("on") or 0))
        return {"starters": starters, "subs": subs}

    comp_lbl = {"UCL": "Champions League", "Copa": "Copa del Rey"}.get(m["comp"], m["comp"])
    hcol = BARCA_COL if m["bcn_is_home"] else OPP_COL
    acol = OPP_COL if m["bcn_is_home"] else BARCA_COL
    mc_logo(m["home"]); mc_logo(m["away"])

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
    }, "sources": ["whoscored"]}

    return {
        "id": m["mid"], "date": m["date"], "stage": comp_lbl, "venue": m.get("venue", ""),
        "maxMin": maxmin,
        "home": {"name": m["home"], "score": m["home_score"], "color": hcol},
        "away": {"name": m["away"], "score": m["away_score"], "color": acol},
        "shots": shots, "passes": passes, "dribbles": dribbles, "goals": goals,
        "saves": saves, "lineups": {"home": lineup("home"), "away": lineup("away")},
        "rec": rec,
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=== BCNProject Single-Page Dashboard Builder ===\n")
    os.makedirs(HTML_DIR, exist_ok=True)

    print("Loading match data...")
    matches = bw.load_matches()
    # One-team dashboard: keep only matches Barcelona actually played, and merge
    # competition-name variants so each competition appears once.
    NORM = {"Copa del Rey": "Copa", "Copa Del Rey": "Copa",
            "Champions League": "UCL", "UEFA Champions League": "UCL",
            "Supercopa de Espana": "Supercopa", "Supercopa de España": "Supercopa"}
    matches = [m for m in matches
               if "barcelona" in (m["home"] + " " + m["away"]).lower()]
    for m in matches:
        m["comp"] = NORM.get(m["comp"], m["comp"])
        # "Riyadh Air Metropolitano" (Atletico's sponsored ground) falsely trips the
        # Saudi-venue Supercopa rule — it is a domestic fixture, not the Supercopa.
        if m["comp"] == "Supercopa" and "metropolitano" in str(m.get("venue", "")).lower():
            m["comp"] = "La Liga"
    # Per-match competition overrides (mid -> competition). Fill this in to pin any
    # match to its official competition and hit the exact 38/10/4/2 breakdown. Real
    # Oviedo and Elche are La Liga clubs this season, so only their cup meeting should
    # be "Copa"; everything else keyed here wins over the auto-classifier.
    COMP_OVERRIDE = {
        # "1913936": "Copa",   # example: pin a specific match to a competition
    }
    # Real Oviedo and Elche are La Liga clubs this season; the name-based Copa rule
    # wrongly tags their league games as cup ties. Treat them as La Liga unless
    # explicitly overridden above.
    LALIGA_CLUBS = {"real oviedo", "elche"}
    for m in matches:
        if m["comp"] == "Copa" and m["opp_name"].lower() in LALIGA_CLUBS:
            m["comp"] = "La Liga"
        if m["mid"] in COMP_OVERRIDE:
            m["comp"] = COMP_OVERRIDE[m["mid"]]
    # Tag every match with the season it belongs to (Jul->Jun). New 2026/27 caches
    # dropped into assets/data are picked up here automatically.
    for m in matches:
        m["season"] = season_of(m["date"])
    print(f"  {len(matches)} Barcelona matches loaded")
    _scount = {}
    for m in matches:
        _scount[m["season"]] = _scount.get(m["season"], 0) + 1
    print(f"  seasons: {_scount}")

    print("Aggregating season + players...")
    data = build_data(matches)
    _def = data["defaultSeason"]
    print(f"  seasons: {data['seasonList']} (default {_def})")
    print(f"  {len(data['seasons'][_def]['players'])} players, "
          f"{len(data['seasons'][_def]['byComp'])} competitions in {_def}")

    # data.js
    out = os.path.join(HTML_DIR, "data.js")
    with open(out, "w", encoding="utf-8") as f:
        f.write("window.DATA = ")
        # ensure_ascii=True keeps data.js pure-ASCII (\uXXXX escapes) so it parses
        # correctly regardless of the charset the static server advertises.
        json.dump(data, f, ensure_ascii=True, separators=(",", ":"))
        f.write(";\n")
    print(f"  data.js  ({os.path.getsize(out)//1024}KB)")

    # per-player event locations (separate file — only the Player Lab needs it)
    pevents = aggregate_player_events(matches)
    pe_out = os.path.join(HTML_DIR, "player_events.js")
    with open(pe_out, "w", encoding="utf-8") as f:
        f.write("window.PLAYER_EVENTS = ")
        json.dump(pevents, f, ensure_ascii=True, separators=(",", ":"))
        f.write(";\n")
    print(f"  player_events.js  ({os.path.getsize(pe_out)//1024}KB)")

    # Match-centre detail files (window.MATCH_DETAIL, consumed by the ported match.js)
    print("Building match-centre detail files...")
    detail_dir = os.path.join(HTML_DIR, "matches_detail")
    os.makedirs(detail_dir, exist_ok=True)
    files = {os.path.basename(f).split("_")[1]: f
             for f in glob.glob(os.path.join(DATA_DIR, "match_*_cache.json"))}
    written = 0
    for m in matches:
        f = files.get(m["mid"])
        if not f:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        try:
            detail = build_match_detail(m, d)
        except Exception as e:
            print(f"  WARN match {m['mid']}: {e}")
            continue
        with open(os.path.join(detail_dir, f"{m['mid']}.js"), "w", encoding="utf-8") as fh:
            fh.write("window.MATCH_DETAIL = ")
            json.dump(detail, fh, ensure_ascii=True, separators=(",", ":"))
            fh.write(";\n")
        written += 1
    print(f"  {written} match-centre detail files written")
    print("\nDone.  index.html + app.js + match.html + match.js are static; data regenerated.")


if __name__ == "__main__":
    main()
