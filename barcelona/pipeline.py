"""
BCNProject – Universal Pipeline
================================
One script to rule them all. Handles scraping, asset generation, and website build.

Usage
-----
  py pipeline.py                        # discover + scrape all missing matches, rebuild
  py pipeline.py <match_id>             # scrape one specific match by WhoScored ID
  py pipeline.py <id1> <id2> ...        # scrape several specific matches
  py pipeline.py --assets-only          # skip scraping, just regenerate assets + rebuild
  py pipeline.py --build-only           # skip scraping + assets, just rebuild website
  py pipeline.py --team <team_id>       # discover for a different team (default 65=Barcelona)
  py pipeline.py --no-rebuild           # scrape + assets but don't rebuild website

Requirements
------------
  pip install undetected-chromedriver beautifulsoup4
"""

import os, sys, json, re, time, subprocess, urllib.request, argparse, glob

ROOT     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "assets", "data")
HTML_DIR = os.path.join(ROOT, "assets", "html")
os.makedirs(DATA_DIR, exist_ok=True)

# WhoScored fixture pages for Barcelona (team ID 65)
DEFAULT_FIXTURE_PAGES = {
    "La Liga":      "https://www.whoscored.com/Teams/65/Fixtures/Spain-Barcelona",
    "UCL":          "https://www.whoscored.com/Teams/65/Fixtures/Europe-Champions-League-Barcelona",
    "Copa del Rey": "https://www.whoscored.com/Teams/65/Fixtures/Spain-Copa-del-Rey-Barcelona",
    "Supercopa":    "https://www.whoscored.com/Teams/65/Fixtures/Spain-Supercopa-de-Espana-Barcelona",
}

SAUDI_VENUES = {"king fahd", "king abdullah", "jeddah", "riyadh", "lusail", "saudi"}

# ---------------------------------------------------------------------------
# UNDERSTAT
# ---------------------------------------------------------------------------
def fetch_understat(team="Barcelona", season="2025"):
    print(f"  [Understat] Fetching {team} {season}...")
    url = f"https://understat.com/team/{team}/{season}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
        m = re.search(r"var datesData\s*=\s*JSON\.parse\('(.+?)'\);", html)
        if m:
            raw = m.group(1).encode("utf-8").decode("unicode_escape")
            entries = json.loads(raw)
            result = {e["datetime"][:10]: e for e in entries if e.get("isResult")}
            print(f"  [Understat] Got {len(result)} results")
            return result
    except Exception as e:
        print(f"  [Understat] Failed: {e}")
    return {}

# ---------------------------------------------------------------------------
# DRIVER SETUP
# ---------------------------------------------------------------------------
def make_driver():
    try:
        import undetected_chromedriver as uc
        opts = uc.ChromeOptions()
        opts.add_argument("--window-size=1920,1080")
        return uc.Chrome(options=opts)
    except ImportError:
        print("ERROR: undetected-chromedriver not installed.")
        print("       pip install undetected-chromedriver")
        sys.exit(1)

# ---------------------------------------------------------------------------
# DISCOVER MATCH IDs FROM FIXTURE PAGE
# ---------------------------------------------------------------------------
def discover_ids(driver, url, comp_name, wait=25):
    print(f"  Discovering {comp_name}...")
    driver.get(url)
    print(f"    Waiting {wait}s (solve CAPTCHA if shown)...")
    time.sleep(wait)
    ids = re.findall(r'/[Mm]atches/(\d+)/(?:[Ll]ive|[Mm]atch[Rr]eport)', driver.page_source)
    unique = list(dict.fromkeys(ids))
    print(f"    Found {len(unique)} match IDs")
    return unique

# ---------------------------------------------------------------------------
# SCRAPE ONE MATCH
# ---------------------------------------------------------------------------
def scrape_match(driver, match_id, understat, comp_hint="", force=False):
    out_path = os.path.join(DATA_DIR, f"match_{match_id}_cache.json")
    if os.path.exists(out_path) and not force:
        print(f"  [{match_id}] Already cached — skip (use --force to re-scrape)")
        return False

    url = f"https://www.whoscored.com/Matches/{match_id}/Live"
    print(f"  [{match_id}] {comp_hint}  →  {url}")
    driver.get(url)

    found = False
    for i in range(90):
        if "matchCentreData" in driver.page_source:
            found = True
            break
        if i % 15 == 0 and i > 0:
            print(f"    Still waiting... {i}s (solve CAPTCHA if needed)")
        time.sleep(1)

    if not found:
        print(f"    TIMEOUT — skipping {match_id}")
        return False

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(driver.page_source, "html.parser")
    script = next((s.string for s in soup.find_all("script")
                   if s.string and "matchCentreData:" in s.string), None)
    if not script:
        print(f"    Script block not found")
        return False

    try:
        start = script.find("matchCentreData:") + len("matchCentreData:")
        content = script[start:].strip()
        if "matchCentreEventTypeJson" in content:
            json_str = content.split("matchCentreEventTypeJson")[0].strip().rstrip(",")
        else:
            json_str = content
        data = json.loads(json_str)
    except Exception as e:
        print(f"    JSON parse error: {e}")
        return False

    # Attach Understat xG by date
    date_str = str(data.get("startDate", ""))[:10]
    us = understat.get(date_str)
    if us:
        data["understat"] = us
        xgh = us.get("xG", {}).get("h", "?")
        xga = us.get("xG", {}).get("a", "?")
        print(f"    Understat xG: h={xgh}  a={xga}")

    # Competition tag
    if comp_hint:
        data["_competition"] = comp_hint

    venue = str(data.get("venueName", "")).lower()
    if any(v in venue for v in SAUDI_VENUES):
        data["_competition"] = "Supercopa"
        print(f"    → Supercopa (Saudi venue)")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    hn  = data.get("home", {}).get("name", "?")
    an  = data.get("away", {}).get("name", "?")
    hs  = data.get("home", {}).get("scores", {}).get("fulltime", "?")
    aws = data.get("away", {}).get("scores", {}).get("fulltime", "?")
    print(f"    ✓  {hn} {hs}–{aws} {an}  ({len(data.get('events',[]))} events)")
    return True

