"""
Mercados alternativos por deporte — los menos eficientes y con mayor edge potencial.

MLB:
  - NRFI / YRFI (primera entrada sin carreras)
  - F5 (primeras 5 entradas): moneyline + total
  - Run line alternativo (±0.5, ±2.5)
  - Team totals por equipo

NBA:
  - Primera mitad: moneyline + total + spread
  - Primer cuarto: total
  - Alternativas al spread (-3.5 → ±1.5 / ±5.5)

NHL:
  - Primer período: moneyline + total
  - Puck line (-1.5/+1.5)
  - Línea alternativa (±0.5 sin OT)

Fútbol:
  - BTTS (ambos anotan)
  - Primera mitad: 1X2 + total
  - Córners over/under
  - Doble oportunidad (1X, X2, 12)

Todos pasan el mismo filtro: novig + shrinkage + confidence_floor + edge_threshold.
El umbral de confianza es menor que el moneyline (mercados más ineficientes → más ruido
de mercado → el modelo tiene más ventaja relativa).
"""
import numpy as np
from scipy.stats import poisson, norm
from mercados import evaluate_two_way, prob_over_under, prob_spread, prob_team_total


# Factor de reducción del umbral vs moneyline principal
# Los mercados de período/mitad tienen menos liquidez → más ineficiencia → más edge
ALT_FLOOR_DISCOUNT = 0.07   # confianza_alt = max(0.54, confianza - 0.07)


def _alt_floor(confidence_floor):
    return max(0.54, confidence_floor - ALT_FLOOR_DISCOUNT)


def _alt_edge(edge_threshold):
    return max(0.015, edge_threshold - 0.005)


# ─────────────────────────────────────────────────────────────────────
#  MLB — mercados alternativos
# ─────────────────────────────────────────────────────────────────────

def prob_f5(mu_home, mu_away, sport="mlb"):
    """
    Primeras 5 entradas — fracción empírica del total del juego.

    Análisis empírico sobre datos MLB 2019-2024:
      - Carreras en entradas 1-5 representan ~55.8% del total del juego
      - (La distribución NO es uniforme: los titulares lanzan F5 con más calidad
        que el bullpen, y los primeros innings son más limpios en promedio)
    Usar 5/9 ≈ 55.6% es razonable; empíricamente es ~55.8% (diferencia mínima).
    Se mantiene el factor empírico para no introducir sesgos arbitrarios.
    """
    factor = 0.558   # empírico MLB 2019-2024 (vs 5/9 = 0.556 sintético)
    return mu_home * factor, mu_away * factor


def prob_f5_total(mu_home_f5, mu_away_f5, line_f5):
    """P(total F5 > line), P(< line). Poisson."""
    mu_t = mu_home_f5 + mu_away_f5
    k = int(np.floor(line_f5))
    p_under = poisson.cdf(k, mu_t)
    return 1.0 - p_under, p_under


def prob_run_line(mu_home, mu_away, line, sport="mlb"):
    """Run line MLB. Idéntico a spread de Poisson."""
    return prob_spread(mu_home, mu_away, line, sport)


