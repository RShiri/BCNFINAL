"""
FIFA World Cup 2026 – primary/secondary colors for all 48 qualified nations.
"""

WC2026_TEAM_COLORS: dict[str, dict[str, str]] = {
    # ── AFC (9) ──────────────────────────────────────────────────────────────
    "Australia":     {"primary": "#006B3F", "secondary": "#FFD700"},
    "Iran":          {"primary": "#239F40", "secondary": "#FFFFFF"},
    "Iraq":          {"primary": "#CE1126", "secondary": "#007A3D"},
    "Japan":         {"primary": "#003F8E", "secondary": "#FFFFFF"},
    "Jordan":        {"primary": "#007A3D", "secondary": "#CE1126"},
    "Qatar":         {"primary": "#8D1B3D", "secondary": "#FFFFFF"},
    "Saudi Arabia":  {"primary": "#006C35", "secondary": "#FFFFFF"},
    "South Korea":   {"primary": "#C60C30", "secondary": "#003478"},
    "Uzbekistan":    {"primary": "#1EB53A", "secondary": "#FFFFFF"},

    # ── CAF (10) ─────────────────────────────────────────────────────────────
    "Algeria":       {"primary": "#006233", "secondary": "#FFFFFF"},
    "Cape Verde":    {"primary": "#003893", "secondary": "#CF2027"},
    "DR Congo":      {"primary": "#007FFF", "secondary": "#F7D618"},
    "Cote d'Ivoire": {"primary": "#F77F00", "secondary": "#009A44"},
    "Egypt":         {"primary": "#CE1126", "secondary": "#FFFFFF"},
    "Ghana":         {"primary": "#000000", "secondary": "#FFFFFF"},
    "Morocco":       {"primary": "#C1272D", "secondary": "#006233"},
    "Senegal":       {"primary": "#00853F", "secondary": "#FDEF42"},
    "South Africa":  {"primary": "#007A4D", "secondary": "#FFB81C"},
    "Tunisia":       {"primary": "#E70013", "secondary": "#FFFFFF"},

    # ── CONCACAF (6) ─────────────────────────────────────────────────────────
    "Canada":        {"primary": "#FF0000", "secondary": "#FFFFFF"},
    "Curacao":       {"primary": "#002B7F", "secondary": "#F9E300"},
    "Haiti":         {"primary": "#00209F", "secondary": "#D21034"},
    "Mexico":        {"primary": "#006847", "secondary": "#FFFFFF"},
    "Panama":        {"primary": "#D21034", "secondary": "#FFFFFF"},
    "USA":           {"primary": "#002868", "secondary": "#BF0A30"},

    # ── CONMEBOL (6) ─────────────────────────────────────────────────────────
    "Argentina":     {"primary": "#74ACDF", "secondary": "#FFFFFF"},
    "Brazil":        {"primary": "#009C3B", "secondary": "#FFDF00"},
    "Colombia":      {"primary": "#FCD116", "secondary": "#003087"},
    "Ecuador":       {"primary": "#FFD100", "secondary": "#034EA2"},
    "Paraguay":      {"primary": "#D52B1E", "secondary": "#FFFFFF"},
    "Uruguay":       {"primary": "#6CACE4", "secondary": "#FFFFFF"},

    # ── OFC (1) ──────────────────────────────────────────────────────────────
    "New Zealand":   {"primary": "#000000", "secondary": "#FFFFFF"},

    # ── UEFA (16) ────────────────────────────────────────────────────────────
    "Austria":             {"primary": "#ED2939", "secondary": "#FFFFFF"},
    "Belgium":             {"primary": "#EF3340", "secondary": "#000000"},
    "Bosnia-Herzegovina":  {"primary": "#002395", "secondary": "#FFCD00"},
    "Croatia":             {"primary": "#FF0000", "secondary": "#FFFFFF"},
    "Czechia":             {"primary": "#D7141A", "secondary": "#FFFFFF"},
    "England":             {"primary": "#003090", "secondary": "#FFFFFF"},
    "France":              {"primary": "#002395", "secondary": "#FFFFFF"},
    "Germany":             {"primary": "#000000", "secondary": "#FFFFFF"},
    "Netherlands":         {"primary": "#FF6000", "secondary": "#FFFFFF"},
    "Norway":              {"primary": "#EF2B2D", "secondary": "#FFFFFF"},
    "Portugal":            {"primary": "#006600", "secondary": "#FF0000"},
    "Scotland":            {"primary": "#003DA5", "secondary": "#FFFFFF"},
    "Spain":               {"primary": "#C60B1E", "secondary": "#F1BF00"},
    "Sweden":              {"primary": "#006AA7", "secondary": "#FECC02"},
    "Turkey":              {"primary": "#E30A17", "secondary": "#FFFFFF"},

    # Aliases
    "United States": {"primary": "#002868", "secondary": "#BF0A30"},
    "IR Iran":       {"primary": "#239F40", "secondary": "#FFFFFF"},
    "Türkiye":       {"primary": "#E30A17", "secondary": "#FFFFFF"},
}


def get_team_colors(team_name: str, fallback_home: bool = True) -> dict[str, str]:
    """Return {'primary': hex, 'secondary': hex} for a team."""
    name_clean = team_name.strip()
    if name_clean in WC2026_TEAM_COLORS:
        return WC2026_TEAM_COLORS[name_clean]
    lower = name_clean.lower()
    for k, v in WC2026_TEAM_COLORS.items():
        if k.lower() == lower:
            return v
    return {"primary": "#a50044" if fallback_home else "#004d98", "secondary": "#FFFFFF"}
