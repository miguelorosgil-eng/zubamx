"""
Conector KBO (Corea) y NPB (Japón) — béisbol asiático vía The Odds API.

Situación de datos (verificado jul 2026):
  - ESPN NO cubre béisbol asiático (no está en su lista de ligas).
  - The Odds API SÍ lista baseball_kbo / baseball_npb, pero su endpoint de
    scores solo entrega 3 días hacia atrás en el plan gratuito, y el histórico
    de odds está tras muro de pago.

Estrategia honesta: ACUMULADOR. Cada corrida guarda los resultados completados
de los últimos 3 días en un CSV de entrenamiento (deduplicando). Como KBO/NPB
juegan ~5 partidos/día, en ~2 semanas se juntan los ≥50 partidos que el motor
necesita para entrenar. No se fabrican datos: se acumulan resultados reales.
"""
import os
import csv
import requests
import pandas as pd
from datetime import date

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "0e72a2907fb18699be347a6507f018b3")
ODDS_BASE = "https://api.the-odds-api.com/v4"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")

SPORT_KEYS = {"KBO": "baseball_kbo", "NPB": "baseball_npb"}
COLS = ["game_id", "date", "home", "away", "home_score", "away_score"]


def _training_path(code):
    return os.path.join(CACHE_DIR, f"training_{code}.csv")


def accumulate_results(code):
    """
    Descarga los scores completados de los últimos 3 días y los añade al CSV
    de entrenamiento (idempotente por game_id). Devuelve nº de filas nuevas.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    sk = SPORT_KEYS[code]
    r = requests.get(f"{ODDS_BASE}/sports/{sk}/scores",
                     params={"apiKey": ODDS_API_KEY, "daysFrom": 3}, timeout=20)
    r.raise_for_status()

    path = _training_path(code)
    existing = set()
    if os.path.exists(path):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                existing.add(row["game_id"])

    new_rows = []
    for ev in r.json():
        if not ev.get("completed"):
            continue
        gid = ev.get("id")
        if not gid or gid in existing:
            continue
        scores = {s["name"]: s.get("score") for s in (ev.get("scores") or [])}
        home, away = ev["home_team"], ev["away_team"]
        hs, as_ = scores.get(home), scores.get(away)
        if hs is None or as_ is None:
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (ValueError, TypeError):
            continue
        new_rows.append({
            "game_id": gid,
            "date": ev.get("commence_time", "")[:10],
            "home": home, "away": away,
            "home_score": hs, "away_score": as_,
        })
        existing.add(gid)

    if new_rows:
        write_header = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            if write_header:
                w.writeheader()
            w.writerows(new_rows)
    return len(new_rows)


def build_asia_training(code, seasons=None):
    """
    Carga el CSV acumulado (tras intentar sumar los resultados más recientes).
    seasons se ignora (no hay histórico); la firma se mantiene por compatibilidad
    con el pipeline. Devuelve DataFrame con columnas del motor.
    """
    try:
        n = accumulate_results(code)
        if n:
            print(f"  [{code}] +{n} resultados nuevos acumulados")
    except Exception as e:
        print(f"  [{code}] no se pudieron acumular resultados: {e}")

    path = _training_path(code)
    if not os.path.exists(path):
        return pd.DataFrame(columns=["home", "away", "home_score", "away_score", "date"])
    df = pd.read_csv(path, parse_dates=["date"])
    return df[["home", "away", "home_score", "away_score", "date"]].reset_index(drop=True)


def fetch_asia_upcoming(code):
    """Partidos próximos con odds disponibles (para saber qué se juega)."""
    sk = SPORT_KEYS[code]
    r = requests.get(f"{ODDS_BASE}/sports/{sk}/odds",
                     params={"apiKey": ODDS_API_KEY, "regions": "us",
                             "markets": "h2h", "oddsFormat": "decimal"}, timeout=20)
    r.raise_for_status()
    rows = []
    for ev in r.json():
        rows.append({"home": ev["home_team"], "away": ev["away_team"],
                     "date": pd.Timestamp(ev["commence_time"][:10]),
                     "game_id": ev.get("id", "")})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    for code in ["KBO", "NPB"]:
        n = accumulate_results(code)
        df = build_asia_training(code)
        print(f"{code}: {n} nuevos | total acumulado {len(df)} partidos "
              f"(faltan {max(0, 50 - len(df))} para entrenar)")
