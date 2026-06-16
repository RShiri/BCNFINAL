"""
BCNProject – Full Season Website Builder
Generates:
  assets/html/index.html          – Season overview, all matches
  assets/html/match_{id}.html     – Individual match dashboard (33 files)
All PNGs are embedded as base64; shot maps are inlined from existing HTML files.
"""

import base64, glob, json, os, re, sys

ROOT     = os.path.dirname(os.path.abspath(__file__))
PNG_DIR  = os.path.join(ROOT, "assets", "png")
HTML_DIR = os.path.join(ROOT, "assets", "html")
DATA_DIR = os.path.join(ROOT, "assets", "data")

# Geometry-based xG fallback (used when Understat data is unavailable)
sys.path.insert(0, ROOT)
try:
    from Projects.shotmap_whoscored import build_shot_df as _build_shot_df
except Exception:
    _build_shot_df = None


def _geometry_xg(data, team_name):
    """Sum of geometry-estimated xG for a team — fallback when no Understat."""
    if _build_shot_df is None:
        return 0.0
    try:
        df = _build_shot_df(data, team_name)
        return round(float(df["xG"].sum()), 2) if not df.empty else 0.0
    except Exception:
        return 0.0


# WhoScored's matchCentreData `stats` dict does NOT include big chances, duels,
# fouls or saves — those must be derived from the raw event stream.
_SHOT_TYPES = {"MissedShots", "SavedShot", "ShotOnPost", "Goal"}

def _event_stats(data):
    """Compute team-level stats from events. Returns (home_dict, away_dict)."""
    hid = data.get("home", {}).get("teamId")
    aid = data.get("away", {}).get("teamId")
    base = lambda: {"big_chance_created": 0, "big_chance_missed": 0,
                    "duels_won": 0, "saves": 0, "fouls": 0}
    out = {hid: base(), aid: base()}

    for ev in data.get("events", []):
        tid = ev.get("teamId")
        if tid not in out:
            continue
        etype = ev.get("type", {}).get("displayName", "")
        outcome = ev.get("outcomeType", {}).get("displayName", "")
        quals = {q.get("type", {}).get("displayName", "") for q in ev.get("qualifiers", [])}

        if "BigChanceCreated" in quals:
            out[tid]["big_chance_created"] += 1
        if "BigChance" in quals and etype in _SHOT_TYPES and etype != "Goal":
            out[tid]["big_chance_missed"] += 1
        if etype == "Save":
            out[tid]["saves"] += 1
        if etype == "Foul" and outcome == "Unsuccessful":
            out[tid]["fouls"] += 1
        # Duels won: aerials won + tackles won + take-ons won
        if etype in ("Aerial", "Tackle", "TakeOn") and outcome == "Successful":
            out[tid]["duels_won"] += 1

    return out.get(hid, base()), out.get(aid, base())

BCN_BLUE = "#004d98"
BCN_RED  = "#a50044"
BCN_GOLD = "#f5c518"
DARK_BG  = "#0d0d1a"
CARD_BG  = "#111128"
BORDER   = "#1e1e4a"

# ---------------------------------------------------------------------------
# COMPETITION DETECTION
# ---------------------------------------------------------------------------
UCL_TEAMS = {
    "chelsea", "psg", "paris saint-germain", "eintracht frankfurt",
    "club brugge", "olympiacos", "slavia prague", "copenhagen", "newcastle",
    "fc copenhagen", "sk slavia prague", "inter", "inter milan",
    "borussia dortmund", "bayern munich", "arsenal", "liverpool",
    "manchester city", "real madrid",  # could appear in UCL KO rounds
}
COPA_LOWER_TEAMS = {
    "real oviedo", "elche", "racing santander", "racing ferrol",
    "cd mirandes", "deportivo de la coruna", "sd huesca", "real valladolid",
    "fc cartagena", "burgos cf", "cd leganes", "albacete",
}
SAUDI_VENUES = {"king fahd", "king abdullah", "jeddah", "riyadh", "saudi"}


