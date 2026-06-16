# WC2026 Demo Renders

This folder showcases the World Cup 2026 dashboard output.

- `json/` - match data in the wc2026 schema
- `png/`  - rendered dashboards (country badges, pass networks, shot maps, stats)

## IMPORTANT: this is DEMO / placeholder data

Every file here was generated from **synthetic or sample data**, not real
WhoScored scrapes. For example `2026_06_16_France_vs_Senegal` shows a fabricated
score line - it is **not** the real result.

Real World Cup data cannot be scraped from a server/sandbox: WhoScored is behind
Cloudflare and FotMob's JSON API is dead. Real games must be scraped from a
desktop session where the Cloudflare CAPTCHA can be solved by hand.

## How to generate REAL game renders

From the repo root, run the WhoScored scraper with the match's WhoScored ID
(visible browser opens - solve the CAPTCHA if shown):

```
py -m wc2026.scrape_wc --ws-id <WHOSCORED_MATCH_ID> --stage "Group I"
```

It will:
1. scrape the real event stream from WhoScored,
2. convert it to the wc2026 schema (computing xG, possession, shots, passes,
   duels, etc. from the events),
3. save `wc2026/matches/<date>_<Home>_vs_<Away>.json`,
4. render `wc2026/output/<date>_<Home>_vs_<Away>.png` with country badges.

To re-render from an already-saved raw cache without a browser:

```
py -m wc2026.scrape_wc --from-cache wc2026/matches/match_<id>_cache.json --stage "Group I"
```

Copy the resulting real JSON/PNG here to replace the demo placeholders.
