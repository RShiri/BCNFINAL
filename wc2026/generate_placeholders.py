"""
Generate colored placeholder flag badges for WC2026 nations.
Used when real flag images can't be downloaded.
Run this from the BCNFINAL root:  python wc2026/generate_placeholders.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from wc2026.team_colors import WC2026_TEAM_COLORS, get_team_colors

OUT_DIR = _REPO / "team_logos" / "wc2026"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ABBREVS: dict[str, str] = {
    "Mexico": "MEX", "South Africa": "RSA", "Czechia": "CZE", "Ghana": "GHA",
    "South Korea": "KOR", "Canada": "CAN", "Bosnia-Herzegovina": "BIH",
    "Scotland": "SCO", "Bolivia": "BOL", "Australia": "AUS", "Nigeria": "NGA",
    "Iran": "IRN", "USA": "USA", "Morocco": "MAR", "Ukraine": "UKR",
    "Paraguay": "PAR", "Brazil": "BRA", "Netherlands": "NED", "Croatia": "CRO",
    "Panama": "PAN", "Germany": "GER", "Spain": "ESP", "Switzerland": "SUI",
    "Qatar": "QAT", "France": "FRA", "Senegal": "SEN", "Iraq": "IRQ",
    "Norway": "NOR", "Belgium": "BEL", "Egypt": "EGY", "Uruguay": "URU",
    "Cape Verde": "CPV", "Saudi Arabia": "KSA", "Haiti": "HAI",
    "New Zealand": "NZL", "Japan": "JPN", "Argentina": "ARG", "Algeria": "ALG",
    "Austria": "AUT", "Jordan": "JOR", "Portugal": "POR", "Colombia": "COL",
    "Uzbekistan": "UZB", "DR Congo": "COD", "England": "ENG",
}


def make_badge(name: str) -> None:
    dest = OUT_DIR / f"{name}.png"
    if dest.exists():
        return

    colors = get_team_colors(name, fallback_home=True)
    primary   = colors["primary"]
    secondary = colors.get("secondary", "#ffffff")
    abbr = ABBREVS.get(name, name[:3].upper())

    fig, ax = plt.subplots(figsize=(1.6, 1.0), dpi=100)
    fig.patch.set_facecolor(primary)
    ax.set_facecolor(primary)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Colored band (secondary color strip at top)
    ax.add_patch(mpatches.Rectangle((0, 0.72), 1, 0.28, color=secondary, zorder=1))

    # Abbreviation text
    r, g, b = tuple(int(primary.lstrip("#")[i:i+2], 16) / 255 for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    txt_color = "#ffffff" if lum < 0.45 else "#111111"

    ax.text(0.5, 0.35, abbr,
            ha="center", va="center",
            fontsize=22, fontweight="bold",
            color=txt_color, zorder=2)

    plt.savefig(dest, bbox_inches="tight", pad_inches=0, dpi=100)
    plt.close(fig)
    print(f"  badge: {name}")


if __name__ == "__main__":
    teams = list(ABBREVS.keys())
    print(f"Generating {len(teams)} placeholder badges → {OUT_DIR}\n")
    for t in teams:
        make_badge(t)
    print("\nDone. Run download_badges.py to replace with real flag images.")