def competition(home_name, away_name, mid, data=None):
    # 1. Explicit tag written by scraper (most reliable)
    if data and data.get("_competition"):
        return data["_competition"]

    # 2. Supercopa: Saudi venue
    if data:
        venue = str(data.get("venueName", "")).lower()
        if any(v in venue for v in SAUDI_VENUES):
            return "Supercopa"

    # 3. UCL: known match-ID range or known European opponents
    if int(mid) >= 1946000:
        return "UCL"
    lo = home_name.lower() + " " + away_name.lower()
    if any(t in lo for t in UCL_TEAMS):
        return "UCL"

    # 4. Copa del Rey: lower-division opponents
    if any(t in lo for t in COPA_LOWER_TEAMS):
        return "Copa"

    return "La Liga"


# ---------------------------------------------------------------------------
# DATA HELPERS
# ---------------------------------------------------------------------------
def load_matches():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "match_*_cache.json")))
    matches = []
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
            mid  = os.path.basename(f).split("_")[1]
            home = d.get("home", {})
            away = d.get("away", {})
            hn   = home.get("name", "Home")
            an   = away.get("name", "Away")
            hs   = home.get("scores", {}).get("fulltime", 0) or 0
            aws  = away.get("scores", {}).get("fulltime", 0) or 0
            date = str(d.get("startDate", ""))[:10]
            us   = d.get("understat", {})
            xg_h = float(us.get("xG", {}).get("h", 0) or 0)
            xg_a = float(us.get("xG", {}).get("a", 0) or 0)
            # Fallback to geometry xG when Understat missing/zero
            xg_source = "Understat"
            if xg_h == 0 and xg_a == 0:
                xg_h = _geometry_xg(d, hn)
                xg_a = _geometry_xg(d, an)
                xg_source = "Model (est.)"

            # Aggregate stats
            def agg(stats, key):
                v = stats.get(key, {})
                return round(sum(v.values())) if isinstance(v, dict) else 0

            hstats = home.get("stats", {})
            astats = away.get("stats", {})
            h_shots   = agg(hstats, "shotsTotal")
            a_shots   = agg(astats, "shotsTotal")
            h_sot     = agg(hstats, "shotsOnTarget")
            a_sot     = agg(astats, "shotsOnTarget")
            h_passes  = agg(hstats, "passesTotal")
            a_passes  = agg(astats, "passesTotal")
            h_pacc    = agg(hstats, "passesAccurate")
            a_pacc    = agg(astats, "passesAccurate")
            tot_pass  = h_passes + a_passes or 1
            h_poss    = round(100 * h_passes / tot_pass)
            a_poss    = 100 - h_poss
            # Big chances / duels / saves / fouls are derived from events
            h_evs, a_evs = _event_stats(d)
            h_bcc   = h_evs["big_chance_created"]; a_bcc = a_evs["big_chance_created"]
            h_bcm   = h_evs["big_chance_missed"];  a_bcm = a_evs["big_chance_missed"]
            h_duel  = h_evs["duels_won"];          a_duel = a_evs["duels_won"]
            h_saves = h_evs["saves"];              a_saves = a_evs["saves"]
            h_fouls = h_evs["fouls"];              a_fouls = a_evs["fouls"]
            h_pacc_pct = round(100 * h_pacc / h_passes) if h_passes else 0
            a_pacc_pct = round(100 * a_pacc / a_passes) if a_passes else 0

            # Barcelona side
            bcn_is_home = "barcelona" in hn.lower()
            bcn_goals   = hs  if bcn_is_home else aws
            opp_goals   = aws if bcn_is_home else hs
            opp_name    = an  if bcn_is_home else hn
            bcn_xg      = xg_h if bcn_is_home else xg_a
            opp_xg      = xg_a if bcn_is_home else xg_h

            if bcn_goals > opp_goals:   result = "W"
            elif bcn_goals == opp_goals: result = "D"
            else:                        result = "L"

            comp = competition(hn, an, mid, data=d)

            matches.append({
                "mid": mid,
                "home": hn, "away": an,
                "home_score": hs, "away_score": aws,
                "date": date,
                "comp": comp,
                "bcn_is_home": bcn_is_home,
                "opp_name": opp_name,
                "bcn_goals": bcn_goals,
                "opp_goals": opp_goals,
                "result": result,
                "bcn_xg": bcn_xg, "opp_xg": opp_xg,
                "h_shots": h_shots, "a_shots": a_shots,
                "h_sot": h_sot, "a_sot": a_sot,
                "h_passes": h_passes, "a_passes": a_passes,
                "h_pacc": h_pacc, "a_pacc": a_pacc,
                "h_poss": h_poss, "a_poss": a_poss,
                "h_bcc": h_bcc, "a_bcc": a_bcc,
                "h_bcm": h_bcm, "a_bcm": a_bcm,
                "h_duel": h_duel, "a_duel": a_duel,
                "h_saves": h_saves, "a_saves": a_saves,
                "h_fouls": h_fouls, "a_fouls": a_fouls,
                "h_pacc_pct": h_pacc_pct, "a_pacc_pct": a_pacc_pct,
                "xg_h": xg_h, "xg_a": xg_a, "xg_source": xg_source,
                "venue": d.get("venueName", ""),
                "referee": d.get("referee", {}).get("name", "") if isinstance(d.get("referee"), dict) else str(d.get("referee", "")),
                "attendance": d.get("attendance", ""),
            })
        except Exception as e:
            print(f"  WARN {os.path.basename(f)}: {e}")
    # Sort by date
    matches.sort(key=lambda m: m["date"])
    return matches


