"""
Motor de props de STRIKEOUTS de pitcher — el mercado menos eficiente de MLB.

Por qué props y no líneas de juego: las casas priecean ML y totales casi perfecto
(un modelo estadístico rara vez les gana). Los props de jugador reciben mucho menos
esfuerzo de pricing, así que ahí sí puede haber edge real.

Lección clave (2026-07-06): el error #1 del modelo es sobre-estimar los INNINGS.
Shane Drohan (swingman) proyectaba "+30% edge" en OVER solo porque el modelo asumió
8 IP; en realidad lanza ~4.5 como swingman y el edge era falso. La casa YA sabe el
rol. Correcciones:
  - Innings realistas: 5.5 titular, 4.5 swingman (más apariciones que 1.5x aperturas).
  - Rechazo de edge > 0.20 (probable error de innings/rol, no value).
  - Requiere muestra >= 40 IP.
"""
import numpy as np
from scipy.stats import poisson

LIGA_KPCT = 0.225   # K% de bateo promedio MLB


def implied_innings(is_swingman: bool) -> float:
    """Innings esperados según rol. La casa los conoce; el modelo debe respetarlos."""
    return 4.5 if is_swingman else 5.5


def project_strikeouts(k9: float, rival_kpct: float, is_swingman: bool) -> float:
    """μ de strikeouts = (K/9 / 9) * innings_esperados * ajuste_K%_rival."""
    innings = implied_innings(is_swingman)
    return (k9 / 9.0) * innings * (rival_kpct / LIGA_KPCT)


def evaluate_k_prop(k9, gs, games, ip, rival_kpct, line, over_odds, under_odds,
                    min_conf=0.62, min_edge=0.05, max_edge=0.20,
                    min_ip=40, min_odds=1.70):
    """
    Evalúa un prop O/U de strikeouts contra la línea real del mercado.
    Devuelve dict con el pick si pasa los filtros, o None.

    max_edge=0.20: un edge mayor casi siempre es error de innings/rol, no value
    (los props son ineficientes pero no TANTO). min_ip=40: muestra suficiente.
    """
    if ip < min_ip or not over_odds or not under_odds:
        return None
    is_swing = games > gs * 1.5 and gs > 0
    mu = project_strikeouts(k9, rival_kpct, is_swing)

    kf = int(np.floor(line))
    p_over = 1.0 - poisson.cdf(kf, mu)
    p_under = poisson.cdf(kf, mu)

    novig_o = (1 / over_odds) / ((1 / over_odds) + (1 / under_odds))
    novig_u = (1 / under_odds) / ((1 / over_odds) + (1 / under_odds))

    side = "OVER" if p_over > p_under else "UNDER"
    p = max(p_over, p_under)
    odds = over_odds if side == "OVER" else under_odds
    edge = (p_over - novig_o) if side == "OVER" else (p_under - novig_u)

    if p >= min_conf and min_edge <= edge <= max_edge and odds >= min_odds:
        return {"market": "PROP-K", "side": side, "line": line,
                "model_p": round(p, 4), "odds": odds, "edge": round(edge, 4),
                "mu_k": round(mu, 2), "role": "swing" if is_swing else "SP"}
    return None
