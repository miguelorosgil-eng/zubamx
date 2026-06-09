"""
CLV Tracker — Closing Line Value tracking usando Pinnacle como referencia sharp.

El CLV es el gold standard de los apostadores profesionales:
si consistentemente apuestas a mejor precio que el cierre de Pinnacle,
eres rentable a largo plazo independientemente de resultados a corto plazo.

Columnas CSV:
  date, sport, home, away, pick_team, pick_side,
  odds_taken, source_book, pinnacle_close, clv, result, profit
"""

import os
import csv
import math
import requests
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CLV_CSV = "_cache/clv_history.csv"
CLV_COLUMNS = [
    "date", "sport", "home", "away", "pick_team", "pick_side",
    "odds_taken", "source_book", "pinnacle_close", "clv", "result", "profit",
]

# Pinnacle guest API
PINNACLE_BASE = "https://guest.api.pinnacle.com/v2"
PINNACLE_SPORT_IDS = {
    "MLB": 3,
    "NBA": 4,
    "NHL": 19,
    "SOCCER": 29,
}

# The Odds API fallback
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "0e72a2907fb18699be347a6507f018b3")
ODDS_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEYS = {
    "MLB": "baseball_mlb",
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "SA":  "soccer_italy_serie_a",
    "BL1": "soccer_germany_bundesliga",
    "FL1": "soccer_france_ligue_one",
}

TIMEOUT = 8  # segundos

# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _ensure_csv():
    """Crea el CSV con cabeceras si no existe."""
    os.makedirs("_cache", exist_ok=True)
    if not os.path.exists(CLV_CSV):
        with open(CLV_CSV, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CLV_COLUMNS).writeheader()


def _read_rows() -> list:
    _ensure_csv()
    with open(CLV_CSV, newline="") as f:
        return list(csv.DictReader(f))


def _write_rows(rows: list):
    _ensure_csv()
    with open(CLV_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLV_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _best_match(name: str, candidates: list, threshold=0.55) -> str | None:
    best, score = None, 0.0
    for c in candidates:
        s = _similar(name, c)
        if s > score:
            best, score = c, s
    return best if score >= threshold else None


# ---------------------------------------------------------------------------
# Funciones públicas principales
# ---------------------------------------------------------------------------

def record_pick(
    sport: str,
    home: str,
    away: str,
    pick_team: str,
    pick_side: str,       # "home" | "away" | "draw"
    odds_taken: float,
    source_book: str = "unknown",
    result: str = "",     # "1" ganó, "0" perdió, "" pendiente
    profit: float = None,
):
    """
    Registra un pick con los odds al momento de apostar.

    Los campos pinnacle_close y clv quedan vacíos hasta llamar
    a update_closing_lines().
    """
    _ensure_csv()
    row = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sport": sport.upper(),
        "home": home,
        "away": away,
        "pick_team": pick_team,
        "pick_side": pick_side,
        "odds_taken": odds_taken,
        "source_book": source_book,
        "pinnacle_close": "",
        "clv": "",
        "result": result,
        "profit": profit if profit is not None else "",
    }
    with open(CLV_CSV, "a", newline="") as f:
        csv.DictWriter(f, fieldnames=CLV_COLUMNS).writerow(row)
    print(f"[CLV] Pick registrado: {pick_team} @ {odds_taken} ({source_book})")


def calculate_clv(odds_taken: float, pinnacle_close: float) -> float:
    """
    CLV = (odds_taken / pinnacle_close - 1) * 100
    Positivo  → apostaste mejor que el mercado (buena señal).
    Negativo  → el mercado se movió en tu contra.
    """
    if pinnacle_close <= 0:
        raise ValueError("pinnacle_close debe ser mayor que 0")
    return (odds_taken / pinnacle_close - 1) * 100


# ---------------------------------------------------------------------------
# Acceso a Pinnacle / fallback Odds API
# ---------------------------------------------------------------------------