def img_b64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def extract_plotly_body(path):
    if not os.path.exists(path):
        return "<p style='color:#666;text-align:center;padding:40px'>Shot map not yet generated.</p>"
    content = open(path, encoding="utf-8").read()
    m = re.search(r"<body[^>]*>(.*?)</body>", content, re.DOTALL)
    return m.group(1) if m else content


# ---------------------------------------------------------------------------
# SHARED CSS
# ---------------------------------------------------------------------------
SHARED_CSS = f"""
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Inter',system-ui,sans-serif;background:{DARK_BG};color:#e0e0e0;line-height:1.5}}
a{{color:inherit;text-decoration:none}}

/* NAV */
.nav{{display:flex;align-items:center;gap:20px;padding:14px 32px;
  background:#08081a;border-bottom:1px solid {BORDER};position:sticky;top:0;z-index:100}}
.nav-logo{{font-size:18px;font-weight:900;color:{BCN_GOLD};letter-spacing:-0.5px}}
.nav-logo span{{color:{BCN_BLUE}}}
.nav a{{font-size:13px;color:#9999cc;transition:color .2s}}
.nav a:hover,.nav a.active{{color:#fff}}

/* CARDS */
.card{{background:{CARD_BG};border:1px solid {BORDER};border-radius:12px;overflow:hidden;
  transition:border-color .2s,box-shadow .2s}}
.card:hover{{border-color:#4444aa;box-shadow:0 4px 30px #0000aa22}}
.card-header{{padding:14px 20px;border-bottom:1px solid {BORDER};display:flex;align-items:center;gap:10px}}
.dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.card-header h3{{font-size:13px;font-weight:600;letter-spacing:.5px;color:#ccccee}}
.card img{{width:100%;display:block}}

/* RESULT BADGES */
.badge-W{{background:#1a4a1a;color:#4caf50;border:1px solid #2e7d32}}
.badge-D{{background:#2a2a1a;color:#ffc107;border:1px solid #f57f17}}
.badge-L{{background:#4a1a1a;color:#ef5350;border:1px solid #b71c1c}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700;letter-spacing:1px}}

/* COMP PILL */
.pill{{display:inline-block;padding:2px 8px;border-radius:8px;font-size:10px;font-weight:600;letter-spacing:.5px}}
.pill-liga{{background:#1a2a5a;color:#6699ff}}
.pill-ucl{{background:#1a3a2a;color:#66cc88}}
.pill-copa{{background:#3a1a3a;color:#cc66cc}}
.pill-supercopa{{background:#3a2a1a;color:#ffaa44}}

/* TWO COL */
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
@media(max-width:900px){{.two-col{{grid-template-columns:1fr}}}}
.three-col{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px}}
@media(max-width:1100px){{.three-col{{grid-template-columns:1fr 1fr}}}}
@media(max-width:600px){{.three-col{{grid-template-columns:1fr}}}}

/* SECTION */
.section{{padding:36px 28px;border-top:1px solid {BORDER}}}
.sec-title{{font-size:18px;font-weight:700;color:#ccccee;margin-bottom:6px}}
.sec-sub{{font-size:12px;color:#8888bb;margin-bottom:22px}}

/* STAT BAR ROW */
.stats-header{{display:flex;justify-content:space-between;padding:0 0 14px;border-bottom:1px solid {BORDER};margin-bottom:14px}}
.stats-team-name{{font-size:13px;font-weight:800;letter-spacing:.5px}}
.sr{{display:grid;grid-template-columns:70px 1fr 70px;align-items:center;gap:10px;margin-bottom:11px}}
.sv{{font-size:15px;font-weight:800;text-align:center;line-height:1}}
.sv.h{{color:{BCN_BLUE}}} .sv.a{{color:{BCN_RED};text-align:center}}
.sb-wrap{{text-align:center}}
.sb{{display:flex;height:6px;border-radius:4px;overflow:hidden;background:#1a1a3a;margin-bottom:5px}}
.bh{{background:{BCN_BLUE};transition:width .6s}} .ba{{background:{BCN_RED};transition:width .6s}}
.sl{{font-size:9px;letter-spacing:1.8px;text-transform:uppercase;color:#5555aa}}

/* TABS */
.tabs{{display:flex;gap:8px;margin-bottom:18px;flex-wrap:wrap}}
.tab{{padding:7px 16px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;
  background:#111128;border:1px solid {BORDER};color:#9999cc;transition:all .2s}}
.tab.active,.tab:hover{{background:{BCN_BLUE};border-color:{BCN_BLUE};color:#fff}}

/* FOOTER */
.footer{{text-align:center;padding:20px;font-size:11px;color:#333366;border-top:1px solid {BORDER}}}

/* Force embedded Plotly charts to fill width.
   The pitch itself stays proportional via the figure's yaxis scaleanchor,
   so width:100% here only changes the surrounding green letterbox, not the
   pitch shape. */
.js-plotly-plot,.plot-container,.plotly{{width:100%!important}}
.js-plotly-plot .main-svg{{width:100%!important}}
"""