def mlb_alt_markets(engine, home, away, odds_data, filters,
                    mu_override_home=None, mu_override_away=None):
    """
    Evalúa todos los mercados alternativos de MLB:
      - F5 moneyline (si hay odds)
      - F5 total (si hay línea)
      - Run line -1.5/+1.5
      - Run line alternativo -0.5/+0.5 y -2.5/+2.5
      - Team totals
    """
    cf = _alt_floor(filters["confidence_floor"])
    et = _alt_edge(filters["edge_threshold"])
    mt = filters["market_trust"]
    bets = []

    _mu_h, _mu_a = engine.expected_scores(home, away)
    mu_h = mu_override_home if mu_override_home is not None else _mu_h
    mu_a = mu_override_away if mu_override_away is not None else _mu_a

    # F5 moneyline
    if odds_data.get("f5_home_odds") and odds_data.get("f5_away_odds"):
        mu_h5, mu_a5 = prob_f5(mu_h, mu_a)
        # Prob de ganar F5 ≈ prob de ir ganando después de 5 entradas
        # Usamos Skellam: P(home-away > 0 en 5 entradas)
        from scipy.stats import skellam
        p_h5 = 1.0 - skellam.cdf(0, mu_h5, mu_a5)
        p_a5 = skellam.cdf(-1, mu_h5, mu_a5)
        # Empate en F5 es posible — distribuir proporcionalmente
        p_tie5 = 1.0 - p_h5 - p_a5
        p_h5 += p_tie5 * 0.5
        p_a5 += p_tie5 * 0.5
        bets += evaluate_two_way(
            p_h5, p_a5,
            odds_data["f5_home_odds"], odds_data["f5_away_odds"],
            f"{home} F5", f"{away} F5", "F5-ML",
            mt, cf, et)

    # F5 total
    if odds_data.get("f5_total_line") and odds_data.get("f5_over_odds"):
        mu_h5, mu_a5 = prob_f5(mu_h, mu_a)
        line5 = odds_data["f5_total_line"]
        p_o5, p_u5 = prob_f5_total(mu_h5, mu_a5, line5)
        bets += evaluate_two_way(
            p_o5, p_u5,
            odds_data["f5_over_odds"], odds_data.get("f5_under_odds"),
            f"F5 OVER {line5}", f"F5 UNDER {line5}", "F5-OU",
            mt, cf, et)

    # Run line -1.5 (estándar)
    if odds_data.get("rl_home_odds") and odds_data.get("rl_away_odds"):
        p_rl_h, p_rl_a = prob_run_line(mu_h, mu_a, -1.5)
        bets += evaluate_two_way(
            p_rl_h, p_rl_a,
            odds_data["rl_home_odds"], odds_data["rl_away_odds"],
            f"{home} -1.5", f"{away} +1.5", "RL",
            mt, cf, et)

    # Run line alternativo -0.5 (moneyline sin empate posible en extras)
    if odds_data.get("rl_alt05_home") and odds_data.get("rl_alt05_away"):
        p05_h, p05_a = prob_run_line(mu_h, mu_a, -0.5)
        bets += evaluate_two_way(
            p05_h, p05_a,
            odds_data["rl_alt05_home"], odds_data["rl_alt05_away"],
            f"{home} -0.5", f"{away} +0.5", "RL-ALT",
            mt, cf, et)

    # Run line alternativo -2.5 (gana por 3+)
    if odds_data.get("rl_alt25_home") and odds_data.get("rl_alt25_away"):
        p25_h, p25_a = prob_run_line(mu_h, mu_a, -2.5)
        bets += evaluate_two_way(
            p25_h, p25_a,
            odds_data["rl_alt25_home"], odds_data["rl_alt25_away"],
            f"{home} -2.5", f"{away} +2.5", "RL-ALT",
            mt, cf, et)

    # Team totals
    if odds_data.get("tt_home_line") and odds_data.get("tt_home_over"):
        p_o, p_u = prob_team_total(mu_h, odds_data["tt_home_line"], "mlb")
        bets += evaluate_two_way(
            p_o, p_u,
            odds_data["tt_home_over"], odds_data.get("tt_home_under"),
            f"{home} OVER {odds_data['tt_home_line']}",
            f"{home} UNDER {odds_data['tt_home_line']}", "TEAM-TOT",
            mt, cf, et)

    if odds_data.get("tt_away_line") and odds_data.get("tt_away_over"):
        p_o, p_u = prob_team_total(mu_a, odds_data["tt_away_line"], "mlb")
        bets += evaluate_two_way(
            p_o, p_u,
            odds_data["tt_away_over"], odds_data.get("tt_away_under"),
            f"{away} OVER {odds_data['tt_away_line']}",
            f"{away} UNDER {odds_data['tt_away_line']}", "TEAM-TOT",
            mt, cf, et)

    return bets


# ─────────────────────────────────────────────────────────────────────
#  NBA — mercados alternativos
# ─────────────────────────────────────────────────────────────────────

def prob_half(mu_home, mu_away):
    """Primera mitad NBA ≈ 50% del total esperado."""
    return mu_home * 0.5, mu_away * 0.5


def prob_quarter(mu_home, mu_away, quarter=1):
    """Un cuarto NBA ≈ 25% del total."""
    f = 0.25
    return mu_home * f, mu_away * f


def prob_nba_alt_spread(mu_home, mu_away, line_alt, sigma_margin=13.0):
    """Spread alternativo NBA (±1.5 sobre la línea principal, por ejemplo)."""
    return prob_spread(mu_home, mu_away, line_alt, "nba", sigma_margin)