def _fetch_pinnacle_raw(sport: str) -> list:
    """
    Descarga matchups de Pinnacle para el deporte indicado.
    Retorna lista de matchups o [] si falla.
    """
    sport_id = PINNACLE_SPORT_IDS.get(sport.upper())
    if sport_id is None:
        return []
    url = f"{PINNACLE_BASE}/matchups"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        r = requests.get(url, params={"sportId": sport_id, "isLive": "false"},
                         headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            return data if isinstance(data, list) else data.get("matchups", [])
        print(f"[CLV] Pinnacle devolvió HTTP {r.status_code}")
    except Exception as e:
        print(f"[CLV] Pinnacle no disponible: {e}")
    return []


def _odds_from_pinnacle_matchup(matchup: dict, pick_side: str) -> float | None:
    """
    Extrae el moneyline decimal del matchup de Pinnacle para el side indicado.
    pick_side: "home" | "away"
    """
    try:
        periods = matchup.get("periods", [])
        for period in periods:
            if period.get("number") != 0:  # periodo full-game
                continue
            ml = period.get("moneyline", {})
            key = "home" if pick_side == "home" else "away"
            price = ml.get(key)
            if price:
                # Pinnacle devuelve American o decimal según versión.
                # Si es negativo es American; convertir.
                if isinstance(price, (int, float)) and abs(price) > 10:
                    # Probablemente American odds
                    if price > 0:
                        return round(price / 100 + 1, 4)
                    else:
                        return round(100 / abs(price) + 1, 4)
                return round(float(price), 4)
    except Exception:
        pass
    return None


def _fetch_odds_api_closing(sport: str, home: str, away: str, pick_side: str) -> float | None:
    """
    Fallback: obtiene las odds más recientes de Pinnacle via The Odds API.
    """
    sport_key = SPORT_KEYS.get(sport.upper())
    if not sport_key or not ODDS_API_KEY:
        return None
    url = f"{ODDS_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "bookmakers": "pinnacle",
    }
    try:
        r = requests.get(url, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"[CLV] The Odds API HTTP {r.status_code}")
            return None
        events = r.json()
        teams = [home, away]
        for ev in events:
            ev_teams = [ev.get("home_team", ""), ev.get("away_team", "")]
            match_home = _best_match(home, ev_teams)
            match_away = _best_match(away, ev_teams)
            if not match_home or not match_away:
                continue
            for bk in ev.get("bookmakers", []):
                if bk.get("key") != "pinnacle":
                    continue
                for mkt in bk.get("markets", []):
                    if mkt.get("key") != "h2h":
                        continue
                    for outcome in mkt.get("outcomes", []):
                        side = "home" if outcome["name"] == ev.get("home_team") else "away"
                        if side == pick_side:
                            return round(float(outcome["price"]), 4)
    except Exception as e:
        print(f"[CLV] The Odds API error: {e}")
    return None


def fetch_pinnacle_odds(sport: str, home: str, away: str, pick_side: str = "home") -> dict | None:
    """
    Intenta obtener odds de Pinnacle via API pública.

    Estrategia:
    1. API guest Pinnacle  → https://guest.api.pinnacle.com/v2/matchups
    2. The Odds API (si hay ODDS_API_KEY en env o hardcoded)
    3. Retorna None si ambos fallan, con mensaje explicativo.

    Retorna dict con claves: home, away, source
    o None si no hay datos disponibles.
    """
    # --- Intento 1: Pinnacle guest API ---
    matchups = _fetch_pinnacle_raw(sport)
    if matchups:
        for m in matchups:
            participants = m.get("participants", [])
            names = [p.get("name", "") for p in participants]
            if _best_match(home, names) and _best_match(away, names):
                home_odds = _odds_from_pinnacle_matchup(m, "home")
                away_odds = _odds_from_pinnacle_matchup(m, "away")
                if home_odds or away_odds:
                    return {
                        "home": home_odds,
                        "away": away_odds,
                        "source": "pinnacle_direct",
                    }

    # --- Intento 2: The Odds API ---
    print("[CLV] Pinnacle guest API sin resultados; intentando The Odds API...")
    home_odds = _fetch_odds_api_closing(sport, home, away, "home")
    away_odds = _fetch_odds_api_closing(sport, home, away, "away")
    if home_odds or away_odds:
        return {
            "home": home_odds,
            "away": away_odds,
            "source": "odds_api_pinnacle",
        }

    print(
        "[CLV] No se pudo obtener odds de Pinnacle.\n"
        "      Registra la línea de cierre manualmente con:\n"
        "      update_closing_lines() pasando pinnacle_close directamente."
    )
    return None


# ---------------------------------------------------------------------------
# Actualización de closing lines
# ---------------------------------------------------------------------------

