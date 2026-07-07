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

# Tasa base real de YRFI (una carrera anota en la 1ª): 54% (backtest 603 juegos)
BASE_YRFI = 0.54


def clasificar_partido(era_home_sp, era_away_sp):
    """
    Regla ganadora del backtest segmentado (603 juegos). Clasifica el partido
    según el ERA del pitcher MÁS FLOJO (max de los dos), que es lo que predice
    si cae carrera en la 1ª:

      max ERA >= 5.5  -> YRFI (SÍ carrera), acierta 67%
      max ERA <= 4.0  -> NRFI (NO carrera), acierta 62%
      en medio (4.0-5.5) -> NO apostar (volado, 54%)

    Devuelve (lado, prob_real) o (None, None) si es zona media.
    """
    if era_home_sp is None or era_away_sp is None:
        return None, None
    max_era = max(era_home_sp, era_away_sp)
    if max_era >= 5.5:
        return "YRFI", 0.67
    if max_era <= 4.0:
        return "NRFI", 0.62
    return None, None  # zona media: sin edge, no se apuesta


def yrfi_calibrada(era_home_sp, era_away_sp):
    """Retrocompat: devuelve prob YRFI o None si es zona media."""
    lado, prob = clasificar_partido(era_home_sp, era_away_sp)
    if lado == "YRFI":
        return prob
    if lado == "NRFI":
        return 1 - prob
    return None


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
