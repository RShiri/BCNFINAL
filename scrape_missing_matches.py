"""
Scrape ALL missing Barcelona 2025/26 matches from WhoScored.
Covers La Liga, UCL, Copa del Rey and Supercopa de España.

Run:  py scrape_missing_matches.py
Requires: undetected-chromedriver  (pip install undetected-chromedriver)
          beautifulsoup4            (pip install beautifulsoup4)

The script:
  1. Opens each WhoScored competition-fixtures page for Barcelona
  2. Collects every match ID not yet cached in assets/data/
  3. Scrapes the missing matches one by one (handles CAPTCHA manually)
  4. Attaches Understat xG where available
  5. Regenerates all assets + rebuilds the website automatically
"""

import os, json, re, time, subprocess, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')
import undetected_chromedriver as uc
from bs4 import BeautifulSoup

ROOT     = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "assets", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# WhoScored fixtures pages for each competition Barcelona plays in
# These show past results + upcoming fixtures for the selected team
FIXTURE_PAGES = {
    "La Liga":            "https://www.whoscored.com/Teams/65/Fixtures/Spain-Barcelona",
    "UCL":                "https://www.whoscored.com/Teams/65/Fixtures/Europe-Champions-League-Barcelona",
    "Copa del Rey":       "https://www.whoscored.com/Teams/65/Fixtures/Spain-Copa-del-Rey-Barcelona",
    "Supercopa":          "https://www.whoscored.com/Teams/65/Fixtures/Spain-Supercopa-de-Espana-Barcelona",
}

# Saudi venue names → Supercopa tag override
SAUDI_VENUES = {"king fahd", "king abdullah", "jeddah", "riyadh", "lusail", "saudi"}

# Copa del Rey lower-division opponents (helps competition detection later)
COPA_LOWER_TEAMS = {
    "real oviedo", "elche", "racing santander", "racing ferrol", "cd mirandes",
    "deportivo de la coruna", "sd huesca", "real valladolid", "levante",
    "cd leganes", "albacete", "fc cartagena", "burgos cf"
}

# ---------------------------------------------------------------------------
def setup_driver():
    opts = uc.ChromeOptions()
    opts.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=opts)
    return driver

# ---------------------------------------------------------------------------
def fetch_understat_xg():
    print("Fetching Understat xG data for Barcelona 2025/26 ...")
    url = "https://understat.com/team/Barcelona/2025"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")
        m = re.search(r"var datesData\s*=\s*JSON\.parse\('(.+?)'\);", html)
        if m:
            raw = m.group(1).encode("utf-8").decode("unicode_escape")
            matches = json.loads(raw)
            out = {e["datetime"][:10]: e for e in matches if e.get("isResult")}
            print(f"  Got {len(out)} Understat results")
            return out
    except Exception as e:
        print(f"  Understat fetch failed: {e}")
    return {}

# ---------------------------------------------------------------------------
def discover_ids_from_page(driver, url, comp_name, wait=25):
    """Navigate to a WhoScored fixtures page and return all match IDs found."""
    print(f"\n  Opening {comp_name} page...")
    print(f"  {url}")
    driver.get(url)
    print(f"  Waiting {wait}s (solve CAPTCHA if shown)...")
    time.sleep(wait)

    html = driver.page_source
    ids = re.findall(r'/[Mm]atches/(\d+)/(?:[Ll]ive|[Mm]atch[Rr]eport)', html)
    unique = list(dict.fromkeys(ids))
    print(f"  Found {len(unique)} match IDs for {comp_name}")
    return unique

# ---------------------------------------------------------------------------
def scrape_one(driver, match_id, understat_by_date, comp_hint=""):
    url = f"https://www.whoscored.com/Matches/{match_id}/Live"
    print(f"\n  [{match_id}] {comp_hint}  →  {url}")
    driver.get(url)

    found = False
    for i in range(90):
        html = driver.page_source
        if "matchCentreData" in html:
            found = True
            break
        if i % 15 == 0 and i > 0:
            print(f"    Still waiting... {i}s (solve CAPTCHA if needed)")
        time.sleep(1)

    if not found:
        print(f"    TIMEOUT — skipping {match_id}")
        return False

    soup = BeautifulSoup(html, "html.parser")
    script = None
    for s in soup.find_all("script"):
        if s.string and "matchCentreData:" in s.string:
            script = s.string
            break
    if not script:
        print(f"    Script block not found for {match_id}")
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

    # Attach Understat xG
    date_str = str(data.get("startDate", ""))[:10]
    us = understat_by_date.get(date_str)
    if us:
        data["understat"] = us
        print(f"    Understat xG: h={us['xG']['h']}  a={us['xG']['a']}")

    # Tag competition from hint
    if comp_hint:
        data["_competition"] = comp_hint

    # Auto-detect Supercopa by Saudi venue
    venue = str(data.get("venueName", "")).lower()
    if any(v in venue for v in SAUDI_VENUES):
        data["_competition"] = "Supercopa"
        print(f"    → Supercopa detected (venue: {data.get('venueName')})")

    out = os.path.join(DATA_DIR, f"match_{match_id}_cache.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    hn  = data.get("home", {}).get("name", "?")
    an  = data.get("away", {}).get("name", "?")
    hs  = data.get("home", {}).get("scores", {}).get("fulltime", "?")
    aws = data.get("away", {}).get("scores", {}).get("fulltime", "?")
    n   = len(data.get("events", []))
    print(f"    ✓  {hn} {hs}-{aws} {an}  ({n} events)")
    return True

# ---------------------------------------------------------------------------
def main():
    existing = {
        f.split("_")[1]
        for f in os.listdir(DATA_DIR)
        if f.startswith("match_") and f.endswith("_cache.json")
    }
    print(f"Already cached: {len(existing)} matches")

    understat = fetch_understat_xg()
    driver    = setup_driver()

    # Collect missing IDs per competition
    missing_by_comp = {}   # comp_name → [match_id, ...]
    all_seen = set()

    try:
        for comp_name, url in FIXTURE_PAGES.items():
            ids = discover_ids_from_page(driver, url, comp_name)
            new_ids = [i for i in ids if i not in existing and i not in all_seen]
            if new_ids:
                missing_by_comp[comp_name] = new_ids
                all_seen.update(new_ids)
                print(f"  → {len(new_ids)} new IDs for {comp_name}: {new_ids}")
            else:
                print(f"  → No new IDs for {comp_name}")
            time.sleep(5)

        total_missing = sum(len(v) for v in missing_by_comp.values())
        print(f"\n{'='*50}")
        print(f"Total missing matches: {total_missing}")
        for comp, ids in missing_by_comp.items():
            print(f"  {comp}: {len(ids)} matches")

        if not total_missing:
            print("All matches already cached!")
            return

        scraped = 0
        for comp_name, ids in missing_by_comp.items():
            print(f"\n--- Scraping {comp_name} ({len(ids)} matches) ---")
            for match_id in ids:
                ok = scrape_one(driver, match_id, understat, comp_hint=comp_name)
                if ok:
                    scraped += 1
                time.sleep(12)

    finally:
        driver.quit()

    print(f"\n{'='*50}")
    print(f"Scraped {scraped} new matches.")

    if scraped > 0:
        print("\nRegenerating all assets...")
        subprocess.run(["py", os.path.join(ROOT, "generate_all_assets.py")])
        print("Rebuilding website...")
        subprocess.run(["py", os.path.join(ROOT, "build_website.py")])
        print("\n✓ Done! Open:  assets/html/index.html")
    else:
        print("No new matches were scraped successfully.")

if __name__ == "__main__":
    main()
