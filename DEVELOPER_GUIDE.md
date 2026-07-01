# BCNProject — Developer Guide

Developer documentation for the FC Barcelona 2025/26 analytics dashboard: a
World-Cup-2026-style single-page app driven by scraped WhoScored + Understat data.

**Live site:** https://rshiri.github.io/BCNFINAL/  (served from the `gh-pages` branch)

---

## 📂 Project structure

```text
BCNPROJECT-main/
│
├── build_dashboard.py          # PRIMARY builder — generates the whole dashboard
├── build_website.py            # legacy helpers reused by build_dashboard (load_matches, xG model)
├── bcn_pipeline.py             # scrape -> build -> publish orchestrator (+ per-fixture scheduling)
├── scrape_missing_matches.py   # WhoScored scraper (undetected-chromedriver; manual CAPTCHA)
│
├── assets/
│   ├── data/                   # WhoScored match caches:  match_{id}_cache.json
│   └── html/                   # THE SITE (this folder is what gets deployed)
│       ├── index.html          # SPA shell (static)
│       ├── app.js              # SPA logic (static, pure ASCII)
│       ├── data.js             # GENERATED: window.DATA (per-season totals/players + matches)
│       ├── styles.css          # WC2026 stylesheet (copied verbatim)
│       ├── match.html          # match-centre shell (ported from WC2026)
│       ├── match.js            # match-centre logic (ported from WC2026)
│       ├── match.css           # match-centre styles (ported from WC2026)
│       ├── matches_detail/     # GENERATED: <id>.js  (window.MATCH_DETAIL per match)
│       ├── logos/              # team badges used by the SPA (slug-named)
│       └── mclogos/            # team badges used by match.js (exact-name-keyed)
│
├── team_logos/                 # source club/national badges (build-time input)
├── Projects/shotmap_whoscored.py   # geometry xG model (build_shot_df)
└── requirements.txt
```

---

## 🖥️ Frontend architecture

The site is a **single-page app** modelled on the WC2026 dashboard, adapted for one club.

### The dashboard SPA — `index.html` + `app.js` + `data.js`
`index.html` is a static shell (header + tab nav + empty containers). `app.js` reads
the global `window.DATA` from `data.js` and renders every tab client-side. Tabs:

| Tab         | What it shows |
|-------------|---------------|
| Overview    | season stat strip, record-by-competition table, form, results timeline |
| Matches     | fixtures & results (comp badge + coloured edge); Season totals toggle; each row deep-links to the match centre |
| Players     | leaders, sortable table, preset sorts, leaderboards |
| xG Lab      | goals-vs-xG scatter, actual goals/conceded, home/away xG, clinical/wasteful finishers |
| Player Lab  | per-player stat card, shot map, percentile radar, and head-to-head compare (bars + a pitch **heatmap per metric** side by side) |
| Shot Maps   | grid of matches linking to the match centre |
| Data        | dataset summary |

### The match centre — `match.html?id=<id>` + `match.js` + `matches_detail/<id>.js`
Copied file-for-file from WC2026 (only the logo path and the head-to-head stat
source were changed). `match.html` loads `data.js` then `match.js`; `match.js` reads
`?id=` and injects `matches_detail/<id>.js` (which sets `window.MATCH_DETAIL`), then
renders: **Match stats · xG momentum · Shot map · On-target shots · Pass explorer ·
Dribbles · Pass network · Average position · Line-ups · All goals map · Goal replays.**
No images — everything is SVG built from the event stream.

---

## ⚙️ The builder — `build_dashboard.py`

`py build_dashboard.py` does everything:

1. `bw.load_matches()` (from `build_website.py`) reads every `assets/data/match_*_cache.json`.
2. Filters to Barcelona matches; normalises competition names; applies `COMP_OVERRIDE`
   (a `{mid: comp}` dict to pin any match) and the "Riyadh Air Metropolitano ≠ Supercopa" fix.
