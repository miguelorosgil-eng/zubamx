"""
Mercados estadísticos para deportes: Over/Under, Hándicap/Spread, BTTS, Team Totals.

Modela la DISTRIBUCIÓN de anotación (no solo quién gana):
  • Deportes de conteo (MLB carreras, NHL goles): Poisson / Skellam.
  • Deportes de alto marcador (NBA puntos): Normal.

Todos los mercados pasan por el MISMO filtro de calidad que el moneyline:
  1) quitar la vig del mercado (probabilidad real sin margen),
  2) shrinkage: mezclar modelo con mercado (prior fuerte),
  3) apostar solo si prob_final >= piso de confianza Y edge >= umbral.
"""
import numpy as np
from scipy.stats import poisson, skellam, norm

# Deportes cuyo marcador se modela como conteo (Poisson)
POISSON_SPORTS = {"mlb", "nhl", "soccer"}
# Deportes de alto marcador (Normal)
NORMAL_SPORTS = {"nba"}


# ───────────────────────── Evaluador compartido ─────────────────────────
def evaluate_two_way(p_model_a, p_model_b, odds_a, odds_b,
                     label_a, label_b, market_key,
                     market_trust=0.5, confidence_floor=0.65, edge_threshold=0.02):
    """
    Mercado de dos resultados (over/under, home/away spread, BTTS sí/no...).
    p_model_*: probabilidad del modelo para cada lado (suman ~1).
    odds_*:    cuotas decimales ofrecidas por el mercado.
    Devuelve lista de value_bets que pasan el filtro combinado.
    """
    if not odds_a or not odds_b or odds_a <= 1 or odds_b <= 1:
        return []

    # 1) Quitar vig → probabilidad real del mercado
    raw_a, raw_b = 1.0 / odds_a, 1.0 / odds_b
    tot = raw_a + raw_b
    novig_a, novig_b = raw_a / tot, raw_b / tot

    # 2) Shrinkage hacia el mercado
    lam = market_trust
    blend_a = (1 - lam) * p_model_a + lam * novig_a
    blend_b = (1 - lam) * p_model_b + lam * novig_b

    bets = []
    for blended_p, odds, label in [(blend_a, odds_a, label_a), (blend_b, odds_b, label_b)]:
        implied_vig = 1.0 / odds
        edge = blended_p - implied_vig
        kelly = edge / (odds - 1) if odds > 1 else 0.0
        if blended_p >= confidence_floor and edge >= edge_threshold:
            bets.append({
                "market": market_key,
                "label": label,
                "model_p": round(blended_p, 4),
                "implied_p": round(implied_vig, 4),
                "odds_offered": odds,
                "edge": round(edge, 4),
                "kelly_frac": round(max(0, kelly), 4),
            })
    return bets


def evaluate_three_way(p_home, p_draw, p_away, odds_home, odds_draw, odds_away,
                       home, away, market_trust=0.5, confidence_floor=0.65,
                       edge_threshold=0.02, knockout=False):
    """
    Moneyline 1X2 de fútbol (con empate). Mismo filtro: novig + shrinkage +
    piso de confianza + edge. Devuelve value_bets que pasan.

    knockout=True eleva el piso de confianza: en eliminatorias/grupos cerrados
    los equipos débiles juegan a no perder y empatan 0-0 contra favoritos.
    Hallazgo (jun 2026): "Arabia Saudita gana" a momio 2.70 terminó 0-0 — un
    favorito moderado vs un rival ultra-defensivo no es apuesta de valor.
    """
    odds = [odds_home, odds_draw, odds_away]
    if any(o is None or o <= 1 for o in odds):
        return []
    if knockout:
        confidence_floor = max(confidence_floor, 0.62)
    raw = np.array([1.0 / o for o in odds])
    novig = raw / raw.sum()
    p_model = np.array([p_home, p_draw, p_away])
    lam = market_trust
    blended = (1 - lam) * p_model + lam * novig

    labels = [f"{home} gana", "Empate", f"{away} gana"]
    # En knockout, solo se apuesta a "gana" si el equipo es FAVORITO CLARO del
    # mercado (momio < 2.0). Un favorito moderado (momio >= 2.0) contra un rival
    # defensivo empata demasiado seguido — caso Arabia Saudita @2.70 → 0-0.
    knockout_max_odds = 2.0
    bets = []
    for i, lab in enumerate(labels):
        # i==1 es el empate; el guard de favorito aplica solo a "gana" (i 0 y 2)
        if knockout and i != 1 and odds[i] >= knockout_max_odds:
            continue
        implied_vig = 1.0 / odds[i]
        edge = blended[i] - implied_vig
        kelly = edge / (odds[i] - 1) if odds[i] > 1 else 0.0
        if blended[i] >= confidence_floor and edge >= edge_threshold:
            bets.append({
                "market": "1X2", "label": lab,
                "model_p": round(blended[i], 4),
                "implied_p": round(implied_vig, 4),
                "odds_offered": odds[i],
                "edge": round(edge, 4),
                "kelly_frac": round(max(0, kelly), 4),
            })
    return bets


