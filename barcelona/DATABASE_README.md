# Elite Analytics Database Structure

The `elite_analytics.db` SQLite database serves as the core storage engine for match event data, players, and team information. It allows for efficient querying and generation of advanced analytics visualizations like pass networks, shot maps, and xG models.

## Location
`EliteAnalytics/data/elite_analytics.db`

## Coverage

Four Barcelona seasons, **171 matches / ~200k events**:

| Season | Matches | Competition | Source | Events |
|---|---|---|---|---|
| 2022-23 | 38 | La Liga | `xlaliga` | 41,087 |
| 2023-24 | 38 | La Liga | `xlaliga` | 41,340 |
| 2024-25 | 38 | La Liga | `xlaliga` | 40,378 |
| 2025-26 | 57 | La Liga + UCL + Copa | `whoscored` | 77,724 |

The 2025/26 rows come from this project's own WhoScored scrape (`scraper.py`) and carry the
full event taxonomy. The three earlier seasons were imported from the
[XLALIGA](https://github.com/RShiri/XLALIGA) dashboard dataset by
[`import_xlaliga.py`](import_xlaliga.py) — see [Importing from XLALIGA](#importing-from-xlaliga).

## Schema Overview

The database consists of four main relational tables:
1. **`teams`**: Stores unique team identities.
2. **`matches`**: Stores high-level match metadata and results.
3. **`players`**: Stores player details linked to specific teams.
4. **`events`**: The core fact table containing chronologically ordered play-by-play actions (passes, shots, dribbles, etc.) with coordinates and expected metrics.

Plus four aggregate tables added with the multi-season import:

5. **`team_match_stats`**: One row per team per match (possession, shots, xG, duels…).
6. **`player_match_stats`**: One row per player per match — the lineup sheet with minutes, rating, goals, xG/xA.
7. **`player_season_stats`**: Barcelona squad totals per season.
8. **`season_summary`**: Barcelona's final league position and record per season.

---

### 1. `teams` Table
Stores the unique teams involved in the matches.
* `id` (INTEGER, Primary Key): Unique identifier for the team (often maps to provider IDs like WhoScored).
* `name` (VARCHAR, Unique): The name of the team (e.g., "Barcelona", "Atletico Madrid").

### 2. `matches` Table
Contains the metadata and final scoreline for each scraped fixture.
* `id` (INTEGER, Primary Key): Unique match ID matching the provider (e.g., `1968936`).
* `date` (VARCHAR): The date and time of the fixture.
* `competition` (VARCHAR): The competition name (e.g., "La Liga", "Copa del Rey").
* `home_team_id` (INTEGER, Foreign Key): Links to `teams.id`.
* `away_team_id` (INTEGER, Foreign Key): Links to `teams.id`.
* `home_score` (INTEGER): Final goals scored by the home team.
* `away_score` (INTEGER): Final goals scored by the away team.
* `season` (VARCHAR): Season the fixture belongs to, e.g. `"2024-25"` (rolls over in July).
* `matchday` (INTEGER): League round, 1-38. `NULL` for cup and European ties.
* `venue` (VARCHAR): Stadium, where the source provides one.
* `home_xg` / `away_xg` (FLOAT): Match-level expected goals.
* `xg_estimated` (BOOLEAN): `1` when xG is modelled from shot locations rather than official.
* `source` (VARCHAR): `"whoscored"` for this project's own scrape, `"xlaliga"` for imported rows.
* `fotmob_id` (INTEGER): FotMob's id for the fixture, when known.

### 3. `players` Table
Maintains the roster of players associated with teams.
* `id` (INTEGER, Primary Key): Unique player ID.
* `name` (VARCHAR): The player's full name.
* `position` (VARCHAR): The player's primary position (if available).
* `team_id` (INTEGER, Foreign Key): Links to `teams.id`.

### 4. `events` Table
This is the most critical and granular table in the database. It stores every registered on-ball action in a match.
* `id` (INTEGER, Primary Key): Auto-incrementing internal ID.
* `match_id` (INTEGER, Foreign Key): Links to `matches.id`.
* `team_id` (INTEGER, Foreign Key): Linked team performing the action.
* `player_id` (INTEGER, Foreign Key): Linked player performing the action.
* `event_id` (INTEGER): Provider-specific event identifier to ensure chronological ordering.
* `minute` (INTEGER): The minute the event occurred.
* `second` (INTEGER): The second the event occurred.
* `type_name` (VARCHAR): The classification of the event (e.g., "Pass", "TakeOn", "Shot", "SubstitutionOn").
* `outcome` (VARCHAR): The result of the action (e.g., "Successful", "Unsuccessful").
* `x` (FLOAT): The starting X coordinate of the action (0-100 scale, usually transformed to StatsBomb 120 scale later).
* `y` (FLOAT): The starting Y coordinate of the action.
* `end_x` (FLOAT): The ending X coordinate (for passes/carries).
* `end_y` (FLOAT): The ending Y coordinate.
* `is_shot` (BOOLEAN): Flag if the event is a shot.
* `xg` (FLOAT): The Expected Goals value (if applicable/calculated).
* `xt` (FLOAT): Expected Threat (if calculated).
* `under_pressure` (BOOLEAN): Flag if the action was performed under defensive pressure.
* `is_big_chance` (BOOLEAN): Flag denoting high-value opportunities.
* `is_penalty` (BOOLEAN): Flag if the event is a penalty kick.
* `is_final_third_pass` (BOOLEAN): Flag indicating passes entering the attacking third.
* `is_progressive_pass` (BOOLEAN): Flag for passes moving significantly closer to the opponent's goal.
* `possession_chain_id` (INTEGER): ID clustering sequential events belonging to the same unbroken team possession.
* `qualifiers` (JSON): A stored JSON string containing supplementary flags (e.g., body part used, pass height, set piece context).

### 5. `team_match_stats` Table
One row per team per match (so two rows per fixture), keyed on `(match_id, team_id)`.
* `season`, `team_id`, `opponent_id`, `side` (`"home"`/`"away"`).
* `goals`, `conceded`, `xg`, `xg_against`.
* `possession`, `shots`, `sot`, `passes`, `pass_acc`, `big_chances`, `big_missed`, `saves`, `fouls`, `duels_won`, `corners`.

### 6. `player_match_stats` Table
The lineup sheet for every match — starters and used substitutes.
* `match_id`, `season`, `team_id`, `player_id`, `player`, `shirt_no`, `position`.
* `started` (BOOLEAN), `minutes`, `on_minute`, `off_minute` (substitution timings).
* `goals`, `assists`, `xg`, `xa`, `rating`, `yellow`, `red`, `motm`.

### 7. `player_season_stats` Table
Barcelona squad totals for one season, keyed on `(season, player_id)`: appearances, minutes, goals, assists, xG/xA, shots, passes and completion, key passes, touches, tackles, interceptions, aerials, dribbles, fouls, clearances, times dispossessed, saves, cards and average rating.

### 8. `season_summary` Table
Barcelona's league campaign, one row per season: `position`, `played`, `won`, `drawn`, `lost`, `gf`, `ga`, `gd`, `points`, plus season-total `xg_for` / `xg_against`.

## Relationships
- A `team` can have many `players` and partake in many `matches`.
- A `match` contains thousands of `events`.
- An `event` is strictly tied to one `match`, one `team`, and usually one `player`.
- `team_match_stats` and `player_match_stats` join back to `matches` on `match_id`, giving the aggregate view of the same fixtures the `events` table holds ball-by-ball.

## Usage
Data from this database is queried by Python scripts (like `generate_all_assets.py`) using `pandas.read_sql` to filter by `match_id` and `type_name` (e.g., Pass, Shot) to compute aggregate statistics and plot coordinates on a pitch.

Now that matches carry a `season`, the same queries can be scoped to a campaign or run across
all four:

```python
df = pd.read_sql("""
    SELECT e.* FROM events e
    JOIN matches m ON m.id = e.match_id
    JOIN teams t   ON t.id = e.team_id
    WHERE m.season = '2024-25' AND t.name = 'Barcelona' AND e.type_name = 'Pass'
""", conn)
```

## Importing from XLALIGA

`import_xlaliga.py` pulls Barcelona fixtures out of the
[XLALIGA](https://github.com/RShiri/XLALIGA) dashboard dataset (`laliga_dashboard/data.js`,
`players.js` and `matches_detail/<id>.js`) and writes them into this database.

```bash
git clone https://github.com/RShiri/XLALIGA ../XLALIGA
py import_xlaliga.py --source ../XLALIGA --dry-run   # report counts, write nothing
py import_xlaliga.py --source ../XLALIGA
```

Options: `--seasons 2022-23,2023-24` to limit the range, `--db` for a different target,
`--replace-existing` to overwrite fixtures the native scrape already covers.

**Behaviour worth knowing:**
- **Idempotent.** Re-running replaces the rows it wrote previously rather than duplicating them.
- **The native scrape wins.** The 38 La Liga fixtures of 2025/26 already scraped by `scraper.py`
  keep their own match ids and richer event streams; they only *gain* the season metadata and
  the `team_match_stats` / `player_match_stats` rows. Pass `--replace-existing` to override.
- **Fixtures are matched by club pair, not date.** The two providers date the same match up to
  six days apart (FotMob stores the UTC kick-off), so an exact-date join would re-import
  fixtures the database already holds.
- **Player ids line up.** XLALIGA carries the same WhoScored player ids this database uses, so
  Lewandowski is one row across all four seasons rather than one per season.

**Fidelity of imported seasons.** XLALIGA's per-match files keep only the on-ball attacking
actions, so 2022-23 → 2024-25 contain `Pass`, `TakeOn`, `Goal`, `SavedShot`, `MissedShots`,
`ShotOnPost` and `Save` events — roughly 1,080 per match against ~1,560 for a natively scraped
one. Defensive and off-ball event types (`Tackle`, `Interception`, `Clearance`, `Aerial`,
`BallRecovery`, `Dispossessed`, `Foul`, substitutions…) exist only for 2025/26; the aggregate
counts for those actions are still available per player in `player_season_stats`. Blocked shots
are absent from the source entirely, so no `BlockedShot` events appear in the imported seasons.
`under_pressure`, `xt` and `possession_chain_id` are likewise unset on imported events.

Filter on `matches.source` when a piece of analysis needs the full taxonomy.
