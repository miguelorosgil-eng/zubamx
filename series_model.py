"""
Modelo de series para playoffs NBA/NHL.
Ajusta probabilidades según el marcador de la serie y el contexto.
"""
import re
import requests

# Ajustes de probabilidad por marcador de serie (histórico NBA/NHL)
# Fuente: análisis histórico de series al mejor de 7
SERIES_ADJUSTMENTS = {
    # (wins_home, wins_away): (adj_home, adj_away)
    # Serie empatada
    (0, 0): (0.00,  0.00),   # inicio, sin ajuste
    (1, 1): (0.00,  0.00),   # empatada, sin ajuste
    (2, 2): (0.00,  0.00),   # empatada, sin ajuste
    (3, 3): (0.00,  0.00),   # game 7, sin ajuste (presión igual)
    # Local lidera
    (1, 0): (+0.03, -0.03),  # lidera 1-0: ligera ventaja psicológica
    (2, 0): (+0.06, -0.06),  # lidera 2-0: impulso significativo
    (3, 0): (+0.10, -0.10),  # lidera 3-0: remontada histórica
    (3, 1): (+0.05, -0.05),  # lidera 3-1: un pie en la final
    (3, 2): (+0.02, -0.02),  # lidera 3-2: ventaja leve
    # Visitante lidera
    (0, 1): (-0.03, +0.03),
    (0, 2): (-0.06, +0.06),
    (0, 3): (-0.10, +0.10),
    (1, 3): (-0.05, +0.05),
    (2, 3): (-0.02, +0.02),
}