def update_closing_lines(date_str: str = None):
    """
    Actualiza las líneas de cierre para picks sin pinnacle_close registrada.

    date_str: 'YYYY-MM-DD' o None → usa el día anterior.
    """
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    rows = _read_rows()
    updated = 0

    for row in rows:
        if row["date"] != date_str:
            continue
        if row["pinnacle_close"]:  # ya tiene closing line
            continue

        sport = row["sport"]
        home  = row["home"]
        away  = row["away"]
        side  = row["pick_side"]

        result = fetch_pinnacle_odds(sport, home, away, side)
        if result is None:
            continue

        pin_close = result.get(side)
        if pin_close is None:
            continue

        row["pinnacle_close"] = pin_close
        try:
            odds_taken = float(row["odds_taken"])
            row["clv"] = round(calculate_clv(odds_taken, pin_close), 4)
        except (ValueError, ZeroDivisionError):
            row["clv"] = ""
        updated += 1

    _write_rows(rows)
    print(f"[CLV] Closing lines actualizadas para {date_str}: {updated} picks procesados.")


# ---------------------------------------------------------------------------
# Reporte CLV
# ---------------------------------------------------------------------------

def get_clv_report() -> dict:
    """
    Reporte completo de CLV:
    - CLV promedio total
    - CLV por deporte
    - CLV por tipo de mercado (pick_side)
    - Correlación CLV vs resultado real
    - ROI real vs ROI esperado por CLV
    - Distribución de CLV (buckets para gráfico ASCII)
    """
    rows = _read_rows()
    valid = [r for r in rows if r.get("clv") and r["clv"] != ""]

    if not valid:
        return {"error": "Sin picks con CLV calculado aún."}

    clvs   = [float(r["clv"]) for r in valid]
    avg_clv = sum(clvs) / len(clvs)

    # CLV por deporte
    by_sport: dict[str, list] = {}
    for r in valid:
        by_sport.setdefault(r["sport"], []).append(float(r["clv"]))
    clv_by_sport = {s: round(sum(v) / len(v), 4) for s, v in by_sport.items()}

    # CLV por pick_side
    by_side: dict[str, list] = {}
    for r in valid:
        by_side.setdefault(r["pick_side"], []).append(float(r["clv"]))
    clv_by_side = {s: round(sum(v) / len(v), 4) for s, v in by_side.items()}

    # Correlación CLV vs resultado (picks con resultado registrado)
    result_rows = [r for r in valid if r.get("result") in ("0", "1")]
    correlation = None
    if len(result_rows) >= 5:
        xs = [float(r["clv"]) for r in result_rows]
        ys = [float(r["result"]) for r in result_rows]
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        num   = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
        den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
        correlation = round(num / (den_x * den_y), 4) if den_x * den_y > 0 else None

    # ROI real
    profit_rows = [r for r in rows if r.get("profit") and r["profit"] != ""]
    stake_rows  = [r for r in profit_rows if r.get("odds_taken")]
    real_roi = None
    if stake_rows:
        total_profit = sum(float(r["profit"]) for r in profit_rows)
        # Aproximamos stake unitario desde profit y odds si no hay columna stake
        real_roi = round(total_profit / len(profit_rows) * 100, 4)

    # ROI esperado por CLV (teoría: ROI ≈ CLV promedio ajustado por margen)
    expected_roi = round(avg_clv * 0.85, 4)  # factor conservador

    # Distribución de CLV en buckets de 1%
    bucket_size = 1.0
    min_clv = math.floor(min(clvs))
    max_clv = math.ceil(max(clvs))
    buckets: dict[str, int] = {}
    for i in range(min_clv, max_clv + 1):
        label = f"{i:+d}%"
        buckets[label] = sum(1 for c in clvs if i <= c < i + bucket_size)

    return {
        "total_picks_with_clv": len(valid),
        "avg_clv": round(avg_clv, 4),
        "clv_by_sport": clv_by_sport,
        "clv_by_side": clv_by_side,
        "correlation_clv_result": correlation,
        "real_roi_pct": real_roi,
        "expected_roi_by_clv_pct": expected_roi,
        "clv_distribution": buckets,
        "positive_clv_rate": round(sum(1 for c in clvs if c > 0) / len(clvs) * 100, 2),
    }


