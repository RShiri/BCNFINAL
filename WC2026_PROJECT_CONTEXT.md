# WC2026 Analytics Pipeline — Project Context

Use this document to resume work in a new conversation. It covers the full
project state, architecture, known bugs, and pending tasks as of 2026-06-16.

---

## 1. Repositories

| Repo | Purpose | Branch |
|---|---|---|
| `github.com/RShiri/BCNFINAL` | Source of truth — all development happens here | `main` |
| `github.com/RShiri/XWORLDCUPTWIT` | Deployment target on Windows — receives rendered PNGs and pipeline code | `main` |

### Local Windows paths (user's machine)
```
C:\Users\puzik\BCNFINAL\         ← local clone of BCNFINAL
C:\Users\puzik\XWORLDCUPTWIT\    ← local clone of XWORLDCUPTWIT
```

### Syncing BCNFINAL → XWORLDCUPTWIT (Windows)
The user manually copies files with xcopy then pushes:
```bat
cd C:\Users\puzik
git -C BCNFINAL pull origin main
xcopy /E /I /Y BCNFINAL\wc2026 XWORLDCUPTWIT\wc2026
xcopy /E /I /Y BCNFINAL\team_logos\wc2026 XWORLDCUPTWIT\team_logos\wc2026
cd XWORLDCUPTWIT
git add wc2026\ team_logos\
git commit -m "sync from BCNFINAL"
git push
```

---

## 2. BCNFINAL Repo Structure

```
BCNFINAL/
├── wc2026/                    ← WC2026 pipeline (main deliverable)
│   ├── pipeline.py            ← orchestrator: watch → render → push → tweet
│   ├── renderer.py            ← dashboard PNG generator (self-contained)
│   ├── scraper.py             ← FotMob + WhoScored data fetcher
│   ├── schedule.py            ← WC2026 fixture list in IDT (UTC+3)
│   ├── team_colors.py         ← primary/secondary colors for all 48 nations
│   ├── generate_placeholders.py ← creates white shield badge PNGs
│   ├── git_ops.py             ← pushes PNGs to XWORLDCUPTWIT via git
│   ├── twitter_bot.py         ← posts to X/Twitter via Tweepy
│   ├── build_spain_cpv.py     ← generates Spain 0-0 Cape Verde test match JSON
│   ├── download_badges.py     ← (unused) attempted SVG→PNG badge download
│   ├── .env.template          ← copy to .env and fill in secrets
│   ├── requirements.txt
│   ├── matches/               ← input: match JSON files
│   │   ├── 2026_06_15_Spain_vs_Cape_Verde.json   ← real match (800 events)
│   │   └── sample_*.json      ← test data
│   └── output/                ← rendered dashboard PNGs
│       └── 2026_06_15_Spain_vs_Cape_Verde.png
│
├── team_logos/
│   └── wc2026/                ← 47 white-shield placeholder badge PNGs
│       ├── Spain.png, France.png, Brazil.png …   (47 total)
│       └── (drop real official PNG here to override)
│
├── barcelona/                 ← legacy Barcelona project (not active)
│   ├── data/                  ← match JSON cache files
│   ├── assets/html|png/       ← generated outputs
│   ├── Projects/              ← analysis notebooks/scripts
│   └── generate_all_assets.py ← source of coordinate helpers (inlined into renderer.py)
│
└── WC2026_PROJECT_CONTEXT.md  ← this file
```

---

## 3. WC2026 Pipeline Flow

```
WhoScored / FotMob
       │
       ▼
  scraper.py  ──►  wc2026/matches/YYYY_MM_DD_TeamA_vs_TeamB.json
       │
       ▼
  pipeline.py (file watcher / webhook)
       │
       ├──►  renderer.py  ──►  wc2026/output/YYYY_MM_DD_*.png
       │
       ├──►  git_ops.py   ──►  push PNG to XWORLDCUPTWIT/WorldCup2026/
       │
       └──►  twitter_bot.py ──► post to @RShiri X account (25-min delay)
```

### Running the pipeline
```bat
rem From XWORLDCUPTWIT root on Windows:
py -m wc2026.pipeline                        # start watcher + webhook server
py -m wc2026.pipeline --once wc2026\matches\2026_06_15_Spain_vs_Cape_Verde.json
py -m wc2026.scraper                         # watch for new WC matches
py -m wc2026.scraper --fotmob-id 4321567     # fetch one specific match
```