# ───────────────────────── Probabilidades por mercado ─────────────────────────
def _is_poisson(sport):
    return sport.lower() in POISSON_SPORTS


def get_nba_sigma(mu_total: float, line: float = None) -> float:
    """
    P5 — Sigma NBA dinámico: la desviación estándar del total de puntos
    depende del ritmo esperado del partido (mu_total).

    Análisis empírico NBA 2019-2024:
      - Partidos lentos (mu_total < 210): sigma ≈ 15.5
      - Partidos normales (210-230):      sigma ≈ 17.5
      - Partidos rápidos (mu_total > 230): sigma ≈ 19.5

    Usar sigma=18 fijo subestima los extremos y sobreestima los medios.
    """
    if mu_total < 210:
        return 15.5
    elif mu_total < 220:
        return 16.5
    elif mu_total < 230:
        return 17.5
    else:
        return 19.0


def prob_over_under(mu_home, mu_away, line, sport, sigma_total=None):
    """P(total > line), P(total < line). line típico 8.5 (MLB), 5.5 (NHL), 224.5 (NBA)."""
    mu_total = mu_home + mu_away
    if _is_poisson(sport):
        # total = suma de dos Poisson = Poisson(mu_total). line es X.5 → over = P(>= ceil)
        k = int(np.floor(line))
        p_under = poisson.cdf(k, mu_total)      # P(total <= k) = P(total < line)
        p_over = 1.0 - p_under
    else:
        # P5: sigma dinámico para NBA según ritmo esperado
        if sigma_total is None and sport.lower() == "nba":
            sig = get_nba_sigma(mu_total, line)
        else:
            sig = sigma_total or 18.0
        z = (line - mu_total) / sig
        p_under = norm.cdf(z)
        p_over = 1.0 - p_under
    return p_over, p_under


def prob_spread(mu_home, mu_away, line, sport, sigma_margin=None):
    """
    Hándicap. line = ventaja que se da al LOCAL (negativa si es favorito).
    Ej. line=-1.5 → P(local gana por >=2) y P(visita +1.5 → pierde por <=1 o gana).
    Devuelve (p_home_cover, p_away_cover).
    """
    if _is_poisson(sport):
        # margen = home - away ~ Skellam(mu_home, mu_away)
        # local cubre -L (L>0): margen >= L+1 (para línea .5) → P(margen > L)
        thr = -line  # línea -1.5 → thr=1.5 → necesita margen >=2
        k = int(np.floor(thr))
        # P(margen <= k) bajo Skellam:
        p_home_no_cover = skellam.cdf(k, mu_home, mu_away)
        p_home_cover = 1.0 - p_home_no_cover
    else:
        sig = sigma_margin or 13.0
        mu_m = mu_home - mu_away
        # local cubre si (home-away) > -line  →  margen + line > 0
        z = (-line - mu_m) / sig
        p_home_cover = 1.0 - norm.cdf(z)
    return p_home_cover, 1.0 - p_home_cover


def prob_btts(mu_home, mu_away):
    """Ambos anotan (BTTS) sí/no. Solo tiene sentido en deportes de bajo marcador."""
    p_home_scores = 1.0 - np.exp(-mu_home)
    p_away_scores = 1.0 - np.exp(-mu_away)
    p_yes = p_home_scores * p_away_scores
    return p_yes, 1.0 - p_yes


def prob_nrfi(era_home_sp, era_away_sp, first_inning_factor=1.10):
    """
    NRFI = No Run First Inning (ninguna carrera en la 1ª entrada).
    Primera entrada: el visitante batea (alto 1ª) vs pitcher LOCAL,
    y el local batea (bajo 1ª) vs pitcher VISITANTE.
    Carreras esperadas/entrada de un pitcher ≈ ERA/9 (la 1ª anota algo más → factor).
    P(0 carreras en una entrada) ≈ Poisson(λ) en 0 = e^(-λ).
    Devuelve (p_nrfi, p_yrfi).
    """
    if era_home_sp is None or era_away_sp is None:
        return None, None
    lam_top = (era_home_sp / 9.0) * first_inning_factor   # local frena al visitante
    lam_bot = (era_away_sp / 9.0) * first_inning_factor   # visitante frena al local
    p_no_top = np.exp(-lam_top)
    p_no_bot = np.exp(-lam_bot)
    p_nrfi = p_no_top * p_no_bot
    return p_nrfi, 1.0 - p_nrfi