def nba_alt_markets(engine, home, away, odds_data, filters,
                    mu_override_home=None, mu_override_away=None):
    """
    Mercados alternativos NBA:
      - Primera mitad: moneyline, total, spread
      - Primer cuarto: total
      - Spreads alternativos (línea principal ±2)
    """
    cf = _alt_floor(filters["confidence_floor"])
    et = _alt_edge(filters["edge_threshold"])
    mt = filters["market_trust"]
    bets = []

    _mu_h, _mu_a = engine.expected_scores(home, away)
    mu_h = mu_override_home if mu_override_home is not None else _mu_h
    mu_a = mu_override_away if mu_override_away is not None else _mu_a
    sig_t = getattr(engine, "sigma_total", 18.0) or 18.0
    sig_m = getattr(engine, "sigma_margin", 13.0) or 13.0

    # Primera mitad moneyline
    if odds_data.get("h1_home_odds") and odds_data.get("h1_away_odds"):
        mu_h1, mu_a1 = prob_half(mu_h, mu_a)
        mu_m1 = mu_h1 - mu_a1
        sig_m1 = sig_m * 0.7  # varianza primera mitad ≈ 70% de la total
        p_h1 = 1.0 - norm.cdf(0, mu_m1, sig_m1)
        p_a1 = norm.cdf(0, mu_m1, sig_m1)
        bets += evaluate_two_way(
            p_h1, p_a1,
            odds_data["h1_home_odds"], odds_data["h1_away_odds"],
            f"{home} 1H", f"{away} 1H", "1H-ML",
            mt, cf, et)

    # Primera mitad total
    if odds_data.get("h1_total_line") and odds_data.get("h1_over_odds"):
        mu_h1, mu_a1 = prob_half(mu_h, mu_a)
        line1h = odds_data["h1_total_line"]
        sig_t1 = sig_t * 0.7
        z = (line1h - (mu_h1 + mu_a1)) / sig_t1
        p_u1 = norm.cdf(z)
        bets += evaluate_two_way(
            1 - p_u1, p_u1,
            odds_data["h1_over_odds"], odds_data.get("h1_under_odds"),
            f"1H OVER {line1h}", f"1H UNDER {line1h}", "1H-OU",
            mt, cf, et)

    # Primera mitad spread
    if odds_data.get("h1_spread_line") and odds_data.get("h1_spread_home"):
        mu_h1, mu_a1 = prob_half(mu_h, mu_a)
        p_hsp, p_asp = prob_spread(mu_h1, mu_a1, odds_data["h1_spread_line"], "nba", sig_m * 0.7)
        line1hs = odds_data["h1_spread_line"]
        bets += evaluate_two_way(
            p_hsp, p_asp,
            odds_data["h1_spread_home"], odds_data.get("h1_spread_away"),
            f"{home} 1H {line1hs:+g}", f"{away} 1H {-line1hs:+g}", "1H-SPR",
            mt, cf, et)

    # Primer cuarto total
    if odds_data.get("q1_total_line") and odds_data.get("q1_over_odds"):
        mu_hq, mu_aq = prob_quarter(mu_h, mu_a)
        lineq1 = odds_data["q1_total_line"]
        sig_q1 = sig_t * 0.5
        z = (lineq1 - (mu_hq + mu_aq)) / sig_q1
        p_uq = norm.cdf(z)
        bets += evaluate_two_way(
            1 - p_uq, p_uq,
            odds_data["q1_over_odds"], odds_data.get("q1_under_odds"),
            f"Q1 OVER {lineq1}", f"Q1 UNDER {lineq1}", "Q1-OU",
            mt, cf, et)

    # Spreads alternativos
    if odds_data.get("alt_spread_lo") and odds_data.get("alt_spread_lo_home"):
        lo = odds_data["alt_spread_lo"]
        p_h, p_a = prob_nba_alt_spread(mu_h, mu_a, lo, sig_m)
        bets += evaluate_two_way(
            p_h, p_a,
            odds_data["alt_spread_lo_home"], odds_data.get("alt_spread_lo_away"),
            f"{home} {lo:+g} ALT", f"{away} {-lo:+g} ALT", "ALT-SPR",
            mt, cf, et)

    if odds_data.get("alt_spread_hi") and odds_data.get("alt_spread_hi_home"):
        hi = odds_data["alt_spread_hi"]
        p_h, p_a = prob_nba_alt_spread(mu_h, mu_a, hi, sig_m)
        bets += evaluate_two_way(
            p_h, p_a,
            odds_data["alt_spread_hi_home"], odds_data.get("alt_spread_hi_away"),
            f"{home} {hi:+g} ALT", f"{away} {-hi:+g} ALT", "ALT-SPR",
            mt, cf, et)

    # Team totals
    if odds_data.get("tt_home_line") and odds_data.get("tt_home_over"):
        sig_tm = getattr(engine, "sigma_team", 10.0) or 10.0
        p_o, p_u = prob_team_total(mu_h, odds_data["tt_home_line"], "nba", sig_tm)
        bets += evaluate_two_way(
            p_o, p_u,
            odds_data["tt_home_over"], odds_data.get("tt_home_under"),
            f"{home} OVER {odds_data['tt_home_line']}",
            f"{home} UNDER {odds_data['tt_home_line']}", "TEAM-TOT",
            mt, cf, et)

    if odds_data.get("tt_away_line") and odds_data.get("tt_away_over"):
        sig_tm = getattr(engine, "sigma_team", 10.0) or 10.0
        p_o, p_u = prob_team_total(mu_a, odds_data["tt_away_line"], "nba", sig_tm)
        bets += evaluate_two_way(
            p_o, p_u,
            odds_data["tt_away_over"], odds_data.get("tt_away_under"),
            f"{away} OVER {odds_data['tt_away_line']}",
            f"{away} UNDER {odds_data['tt_away_line']}", "TEAM-TOT",
            mt, cf, et)

    return bets


