"""
Escáner de PRIMERA ENTRADA (NRFI/YRFI) — el único mercado que pasó la prueba.

Backtest de 445 juegos (jun 2026): el modelo de 1er inning DISCRIMINA de verdad
(cuando dice YRFI alto la realidad es 60%; cuando dice bajo, 36%). A diferencia
de totales/props, aquí sí hay señal. Pero el modelo crudo es sobre-confiado, así
que se RECALIBRA con el mapeo empírico del backtest.

Método (idea del usuario): cruzar TODAS las casas con las estadísticas.
  1. Modelo recalibrado → probabilidad real de YRFI.
  2. Escanear todas las casas → mejor precio disponible (line shopping).
  3. Pick solo si prob_real * mejor_momio - 1 >= umbral EV, momio >= 1.70.
"""
import requests
from mercados import prob_nrfi

ODDS_API_KEY = "0e72a2907fb18699be347a6507f018b3"
BASE = "https://api.the-odds-api.com/v4"

# Tasa base real de YRFI (una carrera anota en la 1ª): 54% (backtest 445 juegos)
BASE_YRFI = 0.54


def yrfi_calibrada(era_home_sp, era_away_sp):
    """
    Probabilidad REAL de YRFI, recalibrada con el backtest.
    El modelo ERA crudo sobre-estima; se mapea a la realidad observada:
      modelo >=0.60 -> 0.60 real | 0.55-0.60 -> 0.49 | <0.55 -> 0.40
    """
    p_nrfi, p_yrfi = prob_nrfi(era_home_sp, era_away_sp)
    if p_yrfi is None:
        return None
    if p_yrfi >= 0.60:
        return 0.60
    if p_yrfi >= 0.55:
        return 0.49
    return 0.40


def _events(date_str):
    r = requests.get(f"{BASE}/sports/baseball_mlb/events",
                     params={"apiKey": ODDS_API_KEY}, timeout=20)
    r.raise_for_status()
    return [e for e in r.json() if e.get("commence_time", "")[:10] == date_str]


def _first_inning_odds(eid):
    """Todas las casas para el mercado de 1er inning (línea 0.5)."""
    r = requests.get(f"{BASE}/sports/baseball_mlb/events/{eid}/odds",
                     params={"apiKey": ODDS_API_KEY, "regions": "us",
                             "markets": "totals_1st_1_innings", "oddsFormat": "decimal"},
                     timeout=20)
    if r.status_code != 200:
        return [], []
    yrfi, nrfi = [], []
    for bk in r.json().get("bookmakers", []):
        for m in bk.get("markets", []):
            for o in m["outcomes"]:
                if o.get("point") == 0.5:
                    (yrfi if o["name"] == "Over" else nrfi).append((bk["title"], o["price"]))
    return yrfi, nrfi


def escanear(date_str, era_map, min_ev=0.05, min_odds=1.70):
    """
    era_map: {(away_team, home_team): (era_away_sp, era_home_sp)}.
    Devuelve lista de candidatos con mejor precio y EV.
    """
    picks = []
    for ev in _events(date_str):
        h, a = ev["home_team"], ev["away_team"]
        key = (a, h)
        if key not in era_map:
            continue
        ea, eh = era_map[key]
        p_yrfi = yrfi_calibrada(eh, ea)
        if p_yrfi is None:
            continue
        p_nrfi = 1 - p_yrfi
        yrfi_odds, nrfi_odds = _first_inning_odds(ev["id"])
        if not yrfi_odds:
            continue
        for side, prob, book_odds in [("YRFI", p_yrfi, yrfi_odds),
                                       ("NRFI", p_nrfi, nrfi_odds)]:
            if not book_odds:
                continue
            best_book, best_price = max(book_odds, key=lambda x: x[1])
            edge = prob * best_price - 1
            if edge >= min_ev and best_price >= min_odds:
                # Kelly 1/4
                kelly = max(0, (prob * best_price - 1) / (best_price - 1)) * 0.25
                picks.append({
                    "game": f"{a} @ {h}", "side": side,
                    "prob_real": round(prob, 3), "best_price": best_price,
                    "best_book": best_book, "edge": round(edge, 3),
                    "kelly_frac": round(kelly, 3),
                    "all_books": book_odds,
                })
    picks.sort(key=lambda p: -p["edge"])
    return picks


def print_picks(picks, bank=10000):
    if not picks:
        print("Sin candidatos de 1er inning hoy."); return
    print("=" * 60)
    print("CANDIDATOS 1er INNING (mejor precio + stats recalibradas)")
    print("=" * 60)
    for p in picks:
        stake = bank * p["kelly_frac"]
        print(f"\n{p['game']} — {p['side']}")
        print(f"  prob real {p['prob_real']:.0%} | mejor momio {p['best_price']} "
              f"({p['best_book']}) | EV {p['edge']:+.0%}")
        print(f"  stake Kelly 1/4: ${stake:.0f}  ({p['kelly_frac']*100:.1f}% de banca)")
        print(f"  todas las casas: {[(b[:8], o) for b, o in p['all_books']]}")


if __name__ == "__main__":
    import sys
    date_str = sys.argv[1] if len(sys.argv) > 1 else None
    if not date_str:
        import datetime
        date_str = datetime.date.today().isoformat()
    # ERAs se pasan desde el runner; ejemplo vacío
    print(f"Escaneo 1er inning {date_str} — pasar era_map desde el pipeline.")