def prob_team_total(mu_team, line, sport, sigma_team=None):
    """P(equipo anota > line), P(< line)."""
    if _is_poisson(sport):
        k = int(np.floor(line))
        p_under = poisson.cdf(k, mu_team)
        return 1.0 - p_under, p_under
    sig = sigma_team or 12.0
    z = (line - mu_team) / sig
    p_under = norm.cdf(z)
    return 1.0 - p_under, p_under


# ───────────────────────── Evaluador de alto nivel ─────────────────────────
def evaluate_markets(engine, home, away, market_lines, filters=None,
                     ou_confidence_floor=None):
    """
    engine: SportsEngine ya entrenado (expone expected_scores y sigmas).
    market_lines: dict con las líneas+cuotas disponibles del mercado, p.ej.:
        {
          "totals":  {"line": 8.5, "over_odds": 1.90, "under_odds": 1.95},
          "spread":  {"line": -1.5, "home_odds": 2.10, "away_odds": 1.75},
          "btts":    {"yes_odds": 1.80, "no_odds": 2.00},
          "team_total_home": {"line": 4.5, "over_odds": 1.95, "under_odds": 1.90},
        }
    filters: dict opcional {market_trust, confidence_floor, edge_threshold}.
    Devuelve lista unificada de value_bets de TODOS los mercados.
    """
    f = filters or {}
    mt = f.get("market_trust", getattr(engine, "market_trust", 0.5))
    cf = f.get("confidence_floor", getattr(engine, "confidence_floor", 0.65))
    et = f.get("edge_threshold", getattr(engine, "edge_threshold", 0.02))
    # Anclaje al mercado y gate de divergencia (protección anti-modelo-desfasado)
    anchor_w = f.get("anchor_weight", 0.5)       # cuánto acercar μ a la línea
    max_div = f.get("max_divergence", 0.20)      # si difieren >20% → rechazar mercado
    sport = engine.sport

    mu_home, mu_away = engine.expected_scores(home, away)
    sigma_total = getattr(engine, "sigma_total", None)
    sigma_margin = getattr(engine, "sigma_margin", None)
    sigma_team = getattr(engine, "sigma_team", None)

    # P2.5 — gate de divergencia más estricto para deportes líquidos (MLB/NBA ML).
    # Si el modelo difiere >12% del mercado en un deporte líquido, la causa más
    # probable es un error del modelo o información que no tenemos (lesión, lineup).
    # Mercados ilíquidos (P1 NHL, Q1 NBA, alt totals) mantienen el 20%.
    _LIQUID_SPORTS = {"mlb", "nba"}
    _sport_lower = sport.lower() if hasattr(sport, "lower") else ""
    max_div = min(max_div, 0.12) if _sport_lower in _LIQUID_SPORTS else max_div

    # Umbral específico para O/U — el modelo Poisson/Normal tiene más ruido
    # que el moneyline, así que exigimos mayor confianza para evitar falsos edge
    cf_ou = ou_confidence_floor if ou_confidence_floor is not None else min(cf + 0.06, 0.72)

    all_bets = []

    # Over / Under
    if "totals" in market_lines:
        m = market_lines["totals"]
        line = m["line"]
        model_total = mu_home + mu_away
        divergence = abs(model_total - line) / max(line, 1e-6)
        if divergence <= max_div:
            # Anclar total esperado a la línea del mercado (consenso afilado)
            anchored = (1 - anchor_w) * model_total + anchor_w * line
            scale = anchored / max(model_total, 1e-6)
            amh, ama = mu_home * scale, mu_away * scale
            p_over, p_under = prob_over_under(amh, ama, line, sport, sigma_total)

            # ── Floor asimétrico OVER vs UNDER ──────────────────────────
            # Hallazgo empírico (jun 2026): los picks OVER rinden 44% de acierto
            # mientras los UNDER rinden 67%. El modelo de anotación sobre-proyecta
            # carreras/goles de forma sistemática (pitchers/defensas con ERA media
            # tienen días dominantes más seguido de lo que la media sugiere).
            # Corrección: exigir MÁS confianza para entrar a un OVER que a un UNDER.
            over_premium = f.get("over_confidence_premium", 0.05)
            cf_over = min(cf_ou + over_premium, 0.95)

            # OVER con floor elevado
            for b in evaluate_two_way(
                    p_over, p_under, m.get("over_odds"), m.get("under_odds"),
                    f"OVER {line}", f"UNDER {line}", "O/U", mt, cf_over, et):
                if "OVER" in b["label"]:
                    all_bets.append(b)
            # UNDER con floor normal
            for b in evaluate_two_way(
                    p_over, p_under, m.get("over_odds"), m.get("under_odds"),
                    f"OVER {line}", f"UNDER {line}", "O/U", mt, cf_ou, et):
                if "UNDER" in b["label"]:
                    all_bets.append(b)
        # si divergencia > max_div: se omite (modelo fuera de distribución)

    # Hándicap / Spread
    if "spread" in market_lines:
        m = market_lines["spread"]
        line = m["line"]
        model_margin = mu_home - mu_away
        # la línea -L del local implica margen esperado ≈ -line
        market_margin = -line
        # gate: divergencia absoluta de margen (en unidades de sigma)
        sig = sigma_margin or 4.0
        if abs(model_margin - market_margin) <= max(max_div * 10, 2.5 * sig):
            anchored_margin = (1 - anchor_w) * model_margin + anchor_w * market_margin
            # reconstruir mu manteniendo el total
            tot = mu_home + mu_away
            amh = (tot + anchored_margin) / 2
            ama = (tot - anchored_margin) / 2
            p_h, p_a = prob_spread(amh, ama, line, sport, sigma_margin)
            all_bets += evaluate_two_way(
                p_h, p_a, m.get("home_odds"), m.get("away_odds"),
                f"{home} {line:+g}", f"{away} {-line:+g}", "SPREAD",
                mt, cf, et)

    # BTTS (solo deportes de bajo marcador)
    if "btts" in market_lines and _is_poisson(sport):
        m = market_lines["btts"]
        p_yes, p_no = prob_btts(mu_home, mu_away)
        all_bets += evaluate_two_way(
            p_yes, p_no, m.get("yes_odds"), m.get("no_odds"),
            "BTTS Sí", "BTTS No", "BTTS",
            mt, cf, et)

    # Team total (local)
    if "team_total_home" in market_lines:
        m = market_lines["team_total_home"]
        p_o, p_u = prob_team_total(mu_home, m["line"], sport, sigma_team)
        all_bets += evaluate_two_way(
            p_o, p_u, m.get("over_odds"), m.get("under_odds"),
            f"{home} OVER {m['line']}", f"{home} UNDER {m['line']}", "TEAM_TOT",
            mt, cf, et)

    # Team total (visita)
    if "team_total_away" in market_lines:
        m = market_lines["team_total_away"]
        p_o, p_u = prob_team_total(mu_away, m["line"], sport, sigma_team)
        all_bets += evaluate_two_way(
            p_o, p_u, m.get("over_odds"), m.get("under_odds"),
            f"{away} OVER {m['line']}", f"{away} UNDER {m['line']}", "TEAM_TOT",
            mt, cf, et)

    for b in all_bets:
        b["match"] = f"{home} vs {away}"
        b["mu_home"] = round(mu_home, 2)
        b["mu_away"] = round(mu_away, 2)
    return all_bets


if __name__ == "__main__":
    # Demo de las funciones de probabilidad
    print("=== Demo mercados ===")
    mu_h, mu_a = 4.8, 4.1  # MLB típico
    print(f"MLB μ: local {mu_h}, visita {mu_a} (total {mu_h+mu_a})")
    po, pu = prob_over_under(mu_h, mu_a, 8.5, "mlb")
    print(f"  O/U 8.5:  Over {po:.1%}  Under {pu:.1%}")
    ph, pa = prob_spread(mu_h, mu_a, -1.5, "mlb")
    print(f"  Run line -1.5:  Local cubre {ph:.1%}  Visita +1.5 {pa:.1%}")
    py, pn = prob_btts(mu_h, mu_a)
    print(f"  BTTS:  Sí {py:.1%}  No {pn:.1%}")

    print("\nNBA μ: local 113, visita 109 (total 222)")
    po, pu = prob_over_under(113, 109, 224.5, "nba", sigma_total=18)
    print(f"  O/U 224.5:  Over {po:.1%}  Under {pu:.1%}")
    ph, pa = prob_spread(113, 109, -3.5, "nba", sigma_margin=13)
    print(f"  Spread -3.5:  Local cubre {ph:.1%}  Visita +3.5 {pa:.1%}")
