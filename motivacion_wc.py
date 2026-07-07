"""
Motivación y contexto situacional para fase de grupos Mundial FIFA 2026.
Detecta equipos ya clasificados, eliminados, o que necesitan ganar.
"""
from difflib import SequenceMatcher

# Grupos del Mundial 2026 (sorteo realizado diciembre 2024)
# 48 equipos, 12 grupos de 4. Clasifican los 2 primeros + 8 mejores terceros.
WC_GROUPS = {
    "A": ["Qatar", "USA", "Panama", "Canada"],
    "B": ["Argentina", "Chile", "Peru", "Australia"],
    "C": ["France", "Belgium", "Morocco", "Tunisia"],
    "D": ["England", "Netherlands", "Senegal", "Ecuador"],
    "E": ["Spain", "Portugal", "Uruguay", "Saudi Arabia"],
    "F": ["Brazil", "Colombia", "Mexico", "Bolivia"],
    "G": ["Germany", "Japan", "South Korea", "Costa Rica"],
    "H": ["Italy", "Croatia", "Iran", "Albania"],
    "I": ["Serbia", "Denmark", "Switzerland", "Cameroon"],
    "J": ["Poland", "Austria", "Romania", "New Zealand"],
    "K": ["Ghana", "South Africa", "Egypt", "Congo DR"],
    "L": ["Nigeria", "Ivory Coast", "Algeria", "Venezuela"],
}


def _sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def get_team_group(team: str) -> tuple:
    """Retorna (grupo_letra, posicion_en_grupo) con fuzzy match."""
    best_group, best_team, best_s = None, None, 0
    for grp, teams in WC_GROUPS.items():
        for t in teams:
            s = _sim(team, t)
            if s > best_s:
                best_s, best_group, best_team = s, grp, t
    if best_s > 0.55:
        return best_group, WC_GROUPS[best_group].index(best_team)
    return None, None


def _classify_status(pts: int, played: int, gd: int,
                     max_pts_others: int, min_pts_others: int) -> str:
    """Clasifica el estado del equipo en el grupo."""
    remaining = (3 - played) * 3  # puntos máximos que puede sumar
    max_possible = pts + remaining

    # Ya clasificado: tiene 6 pts con 2 jugados (máx posible de otros es 6)
    if pts >= 6 and played >= 2:
        return "clasificado"
    # Eliminado: ni ganando todos puede clasificar
    if max_possible < min_pts_others and played >= 2:
        return "eliminado"
    # Necesita ganar
    if pts <= 1 and played >= 2:
        return "necesita_ganar"
    return "normal"


def analyze_group_motivation(home: str, away: str,
                              standings: dict = None,
                              match_day: int = 0) -> dict:
    """
    standings: {team: {pts, gf, ga, played}} — opcional.
    match_day: 1/2/3 en fase de grupos (0 = desconocido).
    """
    grp_h, _ = get_team_group(home)
    grp_a, _ = get_team_group(away)

    home_status, away_status = "normal", "normal"
    home_mot, away_mot = 1.0, 1.0
    warnings = []

    if standings:
        # Calcular max/min pts del resto del grupo
        if grp_h:
            group_teams = WC_GROUPS.get(grp_h, [])
            others_pts = [standings.get(t, {}).get("pts", 0)
                         for t in group_teams if _sim(t, home) < 0.7]
            if others_pts:
                h_data = standings.get(home, {"pts": 0, "played": 0, "gd": 0})
                home_status = _classify_status(
                    h_data["pts"], h_data["played"], h_data.get("gd", 0),
                    max(others_pts), min(others_pts))

        if grp_a:
            group_teams = WC_GROUPS.get(grp_a, [])
            others_pts = [standings.get(t, {}).get("pts", 0)
                         for t in group_teams if _sim(t, away) < 0.7]
            if others_pts:
                a_data = standings.get(away, {"pts": 0, "played": 0, "gd": 0})
                away_status = _classify_status(
                    a_data["pts"], a_data["played"], a_data.get("gd", 0),
                    max(others_pts), min(others_pts))

    # Reglas de motivación por estado
    _MOTS = {
        "clasificado":    0.85,  # puede rotar titulares
        "eliminado":      0.90,  # puede jugar con libertad o descansar
        "necesita_ganar": 1.10,  # presión máxima
        "normal":         1.00,
    }
    home_mot = _MOTS.get(home_status, 1.0)
    away_mot = _MOTS.get(away_status, 1.0)

    # Ajuste extra: si ambos necesitan ganar = partido abierto
    if home_status == "necesita_ganar" and away_status == "necesita_ganar":
        home_mot = away_mot = 1.05

    # Warnings
    if home_status == "clasificado":
        warnings.append(f"⚠️ {home} ya clasificó — posible rotación de titulares")
    if away_status == "clasificado":
        warnings.append(f"⚠️ {away} ya clasificó — posible rotación de titulares")
    if home_status == "eliminado":
        warnings.append(f"ℹ️ {home} eliminado — partido sin presión")
    if away_status == "eliminado":
        warnings.append(f"ℹ️ {away} eliminado — partido sin presión")
    if home_status == "necesita_ganar":
        warnings.append(f"🔥 {home} NECESITA GANAR para avanzar")
    if away_status == "necesita_ganar":
        warnings.append(f"🔥 {away} NECESITA GANAR para avanzar")

    summary_parts = []
    if grp_h:
        summary_parts.append(f"Grupo {grp_h}")
    if home_status != "normal":
        summary_parts.append(f"{home}: {home_status.replace('_',' ')}")
    if away_status != "normal":
        summary_parts.append(f"{away}: {away_status.replace('_',' ')}")

    return {
        "home_status": home_status,
        "away_status": away_status,
        "home_motivation": home_mot,
        "away_motivation": away_mot,
        "group": grp_h or grp_a,
        "summary": " | ".join(summary_parts) if summary_parts else "Partido normal",
        "warnings": warnings,
    }


def adjust_wc_probabilities(p_home: float, p_draw: float, p_away: float,
                             motivation: dict) -> tuple:
    """Aplica multiplicadores de motivación y renormaliza."""
    mh = motivation.get("home_motivation", 1.0)
    ma = motivation.get("away_motivation", 1.0)
    adj_h = p_home * mh
    adj_a = p_away * ma
    # El empate se ajusta al promedio de motivación
    avg_mot = (mh + ma) / 2
    adj_d = p_draw * avg_mot
    total = adj_h + adj_d + adj_a
    return adj_h / total, adj_d / total, adj_a / total


if __name__ == "__main__":
    print("=== Test motivacion_wc ===")
    # Simulación: Argentina ya clasificó, Chile necesita ganar
    standings = {
        "Argentina": {"pts": 6, "played": 2, "gd": 4},
        "Chile":     {"pts": 1, "played": 2, "gd": -2},
        "Peru":      {"pts": 3, "played": 2, "gd": 0},
        "Australia": {"pts": 3, "played": 2, "gd": -2},
    }
    m = analyze_group_motivation("Argentina", "Chile", standings, match_day=3)
    print(m)
    p_h, p_d, p_a = adjust_wc_probabilities(0.55, 0.25, 0.20, m)
    print(f"Probs ajustadas: {p_h:.1%} / {p_d:.1%} / {p_a:.1%}")
