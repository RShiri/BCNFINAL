"""
FIFA World Cup 2026 - WhoScored scraper (Barcelona-style, CAPTCHA-friendly).

Mirrors the proven Barcelona flow (fetch_single_match.py / pipeline.py):
navigate straight to a WhoScored match by its match ID, wait for the
`matchCentreData` blob (solving the Cloudflare CAPTCHA by hand in the visible
browser window), extract it, convert it into the wc2026 dashboard schema
(computing match_stats from the event stream), save the JSON, and render the
country-badge PNG.

This replaces the dead FotMob JSON API path. You run it locally because only a
real desktop session can clear WhoScored's Cloudflare challenge.

Usage:
  # Scrape one or more WhoScored match IDs (visible browser; solve CAPTCHA):
  py -m wc2026.scrape_wc --ws-id 1900001 1900002

  # Convert an already-saved raw matchCentreData cache (no browser, no CAPTCHA):
  py -m wc2026.scrape_wc --from-cache path/to/match_123_cache.json --stage "Group I"

  # Skip rendering (JSON only):
  py -m wc2026.scrape_wc --ws-id 1900001 --no-render
"""

from __future__ import annotations

import os
import sys
import json
import time
import math
import logging
import argparse
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

log = logging.getLogger("wc2026.scrape_wc")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WC-SCRAPE] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

MATCHES_DIR = _REPO_ROOT / "wc2026" / "matches"
OUTPUT_DIR  = _REPO_ROOT / "wc2026" / "output"
MATCHES_DIR.mkdir(parents=True, exist_ok=True)

SHOT_TYPES = {"MissedShots", "SavedShot", "ShotOnPost", "Goal"}


# ══════════════════════════════════════════════════════════════════════════
# STATS COMPUTATION (from the WhoScored event stream)
# ══════════════════════════════════════════════════════════════════════════

def _ws_to_sb(x: float, y: float) -> tuple[float, float]:
    """Cheap linear WhoScored(0-100) -> StatsBomb(120x80) for xG geometry only."""
    return x * 1.2, 80.0 - y * 0.8


def _estimate_xg(x: float, y: float, quals: set[str]) -> float:
    """Geometry-based xG estimate matching the Barcelona wc_dashboard model."""
    sb_x, sb_y = _ws_to_sb(x, y)
    dx, dy = 120.0 - sb_x, 40.0 - sb_y
    dist = max(math.hypot(dx, dy), 0.5)
    angle = math.atan2(4.0, dist)
    xg = (angle / (math.pi / 2)) * (1.0 / (1.0 + dist / 30.0))
    if "Head" in quals:
        xg *= 0.4
    if "BigChance" in quals or "BigChanceCreated" in quals:
        xg = min(0.65, max(0.35, xg * 3.5))
    if "Penalty" in quals:
        xg = 0.76
    if dist > 18:
        xg *= (18.0 / dist) ** 2
    return round(min(max(xg, 0.01), 0.95), 3)


def _quals(ev: dict) -> set[str]:
    return {q.get("type", {}).get("displayName", "") for q in ev.get("qualifiers", [])}


