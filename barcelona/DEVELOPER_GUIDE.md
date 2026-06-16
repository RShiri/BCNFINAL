# BCNProject - Complete Football Analytics Developer Guide

Welcome to the comprehensive developer documentation for the **BCNProject (Complete Football Analytics)** repository. This document serves as a mapping guide, structural overview, and cheat sheet for future development or conversations with AI coding assistants.

---

## 📂 Project Structure & Directory Mapping

The codebase is organized into training modules, core data pipelines, database storage, and a frontend dashboard representation.

```text
BCNPROJECT-main/
│
├── EliteAnalytics/
│   ├── backend/
│   ├── data/
│   │   └── elite_analytics.db         # Core relational SQLite database (51MB)
│   └── frontend/
│
├── assets/
│   ├── data/                           # Scraped match events JSON cache (50 files)
│   │   └── match_{id}_cache.json
│   ├── html/                           # Generated plotly and match pages (259 files)
│   │   ├── index.html                  # Main season overview dashboard
│   │   └── match_{id}.html             # Match dashboards with embedded assets
│   └── png/                            # Generated static pass networks, shot maps (712 files)
│       └── {id}_{team}_{metric}.png
│
├── Module 1 to 6/                      # Interactive Jupyter tutorials
│   ├── Module 1: Python Fundamentals
│   ├── Module 3: Web Scraping (Statsbomb, Understat, Fotmob, Whoscored)
│   ├── Module 4: Data Visualization (mplsoccer, matplotlib, seaborn)
│   ├── Module 5: Data Analysis (Pandas, Numpy)
│   └── Module 6: Machine Learning (Classification, Regression, Clustering)
│
├── Projects/                           # Scripted project definitions
│   ├── Project-1-Match-Dashboards.ipynb
│   └── Project-2-Match-Prediction.ipynb
│
├── pipeline.py                         # The universal orchestrator script
├── generate_all_assets.py              # Visual asset generator (Matplotlib & Plotly)
├── build_website.py                    # Static HTML season overview and match builder
├── requirements.txt                    # Project dependencies
└── .gitignore                          # Configured to ignore __pycache__ & OS files
```

---

## ⚙️ Core Data Pipelines

The system is designed with a single entry point that orchestrates discovery, scraping, asset generation, and site building.

### 1. The Orchestrator: `pipeline.py`
This script runs the entire sequence. It discovers missing matches from WhoScored, fetches coordinates and event details, uses Understat to scrape matching xG values, caches the outputs as JSON, and triggers the asset generation.
*   **Run Scraper & Build**: `python pipeline.py`
*   **Scrape Specific Matches**: `python pipeline.py <match_id_1> <match_id_2>`
*   **Regenerate Assets Only**: `python pipeline.py --assets-only`
*   **Rebuild HTML Site Only**: `python pipeline.py --build-only`

### 2. The Visual Generator: `generate_all_assets.py`
Iterates through all match JSON files in `assets/data` and creates:
*   **Matplotlib Plots (PNGs)**: Saved to `assets/png/`. These include heatmaps, progressive passmaps, passes into the box, final-third entries, and formation pass networks.
*   **Plotly Plots (HTML)**: Interactive shot maps saved to `assets/html/`. Coordinates are scaled from WhoScored's raw scale `(100x100)` to StatsBomb's `(120x80)` pitch bounds.

### 3. The Website Compiler: `build_website.py`
Compiles all data and assets into a fast, single-page-app-like static website:
*   Generates `assets/html/index.html` as the central dashboard hub.
*   Generates interactive standalone `assets/html/match_{id}.html` dashboards.
*   **Asset Inlining**: To keep pages self-contained, PNGs are converted to base64 strings and embedded directly in the HTML.

---

## 🗄️ Database Architecture

The core data engine is `EliteAnalytics/data/elite_analytics.db`, an SQLite database containing four relational tables:

1.  **`teams`**: Key team records.
    *   `id` (Primary Key), `name`
2.  **`matches`**: Fixture records.
    *   `id` (Primary Key), `date`, `competition`, `home_team_id`, `away_team_id`, `home_score`, `away_score`
3.  **`players`**: Team rosters.
    *   `id` (Primary Key), `name`, `position`, `team_id`
4.  **`events`**: Fact table storing play-by-play actions (passes, dribbles, shots, carries).
    *   `id`, `match_id`, `team_id`, `player_id`, `minute`, `second`, `type_name`, `outcome`, `x`, `y`, `end_x`, `end_y`, `xg`, `qualifiers` (stored as JSON)

---

## 📝 Future Conversation Notes for AI Coding Assistants

When resuming development in this repository, share the following directives with the AI model:

> [!IMPORTANT]
> 1. **Do Not Stage `__pycache__`**: A `.gitignore` is active. Ensure all temporary system metadata (`.DS_Store`, `.idea`) is kept out of commits.
> 2. **File Size Awareness**: The repository contains large generated files (PNGs, caches, and a 51MB SQLite database). Keep this in mind when pulling or performing large git operations.
> 3. **Run Pipeline for Changes**: If you modify the plotting formulas (e.g. progressive pass metrics or xG estimation curves), run `python pipeline.py --assets-only` to batch-regenerate all PNGs and interactive HTML assets.
> 4. **Coordinate Scaling**: WhoScored coordinates `(0-100)` are translated to StatsBomb coordinates `(120x80)` using:
>    *   `X_StatsBomb = X_WhoScored * 1.2`
>    *   `Y_StatsBomb = 80 - (Y_WhoScored * 0.8)` (where Y=0 is the top touchline/left wing, Y=80 is the bottom touchline/right wing).
>    *   **Plotly Visualizations**: Plotly uses standard Cartesian charts where Y increases upwards. To align with StatsBomb layout conventions, Plotly charts use reversed Y-axis ranges (e.g. `yaxis: {range: [82, -2]}` for dribble maps, `yaxis: {range: [84, -4]}` for shotmaps).
> 5. **Goalmouth Shot Map Dimensions**:
>    *   The goalmouth aspect ratio is locked at a true 3:1 ratio (width `100`, height `33.33`) representing a standard 7.32m x 2.44m goal frame.
>    *   WhoScored raw `GoalMouthY` coordinates (range `[45, 55]`) are scaled to `[0, 100]` before plotting.
>    *   Plotly `yaxis` has `scaleanchor: "x"` and `scaleratio: 1.0` to prevent dimension distortion across screen sizes, with container height set to `380px` and tight padding ranges (`[-4, 104]` on X, `[-2, 38]` on Y).