---

## 4. Match JSON Format

The renderer expects WhoScored-style JSON with this structure:

```json
{
  "matchId": 760428,
  "wc_metadata": {
    "stage": "Group Stage",
    "group": "H",
    "venue": "Mercedes-Benz Stadium",
    "city": "Atlanta",
    "country": "United States",
    "date": "2026-06-15"
  },
  "home": {
    "teamId": 4000,
    "name": "Spain",
    "score": 0,
    "penalty_score": null,
    "players": [
      {"playerId": 6001, "name": "Unai Simón", "shirtNo": 1,
       "position": "GK", "isFirstEleven": true, "stats": {}}
    ],
    "field": "home",
    "primary_color": "#C60B1E"
  },
  "away": { "...same structure..." },
  "events": [
    {
      "id": 1, "eventId": 2,
      "teamId": 4000,
      "playerId": 6001,
      "type": {"displayName": "Pass"},
      "outcomeType": {"displayName": "Successful"},
      "x": 6.2, "y": 48.1,
      "endX": 28.4, "endY": 61.7,
      "minute": 3, "second": 22,
      "qualifiers": []
    }
  ],
  "match_stats": {
    "possession_home": 74, "possession_away": 26,
    "shots_home": 27, "shots_away": 6,
    "shots_on_target_home": 7, "shots_on_target_away": 2,
    "xg_home": 2.16, "xg_away": 0.28,
    "passes_home": 792, "passes_away": 273,
    "pass_accuracy_home": 92, "pass_accuracy_away": 74,
    "corners_home": 8, "corners_away": 1,
    "fouls_home": 9, "fouls_away": 14,
    "yellow_cards_home": 1, "yellow_cards_away": 3,
    "red_cards_home": 0, "red_cards_away": 0
  }
}
```

**WhoScored coordinates**: x=0→100 (own goal → opponent goal), y=0→100 (left → right).
Converted to StatsBomb (120×80) via `_ws_to_sb_x()` and `SCALE_Y=0.80`.

**Shot event types**: `"MissedShots"`, `"SavedShot"`, `"ShotOnPost"`, `"BlockedShot"`, `"Goal"`
**Pass event types**: `"Pass"` with `outcomeType.displayName` = `"Successful"` or `"Unsuccessful"`

---

## 5. renderer.py — Dashboard Layout

**Canvas**: 24" × 14" @ 200 DPI = 4800 × 2800 px, white background.

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Home Badge]    SPAIN    0 – 0    CAPE VERDE    [Away Badge]       │  Row 0: Header
│                   Group H · 15 Jun 2026 · Atlanta                   │
├──────────────────┬──────────────────┬──────────────────────────────┤
│  Home Pass Net   │   Stats Table    │   Away Pass Net               │  Row 1: Mid
├──────────────────┼──────────────────┼──────────────────────────────┤
│  Home Shot Map   │ Final Third Ent. │   Away Shot Map               │  Row 2: Bottom
└──────────────────┴──────────────────┴──────────────────────────────┘
```

**Key rendering functions** (all in `wc2026/renderer.py`):
- `render_wc_dashboard(match_data, output_path)` — main entry point
- `output_filename(match_data, output_dir)` — generates filename like `2026_06_15_Spain_vs_Cape_Verde.png`
- `_draw_header()` — badge + score + venue/date
- `_draw_pass_network()` — pass network with node size = pass count
- `_draw_stats_table()` — central stats panel
- `_draw_shot_map()` — vertical pitch, xG bubble shots
- `_draw_final_third_entries()` — pass entries into final third, by channel

**Pitch style**: white/off-white (`#f5f5f5`) with dark grey lines (`#888888`). Uses mplsoccer `Pitch` / `VerticalPitch`.

**Badge images**: loaded from `team_logos/wc2026/<Team Name>.png`. Rendered with `ax.imshow()` using data coordinates. Falls back gracefully if file missing.

**renderer.py is fully self-contained** — it does NOT import from `generate_all_assets.py` or `Projects/shotmap_whoscored.py`. All helper functions are inlined:
- `_ws_to_sb_x()`, `_estimate_xg()`, `_player_name()`, `build_shot_df()`, etc.

---