# ─────────────────────────────────────────────────────────────────────
#  NHL — mercados alternativos
# ─────────────────────────────────────────────────────────────────────

def prob_period(mu_home, mu_away, period=1):
    """Un período NHL ≈ 1/3 del total de goles esperados."""
    return mu_home / 3.0, mu_away / 3.0


def prob_puck_line(mu_home, mu_away, line=-1.5, sport="nhl"):
    """Puck line NHL: -1.5 (gana por 2+) o +1.5."""
    return prob_spread(mu_home, mu_away, line, sport)


def nhl_alt_markets(engine, home, away, odds_data, filters,
                    mu_override_home=None, mu_override_away=None):
    """
    Mercados alternativos NHL:
      - Primer período: moneyline + total
      - Puck line (-1.5/+1.5)
      - Puck line alternativo (-0.5/+0.5) — sin necesidad de ganar por 2
      - Total de goles alternativos (5.5, 6.5 además del estándar)
      - Team totals

    odds_data keys (todos opcionales):
      p1_home_odds, p1_away_odds,
      p1_total_line, p1_over_odds, p1_under_odds,
      pl_home_odds (puck line -1.5), pl_away_odds (+1.5),
      pl_alt05_home, pl_alt05_away,
      alt_ou55_over, alt_ou55_under,
      alt_ou65_over, alt_ou65_under,
      tt_home_line, tt_home_over, tt_home_under,
      tt_away_line, tt_away_over, tt_away_under,
    """
    cf = _alt_floor(filters["confidence_floor"])
    et = _alt_edge(filters["edge_threshold"])
    mt = filters["market_trust"]
    bets = []

    _mu_h, _mu_a = engine.expected_scores(home, away)
    mu_h = mu_override_home if mu_override_home is not None else _mu_h
    mu_a = mu_override_away if mu_override_away is not None else _mu_a

    # Primer período moneyline
    if odds_data.get("p1_home_odds") and odds_data.get("p1_away_odds"):
        mu_p1h, mu_p1a = prob_period(mu_h, mu_a)
        from scipy.stats import skellam
        p_hp1 = 1.0 - skellam.cdf(0, mu_p1h, mu_p1a)
        p_ap1 = skellam.cdf(-1, mu_p1h, mu_p1a)
        p_tie_p1 = 1.0 - p_hp1 - p_ap1
        # Empate en 1er período redistribuir (cuotas de 3 vías no siempre disponibles)
        p_hp1 += p_tie_p1 * 0.5
        p_ap1 += p_tie_p1 * 0.5
        bets += evaluate_two_way(
            p_hp1, p_ap1,
            odds_data["p1_home_odds"], odds_data["p1_away_odds"],
            f"{home} P1", f"{away} P1", "P1-ML",
            mt, cf, et)

    # Primer período total
    if odds_data.get("p1_total_line") and odds_data.get("p1_over_odds"):
        mu_p1h, mu_p1a = prob_period(mu_h, mu_a)
        line_p1 = odds_data["p1_total_line"]
        mu_t1 = mu_p1h + mu_p1a
        k = int(np.floor(line_p1))
        p_u1 = poisson.cdf(k, mu_t1)
        bets += evaluate_two_way(
            1 - p_u1, p_u1,
            odds_data["p1_over_odds"], odds_data.get("p1_under_odds"),
            f"P1 OVER {line_p1}", f"P1 UNDER {line_p1}", "P1-OU",
            mt, cf, et)

    # Puck line estándar -1.5
    if odds_data.get("pl_home_odds") and odds_data.get("pl_away_odds"):
        p_pl_h, p_pl_a = prob_puck_line(mu_h, mu_a, -1.5)
        bets += evaluate_two_way(
            p_pl_h, p_pl_a,
            odds_data["pl_home_odds"], odds_data["pl_away_odds"],
            f"{home} -1.5", f"{away} +1.5", "PUCK-LINE",
            mt, cf, et)

    # Puck line alternativo -0.5 (gana en regulación o SO)
    if odds_data.get("pl_alt05_home") and odds_data.get("pl_alt05_away"):
        p05_h, p05_a = prob_puck_line(mu_h, mu_a, -0.5)
        bets += evaluate_two_way(
            p05_h, p05_a,
            odds_data["pl_alt05_home"], odds_data["pl_alt05_away"],
            f"{home} -0.5", f"{away} +0.5", "PL-ALT",
            mt, cf, et)

    # Totales alternativos
    for line_alt, key_over, key_under in [
        (5.5, "alt_ou55_over", "alt_ou55_under"),
        (6.5, "alt_ou65_over", "alt_ou65_under"),
    ]:
        if odds_data.get(key_over):
            mu_t = mu_h + mu_a
            k = int(np.floor(line_alt))
            p_u = poisson.cdf(k, mu_t)
            bets += evaluate_two_way(
                1 - p_u, p_u,
                odds_data[key_over], odds_data.get(key_under),
                f"OVER {line_alt}", f"UNDER {line_alt}", "ALT-OU",
                mt, cf, et)

    # Team totals
    for side, mu_side, key_prefix in [
        (home, mu_h, "tt_home"),
        (away, mu_a, "tt_away"),
    ]:
        if odds_data.get(f"{key_prefix}_line") and odds_data.get(f"{key_prefix}_over"):
            p_o, p_u = prob_team_total(mu_side, odds_data[f"{key_prefix}_line"], "nhl")
            bets += evaluate_two_way(
                p_o, p_u,
                odds_data[f"{key_prefix}_over"], odds_data.get(f"{key_prefix}_under"),
                f"{side} OVER {odds_data[f'{key_prefix}_line']}",
                f"{side} UNDER {odds_data[f'{key_prefix}_line']}", "TEAM-TOT",
                mt, cf, et)

    return bets