# ---------------------------------------------------------------------------
# ASSET GENERATION (incremental — only new/changed matches)
# ---------------------------------------------------------------------------
def generate_assets(match_ids=None):
    """Regenerate assets. If match_ids given, only those; else all."""
    script = os.path.join(ROOT, "generate_all_assets.py")
    if match_ids:
        # Pass specific IDs via env var so generate_all_assets can filter
        env_val = ",".join(str(i) for i in match_ids)
        env = {**os.environ, "PIPELINE_MATCH_IDS": env_val}
        subprocess.run([sys.executable, script], env=env)
    else:
        subprocess.run([sys.executable, script])

# ---------------------------------------------------------------------------
# WEBSITE BUILD
# ---------------------------------------------------------------------------
def build_site():
    subprocess.run([sys.executable, os.path.join(ROOT, "build_website.py")])

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BCNProject Pipeline")
    parser.add_argument("match_ids", nargs="*", help="Specific WhoScored match IDs to scrape")
    parser.add_argument("--assets-only",  action="store_true", help="Skip scraping, just assets + build")
    parser.add_argument("--build-only",   action="store_true", help="Just rebuild the website")
    parser.add_argument("--no-rebuild",   action="store_true", help="Don't rebuild website after scraping")
    parser.add_argument("--force",        action="store_true", help="Re-scrape even if match already cached")
    parser.add_argument("--team",         default="65",        help="WhoScored team ID (default 65 = Barcelona)")
    args = parser.parse_args()

    print("=" * 55)
    print("  BCNProject Pipeline")
    print("=" * 55)

    # --- Build only ---
    if args.build_only:
        print("\n[Build] Rebuilding website...")
        build_site()
        return

    # --- Assets + build only ---
    if args.assets_only:
        print("\n[Assets] Regenerating all assets...")
        generate_assets()
        print("\n[Build] Rebuilding website...")
        build_site()
        return

    # --- Scraping ---
    existing = {
        f.split("_")[1]
        for f in os.listdir(DATA_DIR)
        if f.startswith("match_") and f.endswith("_cache.json")
    }
    print(f"\nCurrently cached: {len(existing)} matches")

    understat = fetch_understat()
    driver    = make_driver()
    scraped_ids = []

    try:
        if args.match_ids:
            # Scrape specific IDs provided on CLI
            print(f"\n[Scrape] {len(args.match_ids)} specific match(es)")
            for mid in args.match_ids:
                ok = scrape_match(driver, mid, understat, force=args.force)
                if ok:
                    scraped_ids.append(mid)
                time.sleep(10)
        else:
            # Discover all missing from fixture pages
            fixture_pages = DEFAULT_FIXTURE_PAGES
            if args.team != "65":
                print(f"  Custom team {args.team} — using generic La Liga fixtures page only")
                fixture_pages = {
                    "La Liga": f"https://www.whoscored.com/Teams/{args.team}/Fixtures/"
                }

            missing_by_comp = {}
            seen = set()
            for comp, url in fixture_pages.items():
                ids = discover_ids(driver, url, comp)
                new = [i for i in ids if i not in existing and i not in seen]
                if new:
                    missing_by_comp[comp] = new
                    seen.update(new)
                time.sleep(5)

            total = sum(len(v) for v in missing_by_comp.values())
            print(f"\nMissing matches: {total}")
            for comp, ids in missing_by_comp.items():
                print(f"  {comp}: {len(ids)}")

            if not total:
                print("All matches already cached!")
                driver.quit()
                if not args.no_rebuild:
                    print("\n[Build] Rebuilding website...")
                    build_site()
                return

            for comp, ids in missing_by_comp.items():
                print(f"\n--- Scraping {comp} ---")
                for mid in ids:
                    ok = scrape_match(driver, mid, understat, comp_hint=comp, force=args.force)
                    if ok:
                        scraped_ids.append(mid)
                    time.sleep(12)

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print(f"\n{'='*55}")
    print(f"Scraped: {len(scraped_ids)} new matches")

    if scraped_ids:
        print("\n[Assets] Regenerating assets for new matches...")
        generate_assets(scraped_ids)

        if not args.no_rebuild:
            print("\n[Build] Rebuilding website...")
            build_site()
            print(f"\n✓ Done!  Open:  assets/html/index.html")
    else:
        print("No new data — nothing to regenerate.")

if __name__ == "__main__":
    main()