## 6. Team Badges (`team_logos/wc2026/`)

**47 PNG files** — white shield shape, dark border, 3-letter code (e.g. `ESP`, `BRA`).

These are **placeholders**. To use real official badges: drop a PNG named exactly `<Team Name>.png` (e.g. `Spain.png`, `Brazil.png`) into `team_logos/wc2026/`. The renderer picks it up automatically.

**Regenerate placeholders**:
```bash
python wc2026/generate_placeholders.py --force
```

### All 48 WC2026 Qualified Nations

| Confederation | Teams |
|---|---|
| **AFC** (9) | Australia, Iran, Iraq, Japan, Jordan, Qatar, Saudi Arabia, South Korea, Uzbekistan |
| **CAF** (10) | Algeria, Cape Verde, DR Congo, Cote d'Ivoire, Egypt, Ghana, Morocco, Senegal, South Africa, Tunisia |
| **CONCACAF** (6) | Canada, Curacao, Haiti, Mexico, Panama, USA |
| **CONMEBOL** (6) | Argentina, Brazil, Colombia, Ecuador, Paraguay, Uruguay |
| **OFC** (1) | New Zealand |
| **UEFA** (15) | Austria, Belgium, Bosnia-Herzegovina, Croatia, Czechia, England, France, Germany, Netherlands, Norway, Portugal, Scotland, Spain, Sweden, Turkey |

File naming: use the exact team name as in the table above (e.g. `Cote d'Ivoire.png`, `Bosnia-Herzegovina.png`, `New Zealand.png`).

---

## 7. Environment Variables (`.env` file)

Copy `wc2026/.env.template` to `.env` at repo root. **Never commit `.env`**.

```env
# GitHub — Personal Access Token with repo write scope
GIT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
XWORLDCUPTWIT_REPO=https://github.com/RShiri/XWORLDCUPTWIT.git
XWORLDCUPTWIT_BRANCH=main

# X / Twitter — OAuth 1.0a (NOT OAuth 2.0)
X_API_KEY=...           # Consumer Key
X_API_SECRET=...        # Consumer Secret
X_ACCESS_TOKEN=...      # Access Token
X_ACCESS_TOKEN_SECRET=... # Access Token Secret

# Tuning
WC2026_TWEET_DELAY_SECONDS=1500   # 25 min delay before posting
WC2026_POLL_SECONDS=60
WC2026_WEBHOOK_SECRET=change_me
```

**Twitter auth note**: Use OAuth 1.0a keys from the Twitter Developer Portal under "Keys and tokens". The "Client ID / Client Secret" (OAuth 2.0) are NOT used — only Consumer Key/Secret + Access Token/Secret.

---

## 8. Schedule (`wc2026/schedule.py`)

Contains the full WC2026 fixture list as `KNOWN_SCHEDULE_UTC` (list of tuples).
All times stored in UTC, displayed in **IDT (Israel Daylight Time = UTC+3)**.

Key functions:
```python
from wc2026.schedule import get_upcoming_matches, get_todays_matches, print_schedule

get_todays_matches()          # matches kicking off today (IDT)
get_upcoming_matches(hours_ahead=24)  # next 24h
print_schedule()              # pretty-print full schedule in IDT
```

---

## 9. Coordinate System

WhoScored uses a 0–100 grid. StatsBomb uses 120×80.

```python
SCALE_Y = 0.80  # y: WS 0-100 → SB 0-80

def _ws_to_sb_x(ws_x):
    # Piecewise: WS50→SB60 (halfway), WS89→SB108 (pen spot), WS100→SB120
    if ws_x <= 50:   return ws_x * (60.0 / 50.0)
    elif ws_x <= 89: return 60.0 + (ws_x - 50) * (48.0 / 39.0)
    else:            return 108.0 + (ws_x - 89) * (12.0 / 11.0)

sb_y = 80 - ws_y * SCALE_Y  # flip Y axis
```

---

## 10. Known Issues & Pending Tasks

### Fixed in this session
- `renderer.py` now **self-contained** — no more `ModuleNotFoundError: No module named 'generate_all_assets'` on Windows
- White/clean pitch surface (no green)
- Badge images render correctly with `ax.imshow()` + `ax.set_autoscale_on(False)`
- Score centered between team names in header
- All 48 WC2026 team badges correct

### Pending / Known Issues