def _ascii_histogram(distribution: dict, width: int = 40) -> str:
    """Genera un gráfico ASCII de barras horizontales."""
    if not distribution:
        return "(sin datos)"
    max_count = max(distribution.values()) or 1
    lines = []
    for label, count in sorted(
        distribution.items(),
        key=lambda kv: int(kv[0].replace("%", "").replace("+", "")),
    ):
        bar_len = int(count / max_count * width)
        bar = "█" * bar_len
        lines.append(f"  {label:>5} │{bar:<{width}}│ {count}")
    return "\n".join(lines)


def print_clv_report():
    """Imprime el reporte de CLV formateado."""
    report = get_clv_report()

    if "error" in report:
        print(f"\n[CLV] {report['error']}")
        return

    sep = "─" * 56
    print(f"\n{'═'*56}")
    print(f"  CLOSING LINE VALUE REPORT")
    print(f"{'═'*56}")
    print(f"  Picks con CLV calculado : {report['total_picks_with_clv']}")
    print(f"  CLV promedio            : {report['avg_clv']:+.2f}%")
    print(f"  % picks con CLV positivo: {report['positive_clv_rate']:.1f}%")

    if report.get("real_roi_pct") is not None:
        print(f"  ROI real (aprox)        : {report['real_roi_pct']:+.2f}%")
    print(f"  ROI esperado por CLV    : {report['expected_roi_by_clv_pct']:+.2f}%")

    if report.get("correlation_clv_result") is not None:
        print(f"  Correlación CLV/result  : {report['correlation_clv_result']:.4f}")

    print(f"\n{sep}")
    print("  CLV por deporte:")
    for sport, val in sorted(report["clv_by_sport"].items()):
        print(f"    {sport:<8} {val:+.2f}%")

    print(f"\n{sep}")
    print("  CLV por mercado (pick_side):")
    for side, val in sorted(report["clv_by_side"].items()):
        print(f"    {side:<8} {val:+.2f}%")

    print(f"\n{sep}")
    print("  Distribución de CLV:")
    print(_ascii_histogram(report["clv_distribution"]))
    print(f"{'═'*56}\n")


# ---------------------------------------------------------------------------
# Verificación de +EV
# ---------------------------------------------------------------------------

def is_positive_ev(model_p: float, pinnacle_odds: float) -> tuple:
    """
    Verifica si hay +EV comparando probabilidad del modelo vs odds de Pinnacle.

    Pinnacle tiene un margen muy bajo (~2.5%), así que sus implied probs
    son casi fair. Comparamos directamente.

    Retorna: (bool es_positive_ev, float edge_pct, str recommendation)
    """
    if pinnacle_odds <= 1.0:
        return (False, 0.0, "Odds inválidas")

    pinnacle_implied_p = 1.0 / pinnacle_odds
    edge = model_p - pinnacle_implied_p

    # Umbral conservador: >3% de edge real para recomendar
    if edge > 0.03:
        rec = f"+EV confirmado: edge de {edge*100:.1f}% vs Pinnacle. APOSTAR."
    elif edge > 0.0:
        rec = f"Edge marginal ({edge*100:.1f}%). Proceder con cautela."
    else:
        rec = f"Sin +EV (edge negativo: {edge*100:.1f}%). NO apostar."

    return (edge > 0.03, round(edge * 100, 2), rec)


# ---------------------------------------------------------------------------
# Simulación de CLV desde historial de backtest
# ---------------------------------------------------------------------------

