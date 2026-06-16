"""
Generate clean placeholder shield-crest badges for all 48 WC2026 nations.
Each badge is a white/neutral shield with 3-letter abbreviation — drop the real
PNG (named <Team Name>.png) into team_logos/wc2026/ to override.

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

# 3-letter abbreviations for every WC2026 participant + common extras
ABBREVS: dict[str, str] = {
    # Group A
    "USA":              "USA",
    "Mexico":           "MEX",
    "Panama":           "PAN",
    "Honduras":         "HON",
    # Group B
    "Canada":           "CAN",
    "Morocco":          "MAR",
    "Portugal":         "POR",
    "Argentina":        "ARG",
    # Group C
    "Germany":          "GER",
    "Japan":            "JPN",
    "Senegal":          "SEN",
    "Costa Rica":       "CRC",
    # Group D
    "Spain":            "ESP",
    "Croatia":          "CRO",
    "Australia":        "AUS",
    "Algeria":          "ALG",
    # Group E
    "France":           "FRA",
    "Netherlands":      "NED",
    "Ecuador":          "ECU",
    "Saudi Arabia":     "KSA",
    # Group F
    "Brazil":           "BRA",
    "England":          "ENG",
    "Serbia":           "SRB",
    "South Korea":      "KOR",
    # Group G
    "Uruguay":          "URU",
    "Belgium":          "BEL",
    "Tunisia":          "TUN",
    "Colombia":         "COL",
    # Group H
    "Switzerland":      "SUI",
    "Chile":            "CHI",
    "Poland":           "POL",
    "Romania":          "ROU",
    # Group I
    "Italy":            "ITA",
    "Nigeria":          "NGA",
    "Paraguay":         "PAR",
    "Indonesia":        "INA",
    # Group J
    "Ghana":            "GHA",
    "Guatemala":        "GUA",
    "Qatar":            "QAT",
    # Group K
    "Denmark":          "DEN",
    "Iran":             "IRN",
    "New Zealand":      "NZL",
    "Cameroon":         "CMR",
    # Group L
    "South Africa":     "RSA",
    "Greece":           "GRE",
    "Ukraine":          "UKR",
    "Venezuela":        "VEN",
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

    DPI = 100
    fig = plt.figure(figsize=(2.0, 2.0), dpi=DPI)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_facecolor("none")

    shield = _shield_path()

    # White fill
    ax.add_patch(mpatches.PathPatch(
        shield, facecolor="#FFFFFF", edgecolor="none", zorder=1))

    # Dark border
    ax.add_patch(mpatches.PathPatch(
        shield, facecolor="none",
        edgecolor="#222222", linewidth=3.0, zorder=5))

    # Abbreviation text
    ax.text(0.50, 0.55, abbr,
            ha="center", va="center",
            fontsize=22, fontweight="bold",
            color="#111111", zorder=6)

    plt.savefig(dest, dpi=DPI, transparent=True,
                bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def make_all_badges(force: bool = False) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ABBREVS:
        make_badge(name, force=force)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing badge files")
    args = parser.parse_args()

    teams = list(ABBREVS.keys())
    print(f"Generating {len(teams)} shield crests → {OUT_DIR}\n")
    for t in teams:
        make_badge(t, force=args.force)
        print(f"  ✓ {t}")
    print(f"\nDone. Drop real PNG files in {OUT_DIR}/ to override.")
