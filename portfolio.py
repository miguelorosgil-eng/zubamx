"""
Portfolio Coverage Staking
Dado un banco B y N value bets con sus probabilidades y cuotas,
calcula el stake óptimo por apuesta de forma que:
1. El EV total sea máximo
2. Si se gana AL MENOS K de N apuestas, se recupera el banco + ganancia mínima
3. Muestra P(ganar >= K), P(ruina total), EV esperado

Requiere: numpy, scipy
"""

import numpy as np
from itertools import combinations
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Poisson-Binomial: P(X >= k) cuando cada evento tiene su propia probabilidad
# ---------------------------------------------------------------------------

def _poisson_binomial_pmf(probs: List[float]) -> np.ndarray:
    """
    Calcula la PMF exacta de la distribución Poisson-Binomial via DP.
    probs: lista de probabilidades individuales p_i (0 < p_i < 1)
    Retorna array de longitud n+1 donde pmf[k] = P(X = k)
    """
    n = len(probs)
    dp = np.zeros(n + 1)
    dp[0] = 1.0
    for p in probs:
        # Iterar en reversa para evitar usar el mismo elemento dos veces
        new_dp = np.zeros(n + 1)
        for k in range(n + 1):
            new_dp[k] += dp[k] * (1.0 - p)
            if k > 0:
                new_dp[k] += dp[k - 1] * p
        dp = new_dp
    return dp


def _p_at_least_k(probs: List[float], k: int) -> float:
    """P(ganar >= k apuestas) con dist. Poisson-Binomial."""
    if k <= 0:
        return 1.0
    pmf = _poisson_binomial_pmf(probs)
    return float(np.sum(pmf[k:]))


def _p_total_loss(probs: List[float]) -> float:
    """P(ganar 0 apuestas) = P(ruina total)."""
    pmf = _poisson_binomial_pmf(probs)
    return float(pmf[0])


# ---------------------------------------------------------------------------
# Cálculo de stakes de cobertura
# ---------------------------------------------------------------------------

def _coverage_stakes_k1(bets: List[Dict], bankroll: float, target_return: float) -> List[float]:
    """
    min_winners=1: cada apuesta i tiene stake tal que si gana,
    el retorno neto cubre bankroll * target_return.
    stake_i * odds_i >= bankroll * target_return
    => stake_i = bankroll * target_return / odds_i
    Luego escalar si la suma excede el bankroll.
    """
    target = bankroll * target_return
    raw_stakes = [target / b["odds_offered"] for b in bets]
    total = sum(raw_stakes)
    if total > bankroll:
        scale = bankroll / total
        raw_stakes = [s * scale for s in raw_stakes]
    return raw_stakes


def _coverage_stakes_k2(bets: List[Dict], bankroll: float, target_return: float) -> List[float]:
    """
    min_winners=2: buscamos stakes tal que para cualquier par (i, j) que gane,
    la ganancia neta >= bankroll * target_return.
    Para simplificar: greedy — ordenar por odds desc, asignar más peso a los de
    menor odds (más probables), asegurar que cada par de ganadores cubra.
    Usamos aproximación: stake_i proporcional a 1/odds_i, luego verificar el
    par mínimo (menores odds) y escalar el banco para que ese par cubra.
    """
    n = len(bets)
    if n < 2:
        return _coverage_stakes_k1(bets, bankroll, target_return)

    target = bankroll * target_return
    # Proporcional a 1/odds (más stake a cuotas bajas = más probable)
    inv_odds = np.array([1.0 / b["odds_offered"] for b in bets])
    weights = inv_odds / inv_odds.sum()
    raw_stakes = weights * bankroll

    # Verificar que el par de ganadores mínimo cubra target
    # El par mínimo es el par con menor retorno combinado
    best_pair_return = -np.inf
    for i, j in combinations(range(n), 2):
        ret = raw_stakes[i] * (bets[i]["odds_offered"] - 1) + raw_stakes[j] * (bets[j]["odds_offered"] - 1)
        # Neto: ganancias de i y j, menos pérdidas del resto
        rest_loss = sum(raw_stakes[k] for k in range(n) if k != i and k != j)
        net = ret - rest_loss
        if net > best_pair_return:
            best_pair_return = net

    # Si el mejor par no cubre, no hay mucho que hacer sin subir stakes
    # Solo garantizamos que suma <= bankroll
    total = sum(raw_stakes)
    if total > bankroll:
        scale = bankroll / total
        raw_stakes = raw_stakes * scale

    return list(raw_stakes)