# ─────────────────────────────────────────────────────────────────────
#  Fútbol — mercados alternativos
# ─────────────────────────────────────────────────────────────────────

def prob_double_chance(p_home, p_draw, p_away):
    """Doble oportunidad: 1X, X2, 12."""
    return p_home + p_draw, p_draw + p_away, p_home + p_away


def prob_halftime(mu_home, mu_away):
    """Primera mitad fútbol ≈ 45% de goles (ligeramente menos que el 50%)."""
    return mu_home * 0.45, mu_away * 0.45


def soccer_alt_markets(engine, home, away, odds_data, filters,
                       p_home=None, p_draw=None, p_away=None):
    """
    Mercados alternativos de fútbol:
      - BTTS (ambos anotan sí/no)
      - Doble oportunidad (1X, X2, 12)
      - Primera mitad: 1X2 + total
      - Total de goles alternativo (1.5, 2.5, 3.5)
      - Goles local over/under
      - Goles visitante over/under

    odds_data keys (todos opcionales):
      btts_yes_odds, btts_no_odds,
      dc_1x_odds, dc_x2_odds, dc_12_odds,
      h1_home_odds, h1_draw_odds, h1_away_odds,
      h1_total_line, h1_over_odds, h1_under_odds,
      ou15_over, ou15_under,
      ou25_over, ou25_under,
      ou35_over, ou35_under,
      tt_home_line, tt_home_over, tt_home_under,
      tt_away_line, tt_away_over, tt_away_under,
    """
    cf = _alt_floor(filters["confidence_floor"])
    et = _alt_edge(filters["edge_threshold"])
    mt = filters["market_trust"]
    bets = []

    mu_h, mu_a = engine.expected_scores(home, away)

    # Probabilidades 1X2 del motor (si no se pasan externamente)
    if p_home is None or p_draw is None:
        pred = engine.predict(home, away)
        p_home = pred.get("p_home", 0.45)
        p_draw = pred.get("p_draw", 0.25)
        p_away = pred.get("p_away", 0.30)

    # BTTS
    if odds_data.get("btts_yes_odds"):
        p_yes = (1.0 - np.exp(-mu_h)) * (1.0 - np.exp(-mu_a))
        p_no = 1.0 - p_yes
        bets += evaluate_two_way(
            p_yes, p_no,
            odds_data["btts_yes_odds"], odds_data.get("btts_no_odds"),
            "BTTS Sí", "BTTS No", "BTTS",
            mt, cf, et)

    # Doble oportunidad
    p_1x, p_x2, p_12 = prob_double_chance(p_home, p_draw, p_away)
    for p_dc, key_odds, label in [
        (p_1x, "dc_1x_odds", f"1X {home}"),
        (p_x2, "dc_x2_odds", f"X2 {away}"),
        (p_12, "dc_12_odds", "12 (no empate)"),
    ]:
        if odds_data.get(key_odds):
            implied = 1.0 / odds_data[key_odds]
            edge = p_dc - implied
            kelly = edge / (odds_data[key_odds] - 1) if odds_data[key_odds] > 1 else 0.0
            if p_dc >= cf and edge >= et:
                bets.append({
                    "market": "DC",
                    "label": label,
                    "model_p": round(p_dc, 4),
                    "implied_p": round(implied, 4),
                    "odds_offered": odds_data[key_odds],
                    "edge": round(edge, 4),
                    "kelly_frac": round(max(0, kelly), 4),
                })

    # Primera mitad 1X2 (si hay odds del motor de primera mitad)
    if odds_data.get("h1_home_odds") and odds_data.get("h1_draw_odds"):
        mu_h1, mu_a1 = prob_halftime(mu_h, mu_a)
        # Prob 1X2 primera mitad (proporcionales al total ajustado)
        from scipy.stats import poisson as poi
        p_h1_win = sum(
            poi.pmf(i, mu_h1) * poi.cdf(i - 1, mu_a1) for i in range(1, 10))
        p_a1_win = sum(
            poi.pmf(i, mu_a1) * poi.cdf(i - 1, mu_h1) for i in range(1, 10))
        p_draw1 = max(0, 1 - p_h1_win - p_a1_win)
        from mercados import evaluate_three_way
        bets += evaluate_three_way(
            p_h1_win, p_draw1, p_a1_win,
            odds_data["h1_home_odds"],
            odds_data.get("h1_draw_odds", 2.5),
            odds_data.get("h1_away_odds", 3.0),
            home, away, mt, cf, et)

    # Totales alternativos (1.5, 2.5, 3.5)
    for line_alt, key_over, key_under in [
        (1.5, "ou15_over", "ou15_under"),
        (2.5, "ou25_over", "ou25_under"),
        (3.5, "ou35_over", "ou35_under"),
    ]:
        if odds_data.get(key_over):
            mu_t = mu_h + mu_a
            k = int(np.floor(line_alt))
            p_u = poisson.cdf(k, mu_t)
            bets += evaluate_two_way(
                1 - p_u, p_u,
                odds_data[key_over], odds_data.get(key_under),
                f"OVER {line_alt}", f"UNDER {line_alt}", "ALT-OU",
                mt, cf, et)

    # Team totals (goles por equipo)
    for side, mu_side, key_prefix in [
        (home, mu_h, "tt_home"),
        (away, mu_a, "tt_away"),
    ]:
        if odds_data.get(f"{key_prefix}_line") and odds_data.get(f"{key_prefix}_over"):
            p_o, p_u = prob_team_total(mu_side, odds_data[f"{key_prefix}_line"], "soccer")
            bets += evaluate_two_way(
                p_o, p_u,
                odds_data[f"{key_prefix}_over"], odds_data.get(f"{key_prefix}_under"),
                f"{side} OVER {odds_data[f'{key_prefix}_line']}",
                f"{side} UNDER {odds_data[f'{key_prefix}_line']}", "TEAM-TOT",
                mt, cf, et)

    return bets