# ---------------------------------------------------------------------------
# INDEX PAGE
# ---------------------------------------------------------------------------
def build_index(matches):
    # Season aggregates for Barcelona
    w = sum(1 for m in matches if m["result"] == "W")
    d = sum(1 for m in matches if m["result"] == "D")
    l = sum(1 for m in matches if m["result"] == "L")
    gf = sum(m["bcn_goals"] for m in matches)
    ga = sum(m["opp_goals"] for m in matches)
    avg_xg = round(sum(m["bcn_xg"] for m in matches if m["bcn_xg"]) / max(sum(1 for m in matches if m["bcn_xg"]), 1), 2)

    def comp_pill(comp):
        cls = {"La Liga": "liga", "UCL": "ucl", "Copa": "copa", "Supercopa": "supercopa"}.get(comp, "liga")
        label = {"UCL": "UCL", "Copa": "Copa del Rey", "Supercopa": "Supercopa"}.get(comp, comp)
        return f'<span class="pill pill-{cls}">{label}</span>'

    def result_badge(r):
        return f'<span class="badge badge-{r}">{r}</span>'

    def match_card(m):
        score = f"{m['home_score']} – {m['away_score']}"
        is_home = m["bcn_is_home"]
        home_cls = f"color:{BCN_BLUE};font-weight:700" if is_home else ""
        away_cls = f"color:{BCN_BLUE};font-weight:700" if not is_home else ""
        result_color = {"W": "#4caf50", "D": "#ffc107", "L": "#ef5350"}[m["result"]]
        return f"""
<a href="match_{m['mid']}.html" class="match-card card" data-comp="{m['comp']}">
  <div style="padding:14px 18px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <span style="font-size:11px;color:#666699">{m['date']}</span>
      <div style="display:flex;gap:6px;align-items:center">
        {comp_pill(m['comp'])}
        {result_badge(m['result'])}
      </div>
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
      <span style="font-size:14px;flex:1;{home_cls}">{m['home']}</span>
      <span style="font-size:22px;font-weight:900;color:#fff;letter-spacing:-1px;min-width:60px;text-align:center;
        text-shadow:0 0 20px {result_color}55">{score}</span>
      <span style="font-size:14px;flex:1;text-align:right;{away_cls}">{m['away']}</span>
    </div>
    <div style="display:flex;justify-content:space-between;margin-top:10px;font-size:11px;color:#666699">
      <span>xG {m['xg_h']:.2f} – {m['xg_a']:.2f}</span>
      <span style="color:#555588">{m.get('venue','')[:30]}</span>
    </div>
  </div>
</a>"""

    cards_html = "\n".join(match_card(m) for m in matches)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FC Barcelona – 2025/26 Season Analytics</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
{SHARED_CSS}

