"""
Generate clean placeholder shield badges for all 48 WC2026 qualified nations.
White shield, dark border, 3-letter abbreviation text.
Drop real PNG named <Team Name>.png into team_logos/wc2026/ to override.

Run:  python wc2026/generate_placeholders.py [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.path as mpath
import numpy as np

_REPO = Path(__file__).resolve().parents[1]
OUT_DIR = _REPO / "team_logos" / "wc2026"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Official 48 WC2026 participants — 3-letter FIFA/IOC code
ABBREVS: dict[str, str] = {
    # AFC (9)
    "Australia":           "AUS",
    "Iran":                "IRN",
    "Iraq":                "IRQ",
    "Japan":               "JPN",
    "Jordan":              "JOR",
    "Qatar":               "QAT",
    "Saudi Arabia":        "KSA",
    "South Korea":         "KOR",
    "Uzbekistan":          "UZB",
    # CAF (10)
    "Algeria":             "ALG",
    "Cape Verde":          "CPV",
    "DR Congo":            "COD",
    "Cote d'Ivoire":       "CIV",
    "Egypt":               "EGY",
    "Ghana":               "GHA",
    "Morocco":             "MAR",
    "Senegal":             "SEN",
    "South Africa":        "RSA",
    "Tunisia":             "TUN",
    # CONCACAF (6)
    "Canada":              "CAN",
    "Curacao":             "CUW",
    "Haiti":               "HAI",
    "Mexico":              "MEX",
    "Panama":              "PAN",
    "USA":                 "USA",
    # CONMEBOL (6)
    "Argentina":           "ARG",
    "Brazil":              "BRA",
    "Colombia":            "COL",
    "Ecuador":             "ECU",
    "Paraguay":            "PAR",
    "Uruguay":             "URU",
    # OFC (1)
    "New Zealand":         "NZL",
    # UEFA (16)
    "Austria":             "AUT",
    "Belgium":             "BEL",
    "Bosnia-Herzegovina":  "BIH",
    "Croatia":             "CRO",
    "Czechia":             "CZE",
    "England":             "ENG",
    "France":              "FRA",
    "Germany":             "GER",
    "Netherlands":         "NED",
    "Norway":              "NOR",
    "Portugal":            "POR",
    "Scotland":            "SCO",
    "Spain":               "ESP",
    "Sweden":              "SWE",
    "Turkey":              "TUR",
}


def _shield_path() -> mpath.Path:
    verts = np.array([
        [0.10, 0.97],
        [0.90, 0.97],
        [0.90, 0.38],
        [0.50, 0.03],
        [0.10, 0.38],
        [0.10, 0.97],
    ])
    codes = ([mpath.Path.MOVETO]
             + [mpath.Path.LINETO] * 4
             + [mpath.Path.CLOSEPOLY])
    return mpath.Path(verts, codes)


def make_badge(name: str, force: bool = False) -> None:
    dest = OUT_DIR / f"{name}.png"
    if dest.exists() and not force:
        return

    abbr = ABBREVS.get(name, name[:3].upper())

    fig = plt.figure(figsize=(2.0, 2.0), dpi=100)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_facecolor("none")

    shield = _shield_path()
    ax.add_patch(mpatches.PathPatch(shield, facecolor="#FFFFFF", edgecolor="none", zorder=1))
    ax.add_patch(mpatches.PathPatch(shield, facecolor="none", edgecolor="#222222",
                                    linewidth=3.0, zorder=5))
    ax.text(0.50, 0.55, abbr, ha="center", va="center",
            fontsize=22, fontweight="bold", color="#111111", zorder=6)

    plt.savefig(dest, dpi=100, transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def make_all_badges(force: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ABBREVS:
        make_badge(name, force=force)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing badge files")
    args = parser.parse_args()

    print(f"Generating {len(ABBREVS)} WC2026 badge(s) → {OUT_DIR}\n")
    for name in ABBREVS:
        make_badge(name, force=args.force)
        print(f"  ✓ {name}")
    print(f"\nDone. Total: {len(list(OUT_DIR.glob('*.png')))} PNG files.")
    print("Drop real PNG files into team_logos/wc2026/ to override placeholders.")