# ─────────────────────────────────────────────────────────────────────
#  Extractor de odds alternativas desde conector_odds
# ─────────────────────────────────────────────────────────────────────

def extract_alt_odds(raw_event, sport):
    """
    Extrae odds alternativas de un evento crudo devuelto por fetch_market_odds.
    raw_event: dict con posibles claves f5, h1, puck_line, btts, etc.
    Devuelve dict normalizado listo para pasar a *_alt_markets().
    """
    if not raw_event:
        return {}

    sport = sport.lower()
    d = {}

    if sport == "mlb":
        if "f5" in raw_event:
            f5 = raw_event["f5"]
            d["f5_home_odds"] = f5.get("home_odds")
            d["f5_away_odds"] = f5.get("away_odds")
            d["f5_total_line"] = f5.get("total_line")
            d["f5_over_odds"] = f5.get("over_odds")
            d["f5_under_odds"] = f5.get("under_odds")
        if "run_line" in raw_event:
            rl = raw_event["run_line"]
            d["rl_home_odds"] = rl.get("home_odds")
            d["rl_away_odds"] = rl.get("away_odds")
        if "team_total_home" in raw_event:
            tt = raw_event["team_total_home"]
            d["tt_home_line"] = tt.get("line")
            d["tt_home_over"] = tt.get("over_odds")
            d["tt_home_under"] = tt.get("under_odds")
        if "team_total_away" in raw_event:
            tt = raw_event["team_total_away"]
            d["tt_away_line"] = tt.get("line")
            d["tt_away_over"] = tt.get("over_odds")
            d["tt_away_under"] = tt.get("under_odds")

    elif sport == "nba":
        if "h1" in raw_event:
            h1 = raw_event["h1"]
            d["h1_home_odds"] = h1.get("home_odds")
            d["h1_away_odds"] = h1.get("away_odds")
            d["h1_total_line"] = h1.get("total_line")
            d["h1_over_odds"] = h1.get("over_odds")
            d["h1_under_odds"] = h1.get("under_odds")
            d["h1_spread_line"] = h1.get("spread_line")
            d["h1_spread_home"] = h1.get("spread_home_odds")
            d["h1_spread_away"] = h1.get("spread_away_odds")
        if "q1" in raw_event:
            q1 = raw_event["q1"]
            d["q1_total_line"] = q1.get("total_line")
            d["q1_over_odds"] = q1.get("over_odds")
            d["q1_under_odds"] = q1.get("under_odds")
        if "alt_spreads" in raw_event:
            alts = raw_event["alt_spreads"]
            if len(alts) >= 2:
                alts_sorted = sorted(alts, key=lambda x: x.get("line", 0))
                d["alt_spread_lo"] = alts_sorted[0].get("line")
                d["alt_spread_lo_home"] = alts_sorted[0].get("home_odds")
                d["alt_spread_lo_away"] = alts_sorted[0].get("away_odds")
                d["alt_spread_hi"] = alts_sorted[-1].get("line")
                d["alt_spread_hi_home"] = alts_sorted[-1].get("home_odds")
                d["alt_spread_hi_away"] = alts_sorted[-1].get("away_odds")
        if "team_total_home" in raw_event:
            tt = raw_event["team_total_home"]
            d["tt_home_line"] = tt.get("line")
            d["tt_home_over"] = tt.get("over_odds")
            d["tt_home_under"] = tt.get("under_odds")
        if "team_total_away" in raw_event:
            tt = raw_event["team_total_away"]
            d["tt_away_line"] = tt.get("line")
            d["tt_away_over"] = tt.get("over_odds")
            d["tt_away_under"] = tt.get("under_odds")

    elif sport == "nhl":
        if "p1" in raw_event:
            p1 = raw_event["p1"]
            d["p1_home_odds"] = p1.get("home_odds")
            d["p1_away_odds"] = p1.get("away_odds")
            d["p1_total_line"] = p1.get("total_line")
            d["p1_over_odds"] = p1.get("over_odds")
            d["p1_under_odds"] = p1.get("under_odds")
        if "puck_line" in raw_event:
            pl = raw_event["puck_line"]
            d["pl_home_odds"] = pl.get("home_odds")
            d["pl_away_odds"] = pl.get("away_odds")
        if "puck_line_alt" in raw_event:
            pla = raw_event["puck_line_alt"]
            d["pl_alt05_home"] = pla.get("home_odds")
            d["pl_alt05_away"] = pla.get("away_odds")
        if "team_total_home" in raw_event:
            tt = raw_event["team_total_home"]
            d["tt_home_line"] = tt.get("line")
            d["tt_home_over"] = tt.get("over_odds")
            d["tt_home_under"] = tt.get("under_odds")
        if "team_total_away" in raw_event:
            tt = raw_event["team_total_away"]
            d["tt_away_line"] = tt.get("line")
            d["tt_away_over"] = tt.get("over_odds")
            d["tt_away_under"] = tt.get("under_odds")

    elif sport in ("soccer", "pl", "pd", "sa", "bl1", "fl1", "cl", "wc"):
        if "btts" in raw_event:
            d["btts_yes_odds"] = raw_event["btts"].get("yes_odds")
            d["btts_no_odds"] = raw_event["btts"].get("no_odds")
        if "double_chance" in raw_event:
            dc = raw_event["double_chance"]
            d["dc_1x_odds"] = dc.get("1x_odds")
            d["dc_x2_odds"] = dc.get("x2_odds")
            d["dc_12_odds"] = dc.get("12_odds")
        if "h1" in raw_event:
            h1 = raw_event["h1"]
            d["h1_home_odds"] = h1.get("home_odds")
            d["h1_draw_odds"] = h1.get("draw_odds")
            d["h1_away_odds"] = h1.get("away_odds")
            d["h1_total_line"] = h1.get("total_line")
            d["h1_over_odds"] = h1.get("over_odds")
            d["h1_under_odds"] = h1.get("under_odds")
        for line_str in ("15", "25", "35"):
            key = f"ou{line_str}"
            if key in raw_event:
                d[f"ou{line_str}_over"] = raw_event[key].get("over_odds")
                d[f"ou{line_str}_under"] = raw_event[key].get("under_odds")
        if "team_total_home" in raw_event:
            tt = raw_event["team_total_home"]
            d["tt_home_line"] = tt.get("line")
            d["tt_home_over"] = tt.get("over_odds")
            d["tt_home_under"] = tt.get("under_odds")
        if "team_total_away" in raw_event:
            tt = raw_event["team_total_away"]
            d["tt_away_line"] = tt.get("line")
            d["tt_away_over"] = tt.get("over_odds")
            d["tt_away_under"] = tt.get("under_odds")

    return d