def _kelly_stake(bet: Dict, bankroll: float, fraction: float = 0.25) -> float:
    """Kelly fraccionado. fraction=0.25 = quarter-Kelly."""
    k = bet.get("kelly_frac", 0.0)
    return max(0.0, k * fraction * bankroll)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def compute_portfolio(
    bets: List[Dict[str, Any]],
    bankroll: float,
    target_return: float = 1.0,
    min_winners: int = 1,
) -> Dict[str, Any]:
    """
    bets: lista de dicts {market, model_p, odds_offered, edge, kelly_frac, label}
    bankroll: float (ej: 1000)
    target_return: multiplicador mínimo al ganar (1.0 = recuperar banco, 1.2 = 20% ganancia)
    min_winners: cuántas apuestas ganadoras necesitas para cubrir (default 1)

    Returns dict con:
    - stakes: lista de {label, stake, odds, potential_return, kelly_stake, chosen_stake}
    - p_at_least_k_winners: P(ganar >= min_winners apuestas)
    - p_total_loss: P(perder todo)
    - expected_value: EV total en unidades monetarias
    - expected_roi: ROI esperado sobre el total invertido
    - coverage_return: retorno neto si exactamente min_winners apuestas ganan (peor caso)
    - recommended: True si EV > 0 y p_at_least_k_winners > 0.7
    """
    if not bets:
        return {"error": "No hay apuestas para evaluar.", "stakes": []}

    # Filtrar apuestas con edge positivo y cuotas válidas
    valid = [b for b in bets if b.get("edge", 0) > 0 and b.get("odds_offered", 1) > 1]
    if not valid:
        return {"error": "Ninguna apuesta tiene edge positivo.", "stakes": []}

    probs = [b["model_p"] for b in valid]

    # Calcular stakes de cobertura
    if min_winners <= 1:
        cov_stakes = _coverage_stakes_k1(valid, bankroll, target_return)
    else:
        cov_stakes = _coverage_stakes_k2(valid, bankroll, target_return)

    # Kelly stakes (quarter-Kelly)
    kelly_stakes = [_kelly_stake(b, bankroll) for b in valid]

    # Elegir el menor (más conservador)
    chosen_stakes = [min(c, k) if k > 0 else c for c, k in zip(cov_stakes, kelly_stakes)]

    # Escalar si la suma de chosen_stakes supera el bankroll
    total_chosen = sum(chosen_stakes)
    if total_chosen > bankroll:
        scale = bankroll / total_chosen
        chosen_stakes = [s * scale for s in chosen_stakes]

    # Construir resultado por apuesta
    stakes_result = []
    for i, b in enumerate(valid):
        s = chosen_stakes[i]
        stakes_result.append({
            "label": b.get("label", b.get("market", f"bet_{i}")),
            "market": b.get("market", ""),
            "model_p": round(b["model_p"], 4),
            "edge": round(b.get("edge", 0), 4),
            "odds": b["odds_offered"],
            "coverage_stake": round(cov_stakes[i], 2),
            "kelly_stake": round(kelly_stakes[i], 2),
            "chosen_stake": round(s, 2),
            "potential_return": round(s * b["odds_offered"], 2),
            "potential_profit": round(s * (b["odds_offered"] - 1), 2),
        })

    # Estadísticas probabilísticas con Poisson-Binomial
    p_at_k = _p_at_least_k(probs, min_winners)
    p_ruin = _p_total_loss(probs)

    # EV total: sum_i [ p_i * profit_i - (1-p_i) * stake_i ]
    total_invested = sum(chosen_stakes)
    ev = sum(
        probs[i] * chosen_stakes[i] * (valid[i]["odds_offered"] - 1)
        - (1 - probs[i]) * chosen_stakes[i]
        for i in range(len(valid))
    )
    roi = ev / total_invested if total_invested > 0 else 0.0

    # Retorno si exactamente min_winners ganan (peor caso de cobertura)
    # Ordenar por retorno potencial desc, tomar las primeras min_winners
    sorted_idx = sorted(range(len(valid)), key=lambda i: chosen_stakes[i] * valid[i]["odds_offered"], reverse=True)
    winners_idx = sorted_idx[:min_winners]
    losers_idx = sorted_idx[min_winners:]
    coverage_profit = sum(chosen_stakes[i] * (valid[i]["odds_offered"] - 1) for i in winners_idx)
    coverage_loss = sum(chosen_stakes[i] for i in losers_idx)
    coverage_net = coverage_profit - coverage_loss

    return {
        "bets_evaluated": len(valid),
        "stakes": stakes_result,
        "total_invested": round(total_invested, 2),
        "p_at_least_k_winners": round(p_at_k, 4),
        "p_total_loss": round(p_ruin, 4),
        "expected_value": round(ev, 2),
        "expected_roi": round(roi, 4),
        "coverage_return": round(coverage_net, 2),
        "coverage_return_pct": round(coverage_net / bankroll * 100, 2),
        "recommended": ev > 0 and p_at_k > 0.7,
        "min_winners": min_winners,
        "target_return": target_return,
    }