3. Tags each match with its season (`season_of(date)`) and aggregates **per season** (plus a
   combined `all`): season totals, per-competition records, per-player stats (incl. progressive
   passes and per-metric **12×8 pitch heatmaps**), and a global per-player shot list. See
   [Seasons & the 2026/27 pipeline](#-seasons--the-202627-pipeline).
4. Writes `assets/html/data.js` as `window.DATA = {...}` — **`ensure_ascii=True`** so it
   parses regardless of the charset the static server advertises.
5. Copies team badges into `logos/` and `mclogos/`.
6. Generates `matches_detail/<id>.js` (`window.MATCH_DETAIL`) for every match by extracting
   shots (+ model xG), passes (with receiver/progressive/key/assist/cross), dribbles, goals,
   line-ups and saves from the raw WhoScored events.

> **app.js must stay pure ASCII.** JS files are served without a charset header; use HTML
> entities (`&rarr;`, `&middot;`, `&mdash;`, `&#9660;`) instead of literal unicode. Validate
> with `node --check assets/html/app.js` after edits.

---

## 🗓️ Seasons & the 2026/27 pipeline

The dashboard is **multi-season aware**. A header **season switch** offers every season present in
the data plus the upcoming one, and **All seasons**; picking one re-slices every tab client-side.

**How a match gets its season.** `season_of(date)` in `build_dashboard.py` maps a date to a
`YYYY/YY` season on a **Jul→Jun** boundary (`2025-08-16` and `2026-06-14` are both `2025/26`;
`2026-08-…` becomes `2026/27`). Every match record is tagged `m["season"]`, and each `_games`
entry in `player_events.js` carries its season too.

**`window.DATA` shape (per season):**

```jsonc
{
  "defaultSeason": "2025/26",                    // latest season that has data
  "seasonList":   ["2025/26", "2026/27", "all"],
  "seasonLabels": { "all": "All seasons", ... },
  "seasons": {                                   // totals/byComp/players PER season (+ "all")
    "2025/26": { "totals": {...}, "byComp": [...], "players": [...] },
    "2026/27": { "totals": {0…}, "byComp": [],    "players": [] },
    "all":     { ... }
  },
  "matches":     [ { "season": "2025/26", ... }, ... ],  // global — filtered client-side
  "playerShots": { "<name>": [ { "date": ..., ... } ] }  // global — filtered by date client-side
}
```

`app.js`'s `applySeason(sel)` sets the active `M / P / T / SHOTS / PEV` slices. Matches, shots and
events are filtered **client-side by date/season**, so the 800 KB+ `player_events.js` is **not**
duplicated per season. A season with no data renders a friendly empty state on every tab.

### ⚠️ TODO — 2026/27 needs a new data pipeline

There is **no fixture or match feed for 2026/27 yet**, so the season is selectable but empty. The
old FotMob endpoints in `fetch_results.py` are **dead (HTTP 404)**, so a new collector is required:

1. Pull the **2026/27 La Liga schedule** (then cup / UCL fixtures) from a working source.
2. After each match, fetch its WhoScored feed and write `assets/data/match_<id>_cache.json` with a
   `startDate` of `2026-08` or later (the same shape the existing scraper produces).
3. Run `py build_dashboard.py`.

`season_of(date)` then buckets those caches into **2026/27 automatically** — no frontend or data-
schema changes needed. Until that pipeline exists, the 2026/27 tab intentionally shows empty
states pointing here.

---

## 🔁 Pipeline & scheduling — `bcn_pipeline.py`

Mirrors the WC2026 automation for the club dashboard:

```
py bcn_pipeline.py                 # scrape -> build -> publish
py bcn_pipeline.py --no-scrape     # build -> publish (no new data)
py bcn_pipeline.py --no-push       # scrape -> build only (local preview)
```

`schedule_fixtures([(name, kickoff_dt), ...])` registers one Windows task per fixture that
runs the pipeline ~2h after kickoff (90' + stoppage + buffer) — the "scrape 1 hour after
the game" cadence. Scraping needs `undetected-chromedriver` and a human for the odd CAPTCHA,
so it can only run locally.

---

## 🚀 Deploy

The site is served from the **`gh-pages`** branch (root), not GitHub Actions — this keeps
`main` untouched and works with a PAT that lacks `workflow` scope.

Redeploy after a rebuild:
1. `py build_dashboard.py`
2. Copy `assets/html/{index.html,app.js,data.js,styles.css,match.*}` + `matches_detail/`,
   `logos/`, `mclogos/` (and a `.nojekyll`) to a clean folder.
3. Commit that folder on `gh-pages` and push. Pages redeploys in ~1 min.

`GIT_TOKEN` in `.env` is the push token. Pages source is `gh-pages` / (set via the REST API).

---

## 🗄️ Database (legacy)

`EliteAnalytics/data/elite_analytics.db` (SQLite) still holds the relational tables
(`teams`, `matches`, `players`, `events`). The live dashboard is driven by the JSON caches,
not this DB.

---

## 🎯 Coordinate systems

- **SVG shot maps / heatmaps** use raw WhoScored coordinates `(0–100, 0–100)`. In the match
  centre the home side attacks right; the away side is rotated 180° (`x → 100−x`).
- **The geometry xG model** (`Projects/shotmap_whoscored.build_shot_df`) converts to
  StatsBomb `(120×80)`:  `X = X_ws * 1.2`, `Y = 80 − (Y_ws * 0.8)`. Its output feeds the xG
  totals and the Player-Lab shot scatter.
- **Goalmouth (on-target) view**: `GoalMouthY` `[45,55]` scaled to `[0,100]`; goal frame
  locked to a 3:1 ratio (7.32m × 2.44m).

---

## 📝 Notes for AI assistants

1. Rebuild after any data/formula change: `py build_dashboard.py`. Validate JS with `node --check`.
2. Keep `app.js` ASCII; keep `data.js`/`matches_detail` ASCII (`ensure_ascii=True`).
3. Don't force-push `main` — it was reorganised into a `barcelona/` subfolder by another
   session. Deploy via `gh-pages` only.
4. Match counts vs the official 38/10/4/2 = 54 need the missing/duplicate matches resolved
   with the local scraper; use `COMP_OVERRIDE` to pin competitions.