def compute_match_stats(events: list[dict], home_id, away_id) -> dict:
    """Compute the flat match_stats dict the wc2026 renderer reads."""
    out: dict = {}

    def team_block(tid):
        evs = [e for e in events if e.get("teamId") == tid]
        passes = [e for e in evs if e.get("type", {}).get("displayName") == "Pass"]
        acc = [e for e in passes if e.get("outcomeType", {}).get("displayName") == "Successful"]
        shots = [e for e in evs if e.get("type", {}).get("displayName") in SHOT_TYPES]
        sot = [e for e in shots if e.get("type", {}).get("displayName") in ("SavedShot", "Goal")]
        xg = sum(_estimate_xg(e.get("x", 50), e.get("y", 50), _quals(e)) for e in shots)
        bcc = sum(1 for e in evs if "BigChanceCreated" in _quals(e))
        bcm = sum(1 for e in shots
                  if "BigChance" in _quals(e)
                  and e.get("type", {}).get("displayName") != "Goal")
        saves = sum(1 for e in evs if e.get("type", {}).get("displayName") == "Save")
        fouls = sum(1 for e in evs
                    if e.get("type", {}).get("displayName") == "Foul"
                    and e.get("outcomeType", {}).get("displayName") == "Unsuccessful")
        duels = [e for e in evs if e.get("type", {}).get("displayName") in ("Aerial", "Tackle", "TakeOn")]
        duels_won = [e for e in duels if e.get("outcomeType", {}).get("displayName") == "Successful"]
        duel_pct = round(100 * len(duels_won) / len(duels)) if duels else 0
        return {
            "passes": len(passes),
            "pass_accuracy": round(100 * len(acc) / len(passes)) if passes else 0,
            "shots": len(shots),
            "shots_on_target": len(sot),
            "xg": round(xg, 2),
            "big_chances_created": bcc,
            "big_chances_missed": bcm,
            "saves": saves,
            "fouls": fouls,
            "duels_won": duel_pct,
        }

    h = team_block(home_id)
    a = team_block(away_id)

    # Possession proxy = pass share
    tot = (h["passes"] + a["passes"]) or 1
    h_poss = round(100 * h["passes"] / tot)
    pairs = {**{f"{k}_home": v for k, v in h.items()},
             **{f"{k}_away": v for k, v in a.items()}}
    pairs["possession_home"] = h_poss
    pairs["possession_away"] = 100 - h_poss
    # Also expose passes_total / passes_accuracy aliases the renderer prefers
    pairs["passes_total_home"] = h["passes"]
    pairs["passes_total_away"] = a["passes"]
    pairs["passes_accuracy_home"] = h["pass_accuracy"]
    pairs["passes_accuracy_away"] = a["pass_accuracy"]
    out.update(pairs)
    return out


# ══════════════════════════════════════════════════════════════════════════
# CONVERTER: raw WhoScored matchCentreData  ->  wc2026 schema
# ══════════════════════════════════════════════════════════════════════════

def whoscored_to_wc2026(mcd: dict, *, stage: str = "Group Stage",
                        competition: str = "FIFA World Cup 2026") -> dict:
    """
    Convert a raw WhoScored matchCentreData dict into the wc2026 dashboard schema.
    Events are passed through unchanged (renderer expects raw WhoScored coords).
    """
    home = mcd.get("home", {})
    away = mcd.get("away", {})
    events = mcd.get("events", [])

    h_id = home.get("teamId")
    a_id = away.get("teamId")

    def players(side):
        out = []
        for p in side.get("players", []):
            out.append({
                "playerId":      p.get("playerId"),
                "name":          p.get("name", ""),
                "shirtNo":       p.get("shirtNo", 0),
                "position":      p.get("position", ""),
                "isFirstEleven": bool(p.get("isFirstEleven", False)),
                "stats":         {},
            })
        return out

    h_score = home.get("scores", {}).get("fulltime", home.get("scores", {}).get("running", 0)) or 0
    a_score = away.get("scores", {}).get("fulltime", away.get("scores", {}).get("running", 0)) or 0

    date_str = str(mcd.get("startDate", mcd.get("startTime", "")))[:10]

    return {
        "matchId": mcd.get("matchId", 0),
        "wc_metadata": {
            "stage":   mcd.get("_competition", stage),
            "venue":   mcd.get("venueName", ""),
            "city":    "",
            "country": "United States",
            "date":    date_str,
            "competition": competition,
        },
        "home": {
            "teamId": h_id, "name": home.get("name", "Home"),
            "score": h_score, "penalty_score": None,
            "players": players(home), "stats": {}, "field": "home",
        },
        "away": {
            "teamId": a_id, "name": away.get("name", "Away"),
            "score": a_score, "penalty_score": None,
            "players": players(away), "stats": {}, "field": "away",
        },
        "events": events,
        "match_stats": compute_match_stats(events, h_id, a_id),
    }


# ══════════════════════════════════════════════════════════════════════════
# SELENIUM SCRAPE (non-headless, like the Barcelona scraper)
# ══════════════════════════════════════════════════════════════════════════