# ---------------------------------------------------------------------------
# Reporte visual
# ---------------------------------------------------------------------------

def print_portfolio_report(portfolio_result: Dict, bankroll: float) -> None:
    """Imprime tabla clara con el plan de apuestas y estadísticas."""
    if "error" in portfolio_result:
        print(f"[Portfolio] ERROR: {portfolio_result['error']}")
        return

    sep = "─" * 90
    print(f"\n{'═' * 90}")
    print(f"  PORTFOLIO REPORT  |  Bankroll: ${bankroll:,.2f}  |  Min. ganadores: {portfolio_result['min_winners']}")
    print(f"{'═' * 90}")

    # Cabecera tabla
    print(f"{'Apuesta':<30} {'Odds':>6} {'P(modelo)':>10} {'Edge':>7} {'Stake':>9} {'Retorno':>10} {'Ganancia':>10}")
    print(sep)

    for s in portfolio_result["stakes"]:
        label = s["label"][:29]
        print(
            f"{label:<30} {s['odds']:>6.2f} {s['model_p']:>10.3%} {s['edge']:>7.3%} "
            f"${s['chosen_stake']:>8.2f} ${s['potential_return']:>9.2f} ${s['potential_profit']:>9.2f}"
        )

    print(sep)
    total_inv = portfolio_result["total_invested"]
    print(f"{'TOTAL INVERTIDO':<30} {'':>6} {'':>10} {'':>7} ${total_inv:>8.2f}")
    print()

    # Estadísticas
    p_k = portfolio_result["p_at_least_k_winners"]
    p_r = portfolio_result["p_total_loss"]
    ev = portfolio_result["expected_value"]
    roi = portfolio_result["expected_roi"]
    cov = portfolio_result["coverage_return"]
    cov_pct = portfolio_result["coverage_return_pct"]
    rec = portfolio_result["recommended"]

    print(f"  P(ganar >= {portfolio_result['min_winners']} apuestas):  {p_k:.1%}  {'✓ OK' if p_k > 0.7 else '✗ BAJO'}")
    print(f"  P(ruina total):              {p_r:.1%}")
    print(f"  EV esperado:                 ${ev:+.2f}  (ROI: {roi:+.2%})")
    print(f"  Retorno si {portfolio_result['min_winners']} gana(n):      ${cov:+.2f}  ({cov_pct:+.1f}% del banco)")
    print()
    status = "RECOMENDADO ✓" if rec else "NO RECOMENDADO ✗"
    print(f"  >>> {status}")
    print(f"{'═' * 90}\n")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample_bets = [
        {
            "market": "home",
            "label": "Lakers gana",
            "model_p": 0.62,
            "odds_offered": 1.85,
            "edge": 0.08,
            "kelly_frac": 0.095,
        },
        {
            "market": "home",
            "label": "Yankees gana",
            "model_p": 0.58,
            "odds_offered": 1.75,
            "edge": 0.06,
            "kelly_frac": 0.08,
        },
        {
            "market": "away",
            "label": "Bruins gana (visitante)",
            "model_p": 0.55,
            "odds_offered": 2.10,
            "edge": 0.045,
            "kelly_frac": 0.04,
        },
    ]

    bankroll = 1000.0

    print("=== Escenario 1: Cubrir con 1 ganador ===")
    p1 = compute_portfolio(sample_bets, bankroll, target_return=1.0, min_winners=1)
    print_portfolio_report(p1, bankroll)

    print("=== Escenario 2: Cubrir con 2 ganadores, 20% ganancia mínima ===")
    p2 = compute_portfolio(sample_bets, bankroll, target_return=1.2, min_winners=2)
    print_portfolio_report(p2, bankroll)
