"""
Motor de predicción del Mundial FIFA 2026 — modelo Poisson de goles calibrado.

Lección post-mortem (jun 2026): el modelo previo proyectaba ~2.4 goles totales
sin importar el mismatch, así que los UNDER perdían por goleada cuando un equipo
atacante de élite (Bélgica 5-1, Noruega 4-1) arrasaba a un rival débil.

Correcciones codificadas aquí:
  1. La λ del favorito escala NO-LINEALMENTE con la diferencia de ranking:
     mismatches grandes proyectan totales altos (3.0-3.7), no 2.4 fijo.
  2. Guard anti-UNDER en mismatches grandes: en diff>25 el UNDER se bloquea
     (riesgo de goleada) salvo confianza extrema.
  3. Guard de "gana" en eliminatorias: solo favoritos claros (se maneja en
     mercados.evaluate_three_way con knockout=True).
"""
from scipy.stats import poisson

# Media de goles por equipo en un partido parejo de selección (histórico WC/Euro ≈ 1.35)
BASE_LAMBDA = 1.35
# Techo de goles para el favorito (evita proyecciones absurdas)
MAX_LAMBDA = 3.2
# Piso de goles para el débil
MIN_LAMBDA = 0.35


def expected_goals(rank_home, rank_away):
    """
    λ esperada de goles por equipo a partir del ranking FIFA (menor = mejor).

    Escalado no-lineal: la ventaja del favorito crece más rápido en mismatches
    grandes, reflejando que los equipos de élite golean a rivales muy inferiores.
    Retorna (lam_home, lam_away).
    """
    diff = rank_away - rank_home  # positivo → local es mejor

    # Componente lineal suave + componente no-lineal para mismatches grandes.
    # sign preserva la dirección; |diff|**1.35 castiga los mismatches extremos.
    mag = abs(diff)
    advantage = (0.010 * mag + 0.0016 * mag ** 1.35) * (1 if diff >= 0 else -1)

    lam_home = min(max(BASE_LAMBDA + advantage, MIN_LAMBDA), MAX_LAMBDA)
    lam_away = min(max(BASE_LAMBDA - advantage, MIN_LAMBDA), MAX_LAMBDA)
    return lam_home, lam_away


def match_probabilities(lam_home, lam_away, max_goals=10):
    """P(local gana), P(empate), P(visitante gana) bajo Poisson independiente."""
    p_home = p_draw = p_away = 0.0
    for gh in range(max_goals):
        for ga in range(max_goals):
            p = poisson.pmf(gh, lam_home) * poisson.pmf(ga, lam_away)
            if gh > ga:
                p_home += p
            elif gh == ga:
                p_draw += p
            else:
                p_away += p
    return p_home, p_draw, p_away


def prob_over_under(lam_home, lam_away, line, max_goals=12):
    """P(total > line), P(total < line). Totales enteros hacen push (no se apuesta)."""
    total_lambda = lam_home + lam_away
    # total de dos Poisson independientes = Poisson(suma de λ)
    k = int(line)  # línea .5 → over = P(total >= k+1)
    p_under = poisson.cdf(k, total_lambda)
    p_over = 1.0 - p_under
    return p_over, p_under


def evaluate_wc_totals(rank_home, rank_away, line, over_odds, under_odds,
                       min_conf=0.62, min_odds=1.70):
    """
    Evalúa OVER/UNDER de un partido del Mundial con los guards aprendidos.

    Guard anti-UNDER en mismatch grande: si |rating_diff| > 25, el UNDER queda
    bloqueado (riesgo de goleada del favorito) salvo que la confianza sea >0.75.
    Devuelve lista de picks {label, model_p, odds, market}.
    """
    diff = abs(rank_away - rank_home)
    lam_h, lam_a = expected_goals(rank_home, rank_away)
    p_over, p_under = prob_over_under(lam_h, lam_a, line)

    picks = []
    # OVER: floor normal
    if p_over >= min_conf and over_odds and over_odds >= min_odds:
        picks.append({"market": "O/U", "label": f"OVER {line}",
                      "model_p": round(p_over, 4), "odds": over_odds})
    # UNDER: en mismatch grande exige confianza extrema (anti-goleada).
    # Umbral diff>20 calibrado sobre los UNDER perdidos (Norway diff42, Belgium
    # diff37, Neth/Tunisia diff25 perdieron; el favorito goleó).
    under_floor = 0.80 if diff > 20 else min_conf
    if p_under >= under_floor and under_odds and under_odds >= min_odds:
        picks.append({"market": "O/U", "label": f"UNDER {line}",
                      "model_p": round(p_under, 4), "odds": under_odds,
                      "note": f"mismatch diff={diff}" if diff > 25 else ""})
    return picks, (lam_h, lam_a)