def scrape_whoscored_match(ws_id: str, captcha_wait: int = 180) -> dict | None:
    """
    Open WhoScored match by ID in a VISIBLE browser and extract matchCentreData.
    Solve the Cloudflare CAPTCHA by hand if it appears; we poll up to captcha_wait
    seconds for the data blob to show up.
    """
    try:
        import undetected_chromedriver as uc
        driver = uc.Chrome(options=_visible_opts(uc.ChromeOptions()))
    except ImportError:
        from selenium import webdriver
        opts = webdriver.ChromeOptions()
        _visible_opts(opts)
        driver = webdriver.Chrome(options=opts)

    url = f"https://www.whoscored.com/Matches/{ws_id}/Live"
    log.info("Loading %s  (solve the CAPTCHA in the window if shown)", url)
    try:
        driver.get(url)
        found = False
        for i in range(captcha_wait):
            if "matchCentreData" in driver.page_source:
                found = True
                break
            if i and i % 15 == 0:
                log.info("  still waiting for data... %ds (solve CAPTCHA if needed)", i)
            time.sleep(1)
        if not found:
            log.error("  timed out waiting for matchCentreData (id=%s)", ws_id)
            return None

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(driver.page_source, "html.parser")
        script = next((s.string for s in soup.find_all("script")
                       if s.string and "matchCentreData:" in s.string), None)
        if not script:
            log.error("  matchCentreData script block not found (id=%s)", ws_id)
            return None

        start = script.find("matchCentreData:") + len("matchCentreData:")
        body = script[start:].strip()
        if "matchCentreEventTypeJson" in body:
            body = body.split("matchCentreEventTypeJson")[0].strip().rstrip(",")
        data = json.loads(body)
        data["matchId"] = int(ws_id)
        log.info("  extracted %d events (id=%s)", len(data.get("events", [])), ws_id)
        return data
    except Exception as exc:
        log.error("  scrape error (id=%s): %s", ws_id, exc)
        return None
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _visible_opts(opts):
    # NOTE: NOT headless on purpose - you need to see + solve the CAPTCHA.
    opts.add_argument("--window-size=1400,1000")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    return opts


# ══════════════════════════════════════════════════════════════════════════
# SAVE + RENDER
# ══════════════════════════════════════════════════════════════════════════

def _save_and_render(wc_json: dict, raw_mcd: dict | None, render: bool) -> Path:
    home = wc_json["home"]["name"].replace(" ", "_")
    away = wc_json["away"]["name"].replace(" ", "_")
    date = wc_json["wc_metadata"]["date"].replace("-", "_") or "2026"
    base = f"{date}_{home}_vs_{away}"

    json_path = MATCHES_DIR / f"{base}.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(wc_json, fh, indent=2, ensure_ascii=False)
    log.info("Saved JSON -> %s", json_path)

    # Also keep the raw cache for re-processing if we scraped it live
    if raw_mcd is not None:
        cache = MATCHES_DIR / f"match_{wc_json.get('matchId', base)}_cache.json"
        with open(cache, "w", encoding="utf-8") as fh:
            json.dump(raw_mcd, fh, ensure_ascii=False)

    if render:
        from wc2026.renderer import render_wc_dashboard, output_filename
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        png = output_filename(wc_json, str(OUTPUT_DIR))
        render_wc_dashboard(wc_json, png)
        log.info("Rendered PNG (with country badges) -> %s", png)
    return json_path


def main() -> None:
    p = argparse.ArgumentParser(description="WC2026 WhoScored scraper + renderer")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--ws-id", nargs="+", help="WhoScored match ID(s) to scrape")
    src.add_argument("--from-cache", help="Convert an existing raw matchCentreData JSON")
    p.add_argument("--stage", default="Group Stage", help="Tournament stage label")
    p.add_argument("--no-render", action="store_true", help="Save JSON only, skip PNG")
    args = p.parse_args()

    render = not args.no_render

    if args.from_cache:
        with open(args.from_cache, encoding="utf-8") as fh:
            mcd = json.load(fh)
        wc = whoscored_to_wc2026(mcd, stage=args.stage)
        _save_and_render(wc, None, render)
        return

    ok = 0
    for wid in args.ws_id:
        mcd = scrape_whoscored_match(wid)
        if not mcd:
            log.warning("Skipping id=%s (no data)", wid)
            continue
        wc = whoscored_to_wc2026(mcd, stage=args.stage)
        _save_and_render(wc, mcd, render)
        ok += 1
        time.sleep(8)  # be polite between matches
    log.info("Done. %d/%d matches processed.", ok, len(args.ws_id))


if __name__ == "__main__":
    main()
