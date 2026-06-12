"""
Phase 4 — Line Shopper.

Busca el mejor precio disponible entre múltiples books para un pick dado,
pero SOLO acepta favoritos p∈[0.55, 0.90] con edge real ≥1%.
Longshots (p<0.55) y super-favoritos (p>0.90) están PROHIBIDOS.

Regla de oro: p_justa × best_odd ≥ 1.01  (edge mínimo del 1%)

Uso:
    from line_shopper import find_best_line, filter_shoppable
    best = find_best_line("MLB", "New York Yankees", "Boston Red Sox", p_justa=0.68)
"""

import os
from typing import Optional

# Rango de favoritos aceptados
P_MIN = 0.55
P_MAX = 0.90
EDGE_MIN = 0.01   # 1% de edge mínimo vs fair value

# Books en orden de preferencia (sharp primero)
BOOK_PRIORITY = ["pinnacle", "bet365", "draftkings", "fanduel", "betmgm", "caesars"]


def _novig_price(odds_h: float, odds_a: float) -> tuple[float, float]:
    """Quita la vig de un mercado de dos vías."""
    rh, ra = 1.0 / odds_h, 1.0 / odds_a
    tot = rh + ra
    return rh / tot, ra / tot


def is_shoppable(p_justa: float) -> bool:
    """
    True si el pick está en el rango de favoritos donde el line shopping
    tiene sentido. Longshots y super-favoritos quedan fuera.
    """
    return P_MIN <= p_justa <= P_MAX


def fair_odds(p: float) -> float:
    """Odds justas (sin margen) para una probabilidad dada."""
    if p <= 0 or p >= 1:
        return 0.0
    return round(1.0 / p, 4)


def has_edge(p_justa: float, best_odd: float) -> bool:
    """True si p_justa × best_odd ≥ 1.01 (edge ≥1%)."""
    return p_justa * best_odd >= 1.0 + EDGE_MIN


def find_best_line(
    sport: str,
    home: str,
    away: str,
    pick_side: str,          # "home" | "away"
    p_justa: float,          # probabilidad calibrada del modelo
    date_str: str = None,    # YYYY-MM-DD (para logs)
    verbose: bool = False,
) -> dict:
    """
    Busca el mejor precio entre los books disponibles via The Odds API.

    Reglas:
    - Solo acepta p_justa ∈ [0.55, 0.90]  (favoritos moderados)
    - Requiere edge ≥ 1%  (p_justa × best_odd ≥ 1.01)
    - Longshots PROHIBIDOS (p < 0.55)
    - Super-favoritos PROHIBIDOS (p > 0.90 → precio tan bajo que el edge es ruido)

    Retorna dict con:
        best_book, best_odd, edge_pct, shoppable, rechazado_por
    """
    result = {
        "sport": sport,
        "home": home,
        "away": away,
        "pick_side": pick_side,
        "p_justa": round(p_justa, 4),
        "fair_odd": fair_odds(p_justa),
        "best_book": None,
        "best_odd": None,
        "edge_pct": None,
        "shoppable": False,
        "rechazado_por": None,
        "all_odds": {},
    }

    # Filtro 1: rango de probabilidad
    if p_justa < P_MIN:
        result["rechazado_por"] = f"longshot (p={p_justa:.3f} < {P_MIN})"
        return result
    if p_justa > P_MAX:
        result["rechazado_por"] = f"super-favorito (p={p_justa:.3f} > {P_MAX})"
        return result

    # Obtener odds de múltiples books
    odds_by_book = _fetch_multi_book_odds(sport, home, away)
    if not odds_by_book:
        result["rechazado_por"] = "sin odds de mercado disponibles"
        return result

    # Encontrar el mejor precio para el lado seleccionado
    best_book, best_odd = None, 0.0
    all_odds = {}
    for book, (oh, oa) in odds_by_book.items():
        odd = oh if pick_side == "home" else oa
        if odd and odd > 1.0:
            all_odds[book] = round(odd, 4)
            if odd > best_odd:
                best_odd = odd
                best_book = book

    result["all_odds"] = all_odds

    if not best_odd or best_odd <= 1.0:
        result["rechazado_por"] = "odds inválidas en todos los books"
        return result

    # Filtro 2: edge mínimo
    edge = p_justa * best_odd - 1.0
    result["best_book"] = best_book
    result["best_odd"] = round(best_odd, 4)
    result["edge_pct"] = round(edge * 100, 2)

    if not has_edge(p_justa, best_odd):
        result["rechazado_por"] = (
            f"edge insuficiente ({edge*100:.2f}% < {EDGE_MIN*100:.0f}%)"
        )
        return result

    result["shoppable"] = True

    if verbose:
        print(f"  [LineShop] {home} vs {away} ({pick_side})")
        print(f"    p_justa={p_justa:.3f}  fair_odd={result['fair_odd']}")
        print(f"    MEJOR: {best_book} @ {best_odd}  edge={edge*100:+.2f}%")
        for bk, od in sorted(all_odds.items(), key=lambda x: -x[1]):
            marker = " ← MEJOR" if bk == best_book else ""
            print(f"    {bk:<15} {od:.4f}{marker}")

    return result


