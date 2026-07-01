"""
FC Barcelona dashboard pipeline  (mirrors the WC2026 flow, for one club)
========================================================================
Runs the full update cycle so the published dashboard refreshes ~1 hour after a
Barcelona match finishes:

    1. scrape   – pull any finished-but-not-yet-cached matches from WhoScored
                  (scrape_missing_matches.py; needs undetected-chromedriver and a
                  human to clear the odd CAPTCHA, exactly like the WC2026 scraper)
    2. build    – regenerate index.html data, the SVG match pages and all badges
                  (build_dashboard.py)
    3. publish  – commit assets/html and push to GitHub; the Pages Action then
                  deploys https://rshiri.github.io/BCNFINAL/

Usage
-----
    py bcn_pipeline.py                 # scrape -> build -> publish
    py bcn_pipeline.py --no-scrape     # build -> publish (no new data)
    py bcn_pipeline.py --no-push       # scrape -> build only (local preview)

Scheduling "1 hour after each game" (same idea as the WC2026 tasks): register one
Windows Task per fixture that runs `py bcn_pipeline.py` at kickoff + ~2h (90' game
+ stoppage + buffer). See schedule_fixtures() for a helper that writes those tasks
from a fixtures list.
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "py"


def _run(cmd, **kw):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT, **kw)


def scrape():
    """Scrape any missing finished matches (interactive: may prompt for CAPTCHA)."""
    script = os.path.join(ROOT, "scrape_missing_matches.py")
    if not os.path.exists(script):
        print("!! scrape_missing_matches.py not found — skipping scrape step")
        return
    r = _run([PY, script])
    if r.returncode != 0:
        print("!! scrape step returned non-zero; continuing with existing caches")


def build():
    r = _run([PY, os.path.join(ROOT, "build_dashboard.py")])
    if r.returncode != 0:
        raise SystemExit("build_dashboard.py failed")


def publish():
    """Commit the rebuilt site and push so GitHub Pages redeploys."""
    _run(["git", "add", "assets/html"])
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    r = _run(["git", "commit", "-m", f"Auto-update dashboard {stamp}"])
    if r.returncode != 0:
        print("Nothing to commit (dashboard unchanged).")
        return
    r = _run(["git", "push", "origin", "main"])
    if r.returncode != 0:
        print("!! git push failed — check credentials / run the push manually.")


def schedule_fixtures(fixtures):
    """fixtures: list of (name, kickoff_datetime). Registers one Windows Scheduled
    Task per fixture that runs this pipeline ~2h after kickoff (full-time + buffer)."""
    for name, ko in fixtures:
        run_at = ko + timedelta(hours=2)
        task = "BCN_" + "".join(c for c in name if c.isalnum())[:24]
        cmd = f'"{PY}" "{os.path.join(ROOT, "bcn_pipeline.py")}"'
        _run([
            "schtasks", "/Create", "/F", "/SC", "ONCE",
            "/TN", task,
            "/TR", cmd,
            "/ST", run_at.strftime("%H:%M"),
            "/SD", run_at.strftime("%d/%m/%Y"),
        ])
        print(f"  scheduled {task} for {run_at:%Y-%m-%d %H:%M}")


def main():
    ap = argparse.ArgumentParser(description="FC Barcelona dashboard pipeline")
    ap.add_argument("--no-scrape", action="store_true", help="skip the scrape step")
    ap.add_argument("--no-push", action="store_true", help="build only, do not push")
    args = ap.parse_args()

    print("=== FC Barcelona dashboard pipeline ===")
    if not args.no_scrape:
        scrape()
    build()
    if not args.no_push:
        publish()
    print("\nDone.")


if __name__ == "__main__":
    main()
