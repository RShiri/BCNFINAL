"""
FIFA World Cup 2026 – Combined one-shot match runner.

Does the entire flow for ONE match in a single synchronous call:
    scrape (WhoScored via FotMob id) → render PNG → push to GitHub → post to X.

Unlike pipeline.py (a long-running watcher with a delayed-tweet thread), this
module runs start-to-finish and exits. That makes it ideal for Windows Task
Scheduler: register one task per match firing at (kick-off + 2h), each calling

    py -m wc2026.run_match --fotmob-id <ID>

Usage:
    py -m wc2026.run_match --fotmob-id 4667812
    py -m wc2026.run_match --fotmob-id 4667812 --fotmob-only   # skip WhoScored
    py -m wc2026.run_match --fotmob-id 4667812 --no-post       # render+push only
    py -m wc2026.run_match --fotmob-id 4667812 --no-push       # render+post only
    py -m wc2026.run_match --from-file wc2026/matches/x.json    # skip scraping
"""

from __future__ import annotations

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# ── Bootstrap path + env ──────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env", override=False)
except ImportError:
    pass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")

from wc2026.scraper     import fetch_and_save, fotmob_fetch_wc_matches
from wc2026.renderer    import render_wc_dashboard, output_filename
from wc2026.git_ops     import push_png_to_xworldcuptwit
from wc2026.twitter_bot import post_match_infographic

log = logging.getLogger("wc2026.run_match")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RUN] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_REPO_ROOT / "wc2026" / "run_match.log", encoding="utf-8"),
    ],
)

OUTPUT_DIR = _REPO_ROOT / "wc2026" / "output"


def run_match(
    fotmob_id: int | None = None,
    from_file: str | None = None,
    *,
    fotmob_only: bool = False,
    do_push: bool = True,
    do_post: bool = True,
) -> bool:
    """
    Full single-match flow. Returns True on success (PNG rendered, plus push/post
    as requested). Either `fotmob_id` or `from_file` must be given.
    """
    # ── 1. Acquire match JSON ─────────────────────────────────────────────
    if from_file:
        json_path = Path(from_file)
        if not json_path.exists():
            log.error("Match file not found: %s", json_path)
            return False
        log.info("Using existing match file: %s", json_path.name)
    elif fotmob_id is not None:
        log.info("Scraping match id=%d …", fotmob_id)
        # Pull the XML stub so names/date resolve even though FotMob JSON is dead
        xml_stub = None
        try:
            xml_stub = next(
                (m for m in fotmob_fetch_wc_matches() if m.get("id") == fotmob_id),
                None,
            )
        except Exception as exc:
            log.warning("Could not fetch XML stub for id=%d: %s", fotmob_id, exc)

        json_path = fetch_and_save(fotmob_id, fotmob_only=fotmob_only, xml_match=xml_stub)
        if not json_path:
            log.error("Scrape failed for id=%d — aborting.", fotmob_id)
            return False
        log.info("Scraped → %s", json_path)
    else:
        log.error("Must provide either --fotmob-id or --from-file.")
        return False

    # ── 2. Load data ──────────────────────────────────────────────────────
    try:
        with open(json_path, encoding="utf-8") as fh:
            match_data = json.load(fh)
    except Exception as exc:
        log.error("Cannot read %s: %s", json_path, exc)
        return False

    home = match_data.get("home", {}).get("name", "Home")
    away = match_data.get("away", {}).get("name", "Away")

    # ── 3. Render dashboard PNG ───────────────────────────────────────────
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        png_path = output_filename(match_data, str(OUTPUT_DIR))
        render_wc_dashboard(match_data, png_path)
        log.info("PNG rendered → %s", png_path)
    except Exception as exc:
        log.error("Render failed for %s vs %s: %s", home, away, exc)
        return False

    # ── 4. Push PNG to XWORLDCUPTWIT (non-fatal) ──────────────────────────
    if do_push:
        try:
            raw_url = push_png_to_xworldcuptwit(
                png_path,
                commit_message=f"[WC2026] {home} vs {away} analytics dashboard",
            )
            log.info("PNG pushed → %s", raw_url)
        except Exception as exc:
            log.error("Git push failed (continuing): %s", exc)
    else:
        log.info("Skipping Git push (--no-push).")

    # ── 5. Post to X immediately (no delay — match already finished) ───────
    if do_post:
        try:
            url = post_match_infographic(png_path, match_data)
            if url:
                log.info("Tweet posted → %s", url)
            else:
                log.warning("Tweet not posted (missing credentials or API error).")
        except Exception as exc:
            log.error("Tweet failed: %s", exc)
            return False
    else:
        log.info("Skipping X post (--no-post).")

    log.info("DONE: %s vs %s", home, away)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WC2026 one-shot: scrape → render → push → post for a single match."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--fotmob-id", type=int, help="FotMob match ID to scrape and process.")
    src.add_argument("--from-file", help="Path to an existing match JSON (skip scraping).")

    parser.add_argument("--fotmob-only", action="store_true",
                        help="Skip WhoScored (FotMob shot data only).")
    parser.add_argument("--no-push", action="store_true",
                        help="Don't push the PNG to GitHub.")
    parser.add_argument("--no-post", action="store_true",
                        help="Don't post the tweet.")
    args = parser.parse_args()

    ok = run_match(
        fotmob_id=args.fotmob_id,
        from_file=args.from_file,
        fotmob_only=args.fotmob_only,
        do_push=not args.no_push,
        do_post=not args.no_post,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
