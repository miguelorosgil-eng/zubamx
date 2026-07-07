"""
Lineup confirmado NBA — ajusta predicciones según jugadores ausentes.
Fuente: ESPN injury API (gratis).
"""
import requests
from difflib import SequenceMatcher

NBA_ALLSTARS = {
    "Victor Wembanyama", "Shai Gilgeous-Alexander", "Nikola Jokic",
    "Giannis Antetokounmpo", "Jayson Tatum", "LeBron James",
    "Stephen Curry", "Kevin Durant", "Luka Doncic", "Anthony Davis",
    "Ja Morant", "Trae Young", "Donovan Mitchell", "Tyrese Haliburton",
    "Joel Embiid", "Damian Lillard", "Karl-Anthony Towns",
    "Kawhi Leonard", "Paul George", "Devin Booker",
}

# Impacto estimado en probabilidad por baja de jugador clave
_ALLSTAR_IMPACT = 0.06   # un All-Star out = -6% prob
_STARTER_IMPACT = 0.04   # titular regular out = -4% prob


def _sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_allstar(name: str) -> bool:
    return any(_sim(name, s) > 0.82 for s in NBA_ALLSTARS)


def fetch_nba_lineup_status(date_str: str = None) -> dict:
    """
    Devuelve {team: {out:[nombres], questionable:[nombres]}} desde ESPN.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    out = {}
    for item in data.get("injuries", []):
        team = item.get("team", {}).get("displayName", "")
        if not team:
            continue
        outs, questionables = [], []
        for inj in item.get("injuries", []):
            player = inj.get("athlete", {}).get("displayName", "")
            status = inj.get("status", "").lower()
            if not player:
                continue
            if "out" in status or "injured reserve" in status or "day-to-day" in status:
                outs.append(player)
            elif "questionable" in status or "probable" in status:
                questionables.append(player)
        out[team] = {"out": outs, "questionable": questionables}
    return out


def estimate_lineup_impact(team: str, status: dict) -> float:
    """
    Retorna ajuste de probabilidad (negativo si hay bajas importantes).
    """
    info = status.get(team)
    if not info:
        # fuzzy match
        best, best_s = None, 0
        for t in status:
            s = _sim(team, t)
            if s > best_s:
                best, best_s = t, s
        if best_s > 0.6:
            info = status[best]
        else:
            return 0.0

    impact = 0.0
    for player in info.get("out", []):
        if _is_allstar(player):
            impact -= _ALLSTAR_IMPACT
        else:
            impact -= _STARTER_IMPACT
    for player in info.get("questionable", []):
        if _is_allstar(player):
            impact -= _ALLSTAR_IMPACT * 0.4  # 40% del impacto si es dudoso
    return impact


def get_lineup_adjusted_prob(home: str, away: str,
                              p_home: float, p_away: float,
                              lineup_status: dict) -> tuple:
    """
    Aplica impacto de lineup. Retorna (adj_p_home, adj_p_away, warnings).
    """
    warnings = []
    imp_h = estimate_lineup_impact(home, lineup_status)
    imp_a = estimate_lineup_impact(away, lineup_status)

    # Detectar bajas All-Star para warnings
    for team, side, imp in [(home, "home", imp_h), (away, "away", imp_a)]:
        info = lineup_status.get(team, {})
        for p in info.get("out", []):
            if _is_allstar(p):
                warnings.append(f"🚨 {p} OUT ({team}) — impacto {imp*100:+.0f}% prob")
        for p in info.get("questionable", []):
            if _is_allstar(p):
                warnings.append(f"⚠️ {p} QUESTIONABLE ({team})")

    adj_h = max(0.05, min(0.95, p_home + imp_h - imp_a))
    adj_a = max(0.05, min(0.95, p_away + imp_a - imp_h))
    total = adj_h + adj_a
    return adj_h / total, adj_a / total, warnings


def print_lineup_report(lineup_status: dict, teams: list = None):
    if not lineup_status:
        print("  Sin datos de lineup disponibles.")
        return
    targets = teams or list(lineup_status.keys())
    for team in targets:
        info = lineup_status.get(team, {})
        if not info.get("out") and not info.get("questionable"):
            continue
        outs = ", ".join(info.get("out", [])) or "—"
        qs   = ", ".join(info.get("questionable", [])) or "—"
        print(f"  {team}: OUT={outs} | Q={qs}")


if __name__ == "__main__":
    status = fetch_nba_lineup_status()
    print(f"Equipos con bajas: {len([t for t,v in status.items() if v['out']])}")
    print_lineup_report(status)