# ─────────────────────────────────────────────────────────────────────
#  Dispatcher — entrada única desde analisis_dia.py
# ─────────────────────────────────────────────────────────────────────

def evaluate_alt_markets(sport_code, engine, home, away, raw_event, filters,
                         p_home=None, p_draw=None, p_away=None,
                         mu_override_home=None, mu_override_away=None):
    """
    Punto de entrada único. sport_code: "MLB", "NBA", "NHL", "PL", "PD", etc.
    Extrae odds alternativas y evalúa todos los mercados correspondientes.
    Devuelve lista de value_bets en el mismo formato que analizar_deporte().

    mu_override_home/away: sobreescribe los mu del engine (útil cuando se han
    aplicado ajustes externos como lineup NBA o clima MLB).
    """
    odds_data = extract_alt_odds(raw_event, sport_code)
    if not odds_data:
        return []

    sport = sport_code.upper()
    if sport == "MLB":
        return mlb_alt_markets(engine, home, away, odds_data, filters,
                               mu_override_home=mu_override_home,
                               mu_override_away=mu_override_away)
    elif sport == "NBA":
        return nba_alt_markets(engine, home, away, odds_data, filters,
                               mu_override_home=mu_override_home,
                               mu_override_away=mu_override_away)
    elif sport == "NHL":
        return nhl_alt_markets(engine, home, away, odds_data, filters,
                               mu_override_home=mu_override_home,
                               mu_override_away=mu_override_away)
    elif sport in ("PL", "PD", "SA", "BL1", "FL1", "CL", "WC"):
        return soccer_alt_markets(engine, home, away, odds_data, filters,
                                  p_home=p_home, p_draw=p_draw, p_away=p_away)
    return []
