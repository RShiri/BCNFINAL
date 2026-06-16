"""
Backfill Understat xG onto every cached match that is missing it.

Understat publishes xG per match. We fetch the Barcelona season page,
key results by date, and attach `understat` to any cached WhoScored match
whose startDate matches — without re-scraping WhoScored.

Usage:
  py backfill_xg.py            # attach where missing
  py backfill_xg.py --force    # re-attach to ALL matches (overwrite)
"""
import os, re, sys, json, urllib.request

ROOT     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "assets", "data")

SEASONS = ["2025"]  # Understat season slug for 2025/26


def fetch_understat_results():
    """Return {date_str: entry} for all Barcelona results across seasons."""
    out = {}
    for season in SEASONS:
        url = f"https://understat.com/team/Barcelona/{season}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8")
            m = re.search(r"var datesData\s*=\s*JSON\.parse\('(.+?)'\);", html)
            if not m:
                print(f"  [{season}] datesData not found")
                continue
            raw = m.group(1).encode("utf-8").decode("unicode_escape")
            entries = json.loads(raw)
            n = 0
            for e in entries:
                if not e.get("isResult"):
                    continue
                date = e.get("datetime", "")[:10]
                if date:
                    out[date] = e
                    n += 1
            print(f"  [{season}] {n} results")
        except Exception as ex:
            print(f"  [{season}] fetch failed: {ex}")
    return out


def main():
    force = "--force" in sys.argv
    print("Fetching Understat results...")
    us = fetch_understat_results()
    if not us:
        print("No Understat data fetched — aborting.")
        return

    files = [f for f in os.listdir(DATA_DIR)
             if f.startswith("match_") and f.endswith("_cache.json")]

    attached, skipped, nomatch = 0, 0, 0
    for fn in files:
        path = os.path.join(DATA_DIR, fn)
        try:
            data = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print(f"  WARN {fn}: {e}")
            continue

        has_us = "understat" in data and data["understat"].get("xG")
        if has_us and not force:
            skipped += 1
            continue

        date = str(data.get("startDate", ""))[:10]
        entry = us.get(date)
        if not entry:
            # Try date ±1 day (timezone slippage between sources)
            from datetime import datetime, timedelta
            try:
                d0 = datetime.strptime(date, "%Y-%m-%d")
                for delta in (-1, 1):
                    alt = (d0 + timedelta(days=delta)).strftime("%Y-%m-%d")
                    if alt in us:
                        entry = us[alt]
                        break
            except ValueError:
                pass

        if not entry:
            hn = data.get("home", {}).get("name", "?")
            an = data.get("away", {}).get("name", "?")
            print(f"  NO MATCH  {fn}  {date}  ({hn} vs {an})")
            nomatch += 1
            continue

        data["understat"] = entry
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        xgh = entry.get("xG", {}).get("h", "?")
        xga = entry.get("xG", {}).get("a", "?")
        print(f"  ✓ {fn}  {date}  xG {xgh} – {xga}")
        attached += 1

    print(f"\nDone. Attached: {attached}  ·  Already had: {skipped}  ·  No match: {nomatch}")
    if attached:
        print("Now run:  py pipeline.py --assets-only")


if __name__ == "__main__":
    main()