def _fetch_series_status(url: str) -> dict:
    """
    Helper interno: descarga scoreboard ESPN y extrae marcadores de serie.
    Devuelve {(team_home, team_away): (wins_home, wins_away)} o {}
    """
    try:
        resp = requests.get(url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return {}

    result = {}
    events = data.get("events", [])
    for event in events:
        competitions = event.get("competitions", [])
        for comp in competitions:
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            # Identificar home y away
            home_comp = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_comp = next((c for c in competitors if c.get("homeAway") == "away"), None)
            if not home_comp or not away_comp:
                continue

            home_name = home_comp.get("team", {}).get("displayName", "")
            away_name = away_comp.get("team", {}).get("displayName", "")
            if not home_name or not away_name:
                continue

            # Buscar series record en seriesSummary o records
            series_summary = comp.get("seriesSummary", {})
            series_text = series_summary.get("seriesSummaryText", "")

            wins_home, wins_away = 0, 0
            # Intentar parsear "X-Y" en el texto del resumen de serie
            match = re.search(r"(\d+)-(\d+)", series_text)
            if match:
                # El texto puede ser "Team leads 2-1" o "Tied 1-1"
                # Necesitamos saber quién lidera para asignar correctamente
                leads_match = re.search(
                    r"(\w[\w\s]+?)\s+leads\s+(\d+)-(\d+)", series_text, re.IGNORECASE
                )
                tied_match = re.search(
                    r"tied\s+(\d+)-(\d+)", series_text, re.IGNORECASE
                )
                if leads_match:
                    leader = leads_match.group(1).strip().lower()
                    w1 = int(leads_match.group(2))
                    w2 = int(leads_match.group(3))
                    home_lower = home_name.lower()
                    # Si el líder coincide con el equipo home
                    if any(part in leader for part in home_lower.split()[-2:]):
                        wins_home, wins_away = w1, w2
                    else:
                        wins_home, wins_away = w2, w1
                elif tied_match:
                    wins_home = wins_away = int(tied_match.group(1))
                else:
                    wins_home = int(match.group(1))
                    wins_away = int(match.group(2))

                result[(home_name, away_name)] = (wins_home, wins_away)

    return result


def fetch_nba_series_status() -> dict:
    """
    Obtiene el marcador actual de series de playoffs NBA desde ESPN API.
    URL: https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard
    Parsea series records si están disponibles.
    Devuelve: {(team_home, team_away): (wins_home, wins_away)} o {}
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
    return _fetch_series_status(url)


def fetch_nhl_series_status() -> dict:
    """
    Igual para NHL.
    URL: https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard"
    return _fetch_series_status(url)


def _fuzzy_match(name: str, candidates: list) -> str | None:
    """
    Fuzzy match simple: busca si alguna palabra del nombre coincide
    con palabras en algún candidato. Devuelve el candidato más parecido o None.
    """
    name_lower = name.lower()
    name_words = set(name_lower.split())

    best = None
    best_score = 0
    for cand in candidates:
        cand_lower = cand.lower()
        cand_words = set(cand_lower.split())
        overlap = len(name_words & cand_words)
        # También verificar si el nombre está contenido o viceversa
        contains = name_lower in cand_lower or cand_lower in name_lower
        score = overlap + (2 if contains else 0)
        if score > best_score:
            best_score = score
            best = cand

    return best if best_score > 0 else None


def get_series_adjustment(home: str, away: str,
                           series_status: dict) -> tuple[float, float, str]:
    """
    Dado el marcador de la serie, devuelve (adj_home, adj_away, summary).
    summary: "Serie 2-1 a favor de Knicks — ajuste +3% Knicks"
    Fuzzy match de nombres.
    """
    if not series_status:
        return 0.0, 0.0, "Sin datos de serie disponibles"

    # Construir lista de pares conocidos para fuzzy match
    all_pairs = list(series_status.keys())
    all_home_names = [p[0] for p in all_pairs]
    all_away_names = [p[1] for p in all_pairs]

    matched_home = _fuzzy_match(home, all_home_names)
    matched_away = _fuzzy_match(away, all_away_names)

    wins_h, wins_a = None, None

    # Buscar la combinación matcheada
    if matched_home and matched_away:
        key = (matched_home, matched_away)
        if key in series_status:
            wins_h, wins_a = series_status[key]

    # Si no encontramos la combinación exacta, intentar buscar cualquier par
    # que contenga a ambos equipos (en cualquier orden)
    if wins_h is None:
        for (h_key, a_key), (wh, wa) in series_status.items():
            h_match = _fuzzy_match(home, [h_key])
            a_match = _fuzzy_match(away, [a_key])
            if h_match and a_match:
                wins_h, wins_a = wh, wa
                break
            # Intentar orden invertido
            h_match2 = _fuzzy_match(home, [a_key])
            a_match2 = _fuzzy_match(away, [h_key])
            if h_match2 and a_match2:
                # Los roles están invertidos en los datos
                wins_h, wins_a = wa, wh
                break

    if wins_h is None:
        return 0.0, 0.0, f"No se encontró serie para {home} vs {away}"

    adj_home, adj_away = SERIES_ADJUSTMENTS.get((wins_h, wins_a), (0.0, 0.0))

    # Construir summary descriptivo
    if wins_h > wins_a:
        leader = home
        leader_wins, trailer_wins = wins_h, wins_a
        adj_pct = adj_home
    elif wins_a > wins_h:
        leader = away
        leader_wins, trailer_wins = wins_a, wins_h
        adj_pct = adj_away
    else:
        leader = None

    if leader:
        sign = "+" if adj_pct > 0 else ""
        summary = (
            f"Serie {leader_wins}-{trailer_wins} a favor de {leader} — "
            f"ajuste {sign}{adj_pct*100:.0f}% {leader}"
        )
    else:
        summary = f"Serie empatada {wins_h}-{wins_a} — sin ajuste"

    return float(adj_home), float(adj_away), summary


def adjust_series_probability(p_home: float, p_away: float,
                               adj_home: float, adj_away: float) -> tuple[float, float]:
    """Aplica ajuste y renormaliza."""
    p_home_adj = max(0.01, min(0.99, p_home + adj_home))
    p_away_adj = max(0.01, min(0.99, p_away + adj_away))
    total = p_home_adj + p_away_adj
    return p_home_adj / total, p_away_adj / total


def analyze_elimination_pressure(wins_h: int, wins_a: int) -> dict:
    """
    Analiza presión psicológica por eliminación.
    Retorna: {home_pressure: str, away_pressure: str, game_importance: float}
    game_importance: 1.0 normal, 1.5 match point, 2.0 game 7
    """
    total_wins = wins_h + wins_a

    # Determinar si alguno está en match point (3 victorias en serie al mejor de 7)
    home_match_point = wins_h == 3
    away_match_point = wins_a == 3
    game_7 = wins_h == 3 and wins_a == 3

    # Presión del equipo local
    if game_7:
        home_pressure = "MÁXIMA — Game 7, eliminación inmediata"
        away_pressure = "MÁXIMA — Game 7, eliminación inmediata"
        game_importance = 2.0
    elif home_match_point and not away_match_point:
        home_pressure = "BAJA — Un paso de cerrar la serie"
        away_pressure = "ALTA — En el borde de la eliminación"
        game_importance = 1.5
    elif away_match_point and not home_match_point:
        home_pressure = "ALTA — En el borde de la eliminación"
        away_pressure = "BAJA — Un paso de cerrar la serie"
        game_importance = 1.5
    elif wins_h == 0 and wins_a == 0:
        home_pressure = "NORMAL — Inicio de serie"
        away_pressure = "NORMAL — Inicio de serie"
        game_importance = 1.0
    elif wins_h == wins_a:
        home_pressure = "MODERADA — Serie empatada"
        away_pressure = "MODERADA — Serie empatada"
        game_importance = 1.2
    elif abs(wins_h - wins_a) == 1:
        if wins_h > wins_a:
            home_pressure = "BAJA — Lidera la serie"
            away_pressure = "MODERADA — Va por detrás"
        else:
            home_pressure = "MODERADA — Va por detrás"
            away_pressure = "BAJA — Lidera la serie"
        game_importance = 1.1
    else:
        # Diferencia de 2 victorias
        if wins_h > wins_a:
            home_pressure = "MUY BAJA — Domina la serie"
            away_pressure = "MUY ALTA — Necesita remontar"
        else:
            home_pressure = "MUY ALTA — Necesita remontar"
            away_pressure = "MUY BAJA — Domina la serie"
        game_importance = 1.3

    return {
        "home_pressure": home_pressure,
        "away_pressure": away_pressure,
        "game_importance": game_importance,
        "series_score": f"{wins_h}-{wins_a}",
        "games_played": total_wins,
    }