1. **`.env` accidentally committed to XWORLDCUPTWIT** — GitHub blocked push with secret scanning.
   Fix on Windows:
   ```bat
   git reset HEAD~1
   git rm --cached .env
   echo .env > .gitignore
   echo __pycache__/ >> .gitignore
   echo *.pyc >> .gitignore
   git add .gitignore
   git commit -m "add .gitignore"
   git push
   ```

2. **Barcelona PNGs still in XWORLDCUPTWIT root** — Windows `git mv 2025_*.png` fails (CMD doesn't expand globs).
   Fix using PowerShell:
   ```bat
   mkdir barcelona_matches
   powershell -command "Get-ChildItem 2025_*.png | ForEach-Object { git mv $_.Name barcelona_matches\ }"
   powershell -command "Get-ChildItem 2026_0[1-5]*.png | ForEach-Object { git mv $_.Name barcelona_matches\ }"
   git commit -m "move Barcelona PNGs to barcelona_matches/"
   git push
   ```

3. **Old `renderer.py` on Windows** — user's local BCNFINAL copy is stale. Must pull before copying:
   ```bat
   git -C C:\Users\puzik\BCNFINAL pull origin main
   copy /Y C:\Users\puzik\BCNFINAL\wc2026\renderer.py C:\Users\puzik\XWORLDCUPTWIT\wc2026\renderer.py
   ```

4. **XWORLDCUPTWIT `team_logos/wc2026/`** — copied from old BCNFINAL (before cleanup), still contains wrong teams (Bolivia, Switzerland, etc.) and missing correct ones (Curacao, Sweden, Turkey, etc.). Fix: re-run xcopy after pulling latest BCNFINAL.

5. **Real badges** — all current badges are white-shield placeholders. User should drop real official PNG files named `<Team Name>.png` into `team_logos/wc2026/` to override.

6. **WhoScored scraper** — requires Selenium + ChromeDriver on the machine running the scraper. Has not been tested live yet.

---

## 11. Key Technical Decisions

| Decision | Choice | Reason |
|---|---|---|
| Pitch background | White `#f5f5f5` | Cleaner for Twitter infographics |
| Badge rendering | `ax.imshow()` with data coords | `AnnotationBbox` caused scaling issues |
| Badge generation | matplotlib shield path | All CDNs blocked in cloud env; cairosvg SVG→PNG produced transparent images |
| Coordinate system | WhoScored 0-100 | Scraper data source; converted to StatsBomb for mplsoccer |
| Twitter auth | OAuth 1.0a (v1.1 media upload) | OAuth 2.0 doesn't support media upload |
| Schedule storage | Embedded Python list | FotMob API returns 403 in cloud environment |
| renderer deps | Fully inlined | Needed for standalone use in XWORLDCUPTWIT without BCNFINAL root |

---

## 12. Dependencies

```
# wc2026/requirements.txt
mplsoccer>=1.3
matplotlib>=3.8
numpy>=1.26
pandas>=2.2
Pillow>=10.0
requests>=2.31
cloudscraper>=1.2
selenium>=4.18
tweepy>=4.14
python-dotenv>=1.0
watchdog>=4.0
fastapi>=0.110
uvicorn>=0.29
```

Install: `pip install -r wc2026/requirements.txt`

---

## 13. Scraper Notes

- **FotMob** (`fotmob_fetch_wc_matches`): uses `cloudscraper`, no browser. Returns finished WC matches with stats and shot data. Has worked well.
- **WhoScored** (`whoscored_fetch_match`): uses Selenium + undetected ChromeDriver. Full event stream (passes, dribbles, shots). Blocked in cloud env — must run on local Windows machine.
- If WhoScored is unavailable, pass `--fotmob-only` to `scraper.py` — dashboard renders with FotMob shot data but no pass networks.

---

## 14. XWORLDCUPTWIT Intended Structure (Goal State)

```
XWORLDCUPTWIT/
├── .env                    ← secrets (gitignored)
├── .gitignore
├── wc2026/                 ← pipeline code (synced from BCNFINAL)
├── team_logos/wc2026/      ← 47 badge PNGs
├── barcelona_matches/      ← old Barcelona infographic PNGs (moved from root)
└── WorldCup2026/           ← WC2026 rendered PNGs (auto-pushed by git_ops.py)
```