def simulate_clv_from_history(sport: str) -> dict:
    """
    Lee backtest_v2_{sport}.csv y simula el CLV del sistema comparando
    p_cal (probabilidad calibrada del modelo) vs p_implied (prob implícita
    del mercado usado en backtest).

    Esta es una proxy del CLV real cuando no tenemos Pinnacle histórico.

    Retorna dict con estadísticas de CLV simulado.
    """
    import os

    sport_up = sport.upper()
    path = f"_cache/backtest_v2_{sport_up}.csv"
    if not os.path.exists(path):
        return {"error": f"No se encontró {path}"}

    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"error": "Archivo vacío"}

    sim_clvs = []
    wins = 0
    total_profit = 0.0

    for r in rows:
        try:
            p_cal     = float(r["p_cal"])
            p_implied = float(r["p_implied"])
            odds      = float(r.get("odds", 0))
            result    = int(r.get("result", 0))
            profit    = float(r.get("profit", 0))
        except (ValueError, KeyError):
            continue

        if p_implied <= 0 or odds <= 0:
            continue

        # Odds del modelo (fair odds según calibración)
        model_fair_odds = 1.0 / p_cal if p_cal > 0 else None
        # Odds del mercado implícita
        market_odds = 1.0 / p_implied

        if model_fair_odds:
            # CLV simulado: cuánto mejor fue la prob del modelo vs mercado
            sim_clv = (odds / market_odds - 1) * 100
            sim_clvs.append(sim_clv)

        wins += result
        total_profit += profit

    if not sim_clvs:
        return {"error": "No hay datos válidos para simulación CLV"}

    avg_sim_clv = sum(sim_clvs) / len(sim_clvs)
    positive_rate = sum(1 for c in sim_clvs if c > 0) / len(sim_clvs) * 100
    roi = total_profit / len(sim_clvs) * 100 if sim_clvs else 0

    # Distribución
    min_b = math.floor(min(sim_clvs))
    max_b = math.ceil(max(sim_clvs))
    distribution = {}
    for i in range(min_b, max_b + 1):
        distribution[f"{i:+d}%"] = sum(1 for c in sim_clvs if i <= c < i + 1)

    print(f"\n[CLV Simulado] {sport_up} — {len(sim_clvs)} picks analizados")
    print(f"  CLV promedio simulado : {avg_sim_clv:+.2f}%")
    print(f"  % picks CLV positivo  : {positive_rate:.1f}%")
    print(f"  ROI real (backtest)   : {roi:+.2f}%")
    print(f"\n  Distribución CLV simulado:")
    print(_ascii_histogram(distribution, width=30))

    return {
        "sport": sport_up,
        "picks_analyzed": len(sim_clvs),
        "avg_simulated_clv": round(avg_sim_clv, 4),
        "positive_clv_rate_pct": round(positive_rate, 2),
        "real_roi_pct": round(roi, 4),
        "wins": wins,
        "distribution": distribution,
        "note": (
            "CLV simulado usando odds de mercado del backtest como proxy de Pinnacle. "
            "No es CLV real pero indica si el sistema tuvo edge consistente."
        ),
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    rows = _read_rows() if os.path.exists(CLV_CSV) else []
    has_clv = any(r.get("clv") for r in rows)

    if has_clv:
        print_clv_report()
    elif rows:
        print("\n[CLV] Hay picks registrados pero sin closing lines aún.")
        print("      Ejecuta update_closing_lines() para poblar el CLV.")
        print("      Ejemplo:")
        print("        from clv_tracker import update_closing_lines")
        print("        update_closing_lines()  # usa el día anterior")
    else:
        print("\n" + "═" * 56)
        print("  CLV TRACKER — Setup")
        print("═" * 56)
        print("""
  No hay picks registrados todavía.

  1. Registra tus picks al momento de apostar:
       from clv_tracker import record_pick
       record_pick(
           sport="MLB",
           home="New York Yankees",
           away="Boston Red Sox",
           pick_team="New York Yankees",
           pick_side="home",
           odds_taken=1.91,
           source_book="DraftKings",
       )

  2. Al día siguiente, actualiza las closing lines:
       from clv_tracker import update_closing_lines
       update_closing_lines()

  3. Ve el reporte completo:
       from clv_tracker import print_clv_report
       print_clv_report()

  4. Simula el CLV histórico del sistema desde backtest:
       from clv_tracker import simulate_clv_from_history
       simulate_clv_from_history("MLB")
       simulate_clv_from_history("NBA")
       simulate_clv_from_history("NHL")

  NOTA: Configura ODDS_API_KEY en el entorno para usar
        The Odds API como fallback si Pinnacle no responde.
        El key actual en conector_odds.py ya está disponible.
""")

    # Demo: simular CLV desde backtest existente
    print("\n" + "─" * 56)
    print("  Simulando CLV histórico desde backtests...")
    print("─" * 56)
    for sport in ("MLB", "NBA", "NHL"):
        path = f"_cache/backtest_v2_{sport}.csv"
        if os.path.exists(path):
            simulate_clv_from_history(sport)
        else:
            print(f"  [{sport}] No hay backtest_v2_{sport}.csv")