/* INDEX SPECIFIC */
.hero{{background:linear-gradient(135deg,#08081a 0%,#0f0f2e 40%,#08081a 100%);
  border-bottom:1px solid {BORDER};padding:48px 32px 36px;text-align:center}}
.hero-badge{{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#6666aa;margin-bottom:16px}}
.hero-title{{font-size:42px;font-weight:900;letter-spacing:-1.5px;margin-bottom:6px}}
.hero-title span{{color:{BCN_GOLD}}}
.hero-sub{{font-size:14px;color:#6666aa}}

.record-bar{{display:flex;justify-content:center;gap:32px;padding:24px 32px;
  background:#080818;border-bottom:1px solid {BORDER};flex-wrap:wrap}}
.rec-item{{text-align:center}}
.rec-val{{font-size:28px;font-weight:900;color:#fff}}
.rec-lbl{{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#555588;margin-top:2px}}

.matches-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;
  padding:28px 28px;max-width:1400px;margin:0 auto}}
.match-card{{transition:transform .15s,box-shadow .15s}}
.match-card:hover{{transform:translateY(-2px);box-shadow:0 8px 40px #00008844}}
.match-card.hidden{{display:none}}

.filter-bar{{display:flex;gap:10px;padding:24px 28px 0;max-width:1400px;margin:0 auto;flex-wrap:wrap}}
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-logo">BCN<span>Analytics</span></div>
  <a href="index.html" class="active">Season</a>
  <span style="color:#333355;font-size:18px">|</span>
  <span style="font-size:12px;color:#555577">2025/26 · {len(matches)} matches</span>
</nav>

<div class="hero">
  <div class="hero-badge">2025 / 26 Season Dashboard</div>
  <div class="hero-title">FC <span>Barcelona</span></div>
  <div class="hero-sub">La Liga · Copa del Rey · Champions League</div>
</div>

<div class="record-bar">
  <div class="rec-item"><div class="rec-val" style="color:#4caf50">{w}</div><div class="rec-lbl">Wins</div></div>
  <div class="rec-item"><div class="rec-val" style="color:#ffc107">{d}</div><div class="rec-lbl">Draws</div></div>
  <div class="rec-item"><div class="rec-val" style="color:#ef5350">{l}</div><div class="rec-lbl">Losses</div></div>
  <div class="rec-item" style="border-left:1px solid {BORDER};padding-left:32px">
    <div class="rec-val">{gf}</div><div class="rec-lbl">Goals For</div></div>
  <div class="rec-item"><div class="rec-val">{ga}</div><div class="rec-lbl">Goals Against</div></div>
  <div class="rec-item" style="border-left:1px solid {BORDER};padding-left:32px">
    <div class="rec-val" style="color:{BCN_GOLD}">{avg_xg}</div><div class="rec-lbl">Avg xG/game</div></div>
  <div class="rec-item"><div class="rec-val">{len(matches)}</div><div class="rec-lbl">Matches</div></div>
</div>

<div class="filter-bar">
  <button class="tab active" onclick="filter('all')">All ({len(matches)})</button>
  <button class="tab" onclick="filter('La Liga')">La Liga ({sum(1 for m in matches if m['comp']=='La Liga')})</button>
  <button class="tab" onclick="filter('UCL')">Champions League ({sum(1 for m in matches if m['comp']=='UCL')})</button>
  <button class="tab" onclick="filter('Copa')">Copa del Rey ({sum(1 for m in matches if m['comp']=='Copa')})</button>
  <button class="tab" onclick="filter('Supercopa')">Supercopa ({sum(1 for m in matches if m['comp']=='Supercopa')})</button>
</div>

<div class="matches-grid" id="grid">
{cards_html}
</div>

<div class="footer">BCNProject Analytics · WhoScored + Understat data · 2025/26</div>

<script>
function filter(comp) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.match-card').forEach(c => {{
    if (comp === 'all' || c.dataset.comp === comp) c.classList.remove('hidden');
    else c.classList.add('hidden');
  }});
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# MATCH PAGE
# ---------------------------------------------------------------------------
def build_match_page(m, prev_mid, next_mid):
    mid = m["mid"]
    hn  = m["home"];  an  = m["away"]
    hs  = m["home_score"]; aws = m["away_score"]
    is_home = m["bcn_is_home"]

    home_col = BCN_BLUE if is_home else "#888888"
    away_col = BCN_BLUE if not is_home else "#888888"
    opp_col  = "#888888"
    bcn_col  = BCN_BLUE

    comp_label = m["comp"]
    result_color = {"W": "#4caf50", "D": "#ffc107", "L": "#ef5350"}[m["result"]]

    # PNGs
    def png(side, kind):
        p = os.path.join(PNG_DIR, f"{mid}_{side}_{kind}.png")
        return img_b64(p)

    h_passnet  = png("home", "passnetwork")
    a_passnet  = png("away", "passnetwork")
    h_total    = png("home", "total_passes")
    a_total    = png("away", "total_passes")
    h_fhalf    = png("home", "final_half")
    a_fhalf    = png("away", "final_half")
    h_ft       = png("home", "final_third")
    a_ft       = png("away", "final_third")
    h_box      = png("home", "into_box")
    a_box      = png("away", "into_box")
    h_prog     = png("home", "progressive_passes")
    a_prog     = png("away", "progressive_passes")
    def dribble_embed(path):
        if not os.path.exists(path):
            return "<p style='color:#666;text-align:center;padding:40px'>No take-on data.</p>"
        content = open(path, encoding="utf-8").read()
        # Extract everything inside <body>
        m2 = re.search(r"<body[^>]*>(.*?)</body>", content, re.DOTALL)
        return m2.group(1) if m2 else content

    h_drib_body = dribble_embed(os.path.join(HTML_DIR, f"{mid}_home_dribbles.html"))
    a_drib_body = dribble_embed(os.path.join(HTML_DIR, f"{mid}_away_dribbles.html"))

    # Shot maps
    shotmap_ws_body = extract_plotly_body(os.path.join(HTML_DIR, f"{mid}_shotmap_ws.html"))
    shotmap_us_body = extract_plotly_body(os.path.join(HTML_DIR, f"{mid}_shotmap_us.html"))

    # Stat bars
    def stat_row(hv, av, label):
        try:
            h = float(str(hv).replace("%",""))
            a = float(str(av).replace("%",""))
            t = h + a or 1
            hp = round(100*h/t); ap = 100-hp
        except:
            hp = ap = 50
        return f"""<div class="sr">
        <span class="sv h">{hv}</span>
        <div class="sb-wrap">
          <div class="sb"><div class="bh" style="width:{hp}%"></div><div class="ba" style="width:{ap}%"></div></div>
          <span class="sl">{label}</span>
        </div>
        <span class="sv a">{av}</span>
      </div>"""

    h_xg = m["xg_h"]; a_xg = m["xg_a"]
    xg_lbl = "xG" if m.get("xg_source") == "Understat" else "xG (model est.)"
    stats_html = (
        stat_row(f"{h_xg:.2f}",          f"{a_xg:.2f}",          xg_lbl) +
        stat_row(f"{m['h_poss']}%",       f"{m['a_poss']}%",      "Possession") +
        stat_row(m["h_sot"],              m["a_sot"],             "Shots on Goal") +
        stat_row(m["h_shots"],            m["a_shots"],           "Shots") +
        stat_row(m["h_bcc"],              m["a_bcc"],             "Big Chances Created") +
        stat_row(m["h_bcm"],              m["a_bcm"],             "Big Chances Missed") +
        stat_row(f"{m['h_pacc_pct']}%",   f"{m['a_pacc_pct']}%", "Passes (Accuracy)") +
        stat_row(m["h_duel"],             m["a_duel"],            "Duels Won") +
        stat_row(m["h_saves"],            m["a_saves"],           "Saves") +
        stat_row(m["h_fouls"],            m["a_fouls"],           "Fouls Committed")
    )

    # nav links
    prev_link = f'<a href="match_{prev_mid}.html" style="color:#8888bb">← Prev</a>' if prev_mid else ""
    next_link = f'<a href="match_{next_mid}.html" style="color:#8888bb">Next →</a>' if next_mid else ""

    def img_card(title, b64, color):
        if not b64:
            return f'<div class="card" style="padding:32px;text-align:center;color:#555577">{title}<br><small>No data</small></div>'
        return f"""<div class="card">
  <div class="card-header"><div class="dot" style="background:{color}"></div><h3>{title}</h3></div>
  <img src="{b64}" alt="{title}" loading="lazy">
</div>"""

    # Pass map tabs – 5 types
    def pass_tabs(h_tot, a_tot, h_fh, a_fh, h_ft2, a_ft2, h_bx, a_bx, h_pr, a_pr):
        tabs_data = [
            ("All Passes",            h_tot, a_tot),
            ("Final Half Passes",     h_fh,  a_fh),
            ("Final Third Entries",   h_ft2, a_ft2),
            ("Passes Into the Box",   h_bx,  a_bx),
            ("Progressive Passes",    h_pr,  a_pr),
        ]
        btns = "".join(
            f'<button class="tab{" active" if i==0 else ""}" onclick="showPassTab({i},this)">{label}</button>'
            for i, (label, _, _) in enumerate(tabs_data)
        )
        panels = "".join(
            f'<div class="pass-tab-content" id="pt{i}" style="display:{"block" if i==0 else "none"}">'
            f'<div class="two-col">'
            f'{img_card(hn + " — " + label, h_b64, home_col)}'
            f'{img_card(an + " — " + label, a_b64, away_col)}'
            f'</div></div>'
            for i, (label, h_b64, a_b64) in enumerate(tabs_data)
        )
        return f'<div class="tabs">{btns}</div>{panels}'

    venue_txt = m.get("venue", "")
    ref_txt   = m.get("referee", "")
    att_txt   = f"{m.get('attendance',''):,}" if m.get("attendance") else ""
    meta_parts = [x for x in [venue_txt, f"Ref: {ref_txt}" if ref_txt else "", f"Att: {att_txt}" if att_txt else ""] if x]
    meta_str = "  ·  ".join(meta_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{hn} {hs}–{aws} {an} | BCNAnalytics</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
{SHARED_CSS}

.hdr{{background:linear-gradient(135deg,#08081a 0%,#111130 60%,#08081a 100%);
  border-bottom:1px solid {BORDER};padding:28px 32px 20px;text-align:center}}
.match-label{{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:#6666aa;margin-bottom:12px}}
.scoreline{{display:flex;align-items:center;justify-content:center;gap:24px;margin:10px 0}}
.tn{{font-size:22px;font-weight:900;min-width:180px}}
.tn.h{{color:{home_col};text-align:right}}
.tn.a{{color:{away_col};text-align:left}}
.sc{{font-size:48px;font-weight:900;color:#fff;letter-spacing:-2px;
  text-shadow:0 0 40px {result_color}44}}
.meta{{font-size:11px;color:#555577;margin-top:8px}}

.stats-box{{max-width:760px;margin:0 auto;padding:28px 28px}}

.page-inner{{max-width:1400px;margin:0 auto}}

.match-nav{{display:flex;justify-content:space-between;padding:12px 32px;
  border-bottom:1px solid {BORDER};font-size:13px}}
</style>
</head>
<body>

<nav class="nav">
  <div class="nav-logo">BCN<span>Analytics</span></div>
  <a href="index.html">← Season</a>
</nav>

<div class="match-nav">
  {prev_link}
  <span style="font-size:12px;color:#555577">{m['date']} · {comp_label}</span>
  {next_link}
</div>

<div class="hdr">
  <div class="match-label">{comp_label} · {m['date']}</div>
  <div class="scoreline">
    <div class="tn h">{hn}</div>
    <div class="sc">{hs} – {aws}</div>
    <div class="tn a">{an}</div>
  </div>
  <span class="badge badge-{m['result']}" style="font-size:13px;padding:4px 14px">{m['result']}</span>
  <div class="meta" style="margin-top:10px">{meta_str}</div>
</div>

<!-- STATS -->
<div class="stats-box">
  <div style="text-align:center;margin-bottom:16px">
    <span style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#6666aa">Match Statistics</span>
  </div>
  <div class="stats-header">
    <span class="stats-team-name" style="color:{home_col}">{hn}</span>
    <span class="stats-team-name" style="color:{away_col}">{an}</span>
  </div>
  {stats_html}
</div>

<div class="page-inner">

<!-- SHOT MAPS -->
<div class="section">
  <div class="sec-title">🎯 Shot Maps</div>
  <div class="sec-sub">Dot size = xG · ★ = Goal · Hover for player, minute, xG, zone · {hn} attacks → &nbsp;|&nbsp; {an} attacks ←</div>

  <div style="margin-bottom:10px;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#6666aa">
    WhoScored xG Model
  </div>
  <div style="border-radius:12px;overflow:hidden;border:1px solid {BORDER};background:#1a1a2e;margin-bottom:28px;width:100%">
    {shotmap_ws_body}
  </div>

  <div style="margin-bottom:10px;font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#6666aa">
    Understat xG Model
  </div>
  <div style="border-radius:12px;overflow:hidden;border:1px solid {BORDER};background:#1a1a2e;width:100%">
    {shotmap_us_body}
  </div>
</div>

<!-- PASS NETWORKS -->
<div class="section">
  <div class="sec-title">🔗 Passing Networks</div>
  <div class="sec-sub">Starting XI · Line thickness = pass volume · Pre-first substitution</div>
  <div class="two-col">
    {img_card(hn + ' Pass Network', h_passnet, home_col)}
    {img_card(an + ' Pass Network', a_passnet, away_col)}
  </div>
</div>

<!-- PASS MAPS -->
<div class="section">
  <div class="sec-title">📊 Pass Maps</div>
  <div class="sec-sub">Green = complete · Red = incomplete</div>
  {pass_tabs(h_total, a_total, h_fhalf, a_fhalf, h_ft, a_ft, h_box, a_box, h_prog, a_prog)}
</div>

<!-- DRIBBLES -->
<div class="section">
  <div class="sec-title">⚡ Take-Ons</div>
  <div class="sec-sub">Filter by player · Green = successful · Red = unsuccessful</div>
  <div class="two-col">
    <div class="card">
      <div class="card-header"><div class="dot" style="background:{home_col}"></div><h3>{hn} Take-Ons</h3></div>
      <div style="background:#0d0d1a">{h_drib_body}</div>
    </div>
    <div class="card">
      <div class="card-header"><div class="dot" style="background:{away_col}"></div><h3>{an} Take-Ons</h3></div>
      <div style="background:#0d0d1a">{a_drib_body}</div>
    </div>
  </div>
</div>

</div><!-- /page-inner -->

<div class="footer">BCNProject Analytics · Match {mid} · WhoScored + Understat</div>

<script>
function showPassTab(idx, btn) {{
  document.querySelectorAll('.pass-tab-content').forEach((el,i) => el.style.display = i===idx ? 'block' : 'none');
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    print("=== BCNProject Website Builder ===\n")

    os.makedirs(HTML_DIR, exist_ok=True)

    print("Loading match data...")
    matches = load_matches()
    print(f"  {len(matches)} matches loaded\n")

    # Index page
    print("Building index.html...")
    html = build_index(matches)
    out = os.path.join(HTML_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved ({os.path.getsize(out)//1024}KB)\n")

    # Individual match pages
    print("Building match pages...")
    for i, m in enumerate(matches):
        prev_mid = matches[i-1]["mid"] if i > 0 else None
        next_mid = matches[i+1]["mid"] if i < len(matches)-1 else None
        html = build_match_page(m, prev_mid, next_mid)
        out = os.path.join(HTML_DIR, f"match_{m['mid']}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        kb = os.path.getsize(out) // 1024
        print(f"  [{i+1:2d}/{len(matches)}] match_{m['mid']}.html  {m['home']} {m['home_score']}-{m['away_score']} {m['away']}  ({kb}KB)")

    print(f"\nDone! Open: assets/html/index.html")


if __name__ == "__main__":
    main()
