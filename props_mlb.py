"""
Props de jugadores MLB — Strikeouts del pitcher y Hits+Total bases del bateador.
Modela con K/9 histórico del pitcher vs K% del lineup rival.
Fuente: MLB Stats API (gratis).
"""
import requests
import numpy as np
from scipy.stats import poisson

BASE = "https://statsapi.mlb.com/api/v1"

_CACHE = {}


def _get(path, params=None):
    url = BASE + path
    key = (url, str(sorted((params or {}).items())))
    if key in _CACHE:
        return _CACHE[key]
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    _CACHE[key] = data
    return data


def _pitcher_stats(pitcher_id: int, season: int) -> dict:
    """K/9, IP, ERA, WHIP del pitcher en la temporada."""
    try:
        data = _get(f"/people/{pitcher_id}/stats",
                    {"stats": "season", "group": "pitching", "season": season})
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            return {}
        s = splits[0]["stat"]
        ip = float(s.get("inningsPitched", 0) or 0)
        k = float(s.get("strikeOuts", 0) or 0)
        era = float(s.get("era", 4.5) or 4.5)
        whip = float(s.get("whip", 1.3) or 1.3)
        k9 = (k / ip * 9) if ip > 0 else 7.0
        return {"k9": k9, "ip": ip, "era": era, "whip": whip, "k": int(k)}
    except Exception:
        return {}


def _team_k_pct(team_id: int, season: int) -> float:
    """Porcentaje de strikeouts del lineup (como bateadores) en la temporada."""
    try:
        data = _get(f"/teams/{team_id}/stats",
                    {"stats": "season", "group": "hitting", "season": season})
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            return 0.22
        s = splits[0]["stat"]
        ab = float(s.get("atBats", 1) or 1)
        k = float(s.get("strikeOuts", 0) or 0)
        return k / ab if ab > 0 else 0.22
    except Exception:
        return 0.22


def _expected_innings(pitcher_stats: dict) -> float:
    """IP esperados para este inicio (cap en 6.0 para bullpen moderno)."""
    ip = pitcher_stats.get("ip", 0)
    era = pitcher_stats.get("era", 4.50)
    # Pitchers con ERA < 3.0 y >60 IP: esperamos 6+ innings
    if ip > 80 and era < 3.0:
        return 6.0
    elif ip > 60 and era < 4.0:
        return 5.5
    elif ip > 40 and era < 5.0:
        return 5.0
    else:
        return 4.5


def predict_pitcher_strikeouts(pitcher_id: int, rival_team_id: int,
                                season: int, line: float = 5.5) -> dict:
    """
    Predice strikeouts del pitcher vs un lineup rival.
    Modelo: K esperados = k9 * innings_esperados / 9 * ajuste_rival_k%
    line: línea de O/U ofrecida por el mercado (ej. 5.5)
    """
    stats = _pitcher_stats(pitcher_id, season)
    if not stats:
        return {}

    rival_kpct = _team_k_pct(rival_team_id, season)
    liga_avg_kpct = 0.225  # MLB average 2025

    innings = _expected_innings(stats)
    k9 = stats.get("k9", 7.0)

    # Ajustar por k% del lineup rival vs media de liga
    adjustment = rival_kpct / liga_avg_kpct
    mu_k = (k9 / 9.0) * innings * adjustment

    # Distribución Poisson para O/U
    k_floor = int(np.floor(line))
    p_over = 1.0 - poisson.cdf(k_floor, mu_k)
    p_under = poisson.cdf(k_floor, mu_k)

    return {
        "pitcher_id": pitcher_id,
        "mu_k": round(mu_k, 2),
        "innings_expected": round(innings, 1),
        "k9": round(k9, 2),
        "rival_kpct": round(rival_kpct, 3),
        "line": line,
        "p_over": round(p_over, 4),
        "p_under": round(p_under, 4),
        "recommendation": "OVER" if p_over > 0.58 else ("UNDER" if p_under > 0.58 else "NO PLAY"),
    }


def get_today_pitcher_props(probable_pitchers: list, season: int = 2026) -> list:
    """
    Dado el output de fetch_probable_pitchers(), genera props de K para cada starter.
    Filtra pitchers sin ID o sin línea disponible.
    """
    results = []
    for game in probable_pitchers:
        for side in ["home", "away"]:
            sp_id = game.get(f"{side}_sp_id")
            rival_side = "away" if side == "home" else "home"
            rival_id = game.get(f"{rival_side}_team_id")
            sp_name = game.get(f"{side}_sp", "?")
            era = game.get(f"era_{side}_sp")

            if not sp_id or not rival_id:
                continue

            prop = predict_pitcher_strikeouts(sp_id, rival_id, season)
            if prop:
                prop["pitcher"] = sp_name
                prop["era"] = era
                prop["team"] = game.get(side, "")
                prop["opponent"] = game.get(rival_side, "")
                results.append(prop)

    return results


def print_pitcher_props(props: list):
    """Imprime tabla de props de strikeouts."""
    if not props:
        print("  Sin props de strikeouts disponibles.")
        return
    print(f"\n  ⚾ PROPS STRIKEOUTS PITCHERS")
    print(f"  {'Pitcher':<24} {'ERA':>5} {'μK':>5} {'IP':>4} {'Línea':>6} {'Over':>6} {'Under':>6} {'Pick':>8}")
    print(f"  {'-'*75}")
    for p in sorted(props, key=lambda x: -max(x.get("p_over",0), x.get("p_under",0))):
        flag = "🔥" if max(p.get("p_over",0), p.get("p_under",0)) > 0.62 else "  "
        rec = p.get("recommendation", "NO PLAY")
        print(f"  {flag}{p.get('pitcher','?'):<22} {p.get('era') or '?':>5}  "
              f"{p.get('mu_k',0):>4.1f}  {p.get('innings_expected',0):>3.1f}  "
              f"{p.get('line',0):>5.1f}  {p.get('p_over',0):>5.0%}  "
              f"{p.get('p_under',0):>5.0%}  {rec:>8}")


if __name__ == "__main__":
    # Demo con pitcher hipotético
    print("Demo props_mlb.py — requiere IDs reales de pitcher y equipo")
    print("Ejecutar desde analisis_dia.py con datos reales del día")