def filter_shoppable(picks: list, verbose: bool = False) -> list:
    """
    Filtra una lista de picks del analisis_dia para quedarse solo con
    los que pasan el filtro de line shopping (favoritos moderados + edge ≥1%).

    picks: lista de dicts del formato analisis_dia (model_p, odds_offered, home, away, ...)
    Retorna lista filtrada con campo "best_line" agregado.
    """
    results = []
    n_rejected = 0

    for pick in picks:
        p = pick.get("model_p", 0.0)
        home = pick.get("home", "")
        away = pick.get("away", "")
        sport = pick.get("sport", "")

        # Determinar pick_side
        label = pick.get("label", "")
        pick_side = "home" if home and home in label else "away"

        best = find_best_line(sport, home, away, pick_side, p, verbose=verbose)

        if best["shoppable"]:
            enriched = dict(pick)
            enriched["best_line"] = best
            # Actualizar odds con el mejor precio encontrado
            if best["best_odd"] and best["best_odd"] > pick.get("odds_offered", 0):
                enriched["odds_offered"] = best["best_odd"]
                enriched["best_book"] = best["best_book"]
            results.append(enriched)
        else:
            n_rejected += 1
            if verbose:
                print(f"  [LineShop] RECHAZADO {home} vs {away}: {best['rechazado_por']}")

    if verbose and n_rejected:
        print(f"  [LineShop] {n_rejected} picks rechazados por line shopper.")

    return results


def _fetch_multi_book_odds(sport: str, home: str, away: str) -> dict:
    """
    Descarga odds de múltiples books via The Odds API.
    Retorna {book_key: (odds_home, odds_away)}.
    """
    try:
        from conector_odds import ODDS_API_KEY, _SPORT_KEYS
        import requests

        sport_key = _SPORT_KEYS.get(sport.upper())
        if not sport_key or not ODDS_API_KEY:
            return {}

        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us,eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
            "bookmakers": ",".join(BOOK_PRIORITY),
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()

        events = r.json()
        from difflib import SequenceMatcher

        def _sim(a, b):
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()

        # Buscar el partido
        for ev in events:
            sh = _sim(home, ev.get("home_team", ""))
            sa = _sim(away, ev.get("away_team", ""))
            if (sh + sa) / 2 < 0.55:
                continue
            # Extraer odds por book
            result = {}
            for bk in ev.get("bookmakers", []):
                key = bk.get("key", "")
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    outcomes = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                    oh = outcomes.get(ev["home_team"])
                    oa = outcomes.get(ev["away_team"])
                    if oh and oa:
                        result[key] = (float(oh), float(oa))
            return result
    except Exception:
        pass
    return {}


def print_shopping_report(picks_with_lines: list):
    """Imprime tabla comparativa de precios por pick."""
    if not picks_with_lines:
        print("  [LineShop] Sin picks para mostrar.")
        return
    print(f"\n{'═'*65}")
    print("  LINE SHOPPING — mejores precios disponibles")
    print(f"{'═'*65}")
    print(f"  {'Pick':<30} {'p_justa':>8} {'fair':>6} {'best_odd':>9} {'edge':>7}  book")
    print(f"  {'-'*63}")
    for p in picks_with_lines:
        bl = p.get("best_line", {})
        if not bl.get("shoppable"):
            continue
        label = p.get("label", "")[:29]
        print(
            f"  {label:<30} {bl['p_justa']:>8.3f} {bl['fair_odd']:>6.3f} "
            f"{bl['best_odd']:>9.4f} {bl['edge_pct']:>+7.2f}%  {bl['best_book']}"
        )
    print(f"{'═'*65}\n")
