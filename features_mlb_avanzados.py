"""
features_mlb_avanzados.py — Features avanzados para MLB.

Calcula features adicionales a partir del historial de partidos sin data leakage
(solo datos anteriores al partido en cuestión).

Features generados por equipo (home/away):
  - pitcher_rest_days_home/away   : días desde el último partido del equipo
  - bullpen_era_7d_home/away      : proxy ERA bulevar últimos 7d (runs concedidos últimos 3 juegos)
  - team_ops_7d_home/away         : promedio de carreras anotadas últimos 7 días
  - momentum_home/away            : suma de resultados (+1 win, -1 loss) últimos 5 partidos
  - is_back_to_back_home/away     : 1 si jugó ayer
  - season_pct_home/away          : fracción de temporada transcurrida
  - context                       : 'early' | 'mid' | 'late' | 'playoff'
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from collections import defaultdict, deque
from typing import Optional

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
MOMENTUM_WINDOW = 5
OPS_DAYS = 7
ERA_GAMES = 3        # número de partidos para proxy ERA
EARLY_GAMES = 30     # primeros N partidos → 'early'
LATE_GAMES = 30      # últimos N partidos → 'late'
NEUTRAL_RUNS = 4.5   # valor neutro de carreras cuando no hay historial


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _team_game_index(df: pd.DataFrame) -> dict[str, list[int]]:
    """Devuelve {team: [row_idx, ...]} en orden cronológico."""
    idx: dict[str, list[int]] = defaultdict(list)
    for i, row in df.iterrows():
        idx[row["home"]].append(i)
        idx[row["away"]].append(i)
    return idx


def _season_bounds(df: pd.DataFrame) -> dict[int, tuple[pd.Timestamp, pd.Timestamp]]:
    """Límites (min_date, max_date) por temporada (columna season si existe)."""
    if "season" not in df.columns:
        # Inferir año del campo date
        df = df.copy()
        df["season"] = df["date"].dt.year
    bounds: dict[int, tuple] = {}
    for season, g in df.groupby("season"):
        bounds[int(season)] = (g["date"].min(), g["date"].max())
    return bounds


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def enrich_mlb_training(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recibe df con columnas: home, away, home_score, away_score, date
    (y opcionalmente season, game_id).
    Devuelve df con features adicionales, calculados sin data leakage.
    """
    df = _ensure_datetime(df)
    df = df.sort_values("date").reset_index(drop=True)

    if "season" not in df.columns:
        df["season"] = df["date"].dt.year

    season_bounds = _season_bounds(df)

    # Estado por equipo (actualizado después de procesar cada partido)
    # last_date[team]          → última fecha jugada
    # scores_for[team]         → deque de (date, runs_scored)
    # scores_against[team]     → deque de (date, runs_allowed)
    # results[team]            → deque(maxlen=5) de +1/-1
    # game_count[team][season] → número de partidos jugados en esa temporada

    last_date: dict[str, pd.Timestamp] = {}
    scores_for: dict[str, deque] = defaultdict(lambda: deque())
    scores_against: dict[str, deque] = defaultdict(lambda: deque())
    results_dq: dict[str, deque] = defaultdict(lambda: deque(maxlen=MOMENTUM_WINDOW))
    game_count: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    rows_out = []

    for _, row in df.iterrows():
        home = row["home"]
        away = row["away"]
        date = row["date"]
        h_score = float(row["home_score"])
        a_score = float(row["away_score"])
        season = int(row["season"])

        # ------------------------------------------------------------------ #
        # 1. pitcher_rest_days
        # ------------------------------------------------------------------ #
        if home in last_date:
            pitcher_rest_home = (date - last_date[home]).days
        else:
            pitcher_rest_home = np.nan  # sin historial

        if away in last_date:
            pitcher_rest_away = (date - last_date[away]).days
        else:
            pitcher_rest_away = np.nan

        # ------------------------------------------------------------------ #
        # 2. is_back_to_back
        # ------------------------------------------------------------------ #
        b2b_home = 1 if (home in last_date and pitcher_rest_home == 1) else 0
        b2b_away = 1 if (away in last_date and pitcher_rest_away == 1) else 0

        # ------------------------------------------------------------------ #
        # 3. team_ops_7d  (proxy: promedio carreras anotadas últimos 7 días)
        # ------------------------------------------------------------------ #
        cutoff_7d = date - pd.Timedelta(days=OPS_DAYS)

        def ops_proxy(team: str) -> float:
            recent = [s for d, s in scores_for[team] if d >= cutoff_7d]
            return float(np.mean(recent)) if recent else np.nan

        ops_home = ops_proxy(home)
        ops_away = ops_proxy(away)

        # ------------------------------------------------------------------ #
        # 4. bullpen_era_7d  (proxy: runs concedidos últimos ERA_GAMES juegos)
        # ------------------------------------------------------------------ #
        def bullpen_era_proxy(team: str) -> float:
            # Usa los últimos ERA_GAMES valores de scores_against
            hist = list(scores_against[team])
            if not hist:
                return np.nan
            recent = hist[-ERA_GAMES:]
            return float(np.mean([s for _, s in recent]))

        era_home = bullpen_era_proxy(home)
        era_away = bullpen_era_proxy(away)

        # ------------------------------------------------------------------ #
        # 5. momentum (últimos 5 partidos: +1 victoria, -1 derrota)
        # ------------------------------------------------------------------ #
        def momentum(team: str) -> float:
            if not results_dq[team]:
                return 0.0
            return float(sum(results_dq[team]))

        mom_home = momentum(home)
        mom_away = momentum(away)

        # ------------------------------------------------------------------ #
        # 6. season_pct
        # ------------------------------------------------------------------ #
        def season_pct(team: str) -> float:
            s_min, s_max = season_bounds.get(season, (date, date))
            total_days = (s_max - s_min).days
            if total_days == 0:
                return 0.0
            elapsed = (date - s_min).days
            return float(np.clip(elapsed / total_days, 0.0, 1.0))

        spct_home = season_pct(home)
        spct_away = season_pct(away)

        # ------------------------------------------------------------------ #
        # 7. context
        # ------------------------------------------------------------------ #
        def get_context(team: str) -> str:
            # Usar is_playoff si existe
            if "is_playoff" in row.index and row.get("is_playoff", 0):
                return "playoff"
            gc = game_count[team][season]  # juegos ANTES de este partido
            s_min, s_max = season_bounds.get(season, (date, date))
            total_days = (s_max - s_min).days
            elapsed = (date - s_min).days
            pct = elapsed / total_days if total_days > 0 else 0.0
            if gc < EARLY_GAMES:
                return "early"
            elif pct >= (1 - LATE_GAMES / 162):  # aprox últimas 30 de 162
                return "late"
            else:
                return "mid"

        # Usar contexto del home team como referencia del partido
        ctx = get_context(home)

        # ------------------------------------------------------------------ #
        # Guardar fila
        # ------------------------------------------------------------------ #
        rows_out.append({
            "pitcher_rest_days_home": pitcher_rest_home,
            "pitcher_rest_days_away": pitcher_rest_away,
            "bullpen_era_7d_home": era_home,
            "bullpen_era_7d_away": era_away,
            "team_ops_7d_home": ops_home,
            "team_ops_7d_away": ops_away,
            "momentum_home": mom_home,
            "momentum_away": mom_away,
            "is_back_to_back_home": b2b_home,
            "is_back_to_back_away": b2b_away,
            "season_pct_home": spct_home,
            "season_pct_away": spct_away,
            "context": ctx,
        })

        # ------------------------------------------------------------------ #
        # Actualizar estado (DESPUÉS de registrar features → sin leakage)
        # ------------------------------------------------------------------ #
        last_date[home] = date
        last_date[away] = date

        scores_for[home].append((date, h_score))
        scores_for[away].append((date, a_score))
        scores_against[home].append((date, a_score))
        scores_against[away].append((date, h_score))

        home_win = h_score > a_score
        results_dq[home].append(1 if home_win else -1)
        results_dq[away].append(-1 if home_win else 1)

        game_count[home][season] += 1
        game_count[away][season] += 1

    feat_df = pd.DataFrame(rows_out, index=df.index)
    return pd.concat([df, feat_df], axis=1)


# ---------------------------------------------------------------------------
# Función para inferencia de partido específico
# ---------------------------------------------------------------------------

def get_game_features(
    home: str,
    away: str,
    date: str,
    df_hist: pd.DataFrame,
) -> dict:
    """
    Devuelve un dict con los features avanzados para un partido específico,
    calculados a partir del historial df_hist (que debe estar en el mismo
    formato que el CSV de entrenamiento: home, away, home_score, away_score, date).

    Solo se usan partidos anteriores a `date` para evitar leakage.
    """
    target_date = pd.to_datetime(date)
    df_hist = _ensure_datetime(df_hist)

    # Filtrar historial previo al partido
    df_prev = df_hist[df_hist["date"] < target_date].copy()

    if df_prev.empty:
        return _neutral_features()

    # Construir el DataFrame con el partido ficticio al final y ejecutar enrich
    fake_row = pd.DataFrame([{
        "home": home,
        "away": away,
        "home_score": 0,
        "away_score": 0,
        "date": target_date,
        "season": df_hist["season"].iloc[-1] if "season" in df_hist.columns else target_date.year,
    }])

    df_combined = pd.concat([df_prev, fake_row], ignore_index=True)
    df_enriched = enrich_mlb_training(df_combined)

    last_row = df_enriched.iloc[-1]
    feature_cols = [
        "pitcher_rest_days_home", "pitcher_rest_days_away",
        "bullpen_era_7d_home", "bullpen_era_7d_away",
        "team_ops_7d_home", "team_ops_7d_away",
        "momentum_home", "momentum_away",
        "is_back_to_back_home", "is_back_to_back_away",
        "season_pct_home", "season_pct_away",
        "context",
    ]
    return {col: last_row[col] for col in feature_cols}


def _neutral_features() -> dict:
    """Valores neutros cuando no hay historial disponible."""
    return {
        "pitcher_rest_days_home": np.nan,
        "pitcher_rest_days_away": np.nan,
        "bullpen_era_7d_home": np.nan,
        "bullpen_era_7d_away": np.nan,
        "team_ops_7d_home": np.nan,
        "team_ops_7d_away": np.nan,
        "momentum_home": 0.0,
        "momentum_away": 0.0,
        "is_back_to_back_home": 0,
        "is_back_to_back_away": 0,
        "season_pct_home": 0.0,
        "season_pct_away": 0.0,
        "context": "early",
    }


# ---------------------------------------------------------------------------
# __main__: demo con MLB_train.csv
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    cache_path = os.path.join(os.path.dirname(__file__), "_cache", "MLB_train.csv")
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"No se encontró {cache_path}")

    df_raw = pd.read_csv(cache_path)
    print(f"Partidos cargados: {len(df_raw)}")
    print(f"Columnas originales: {list(df_raw.columns)}\n")

    df_enriched = enrich_mlb_training(df_raw)

    new_cols = [
        "pitcher_rest_days_home", "pitcher_rest_days_away",
        "bullpen_era_7d_home", "bullpen_era_7d_away",
        "team_ops_7d_home", "team_ops_7d_away",
        "momentum_home", "momentum_away",
        "is_back_to_back_home", "is_back_to_back_away",
        "season_pct_home", "season_pct_away",
        "context",
    ]

    display_cols = ["date", "home", "away", "home_score", "away_score"] + new_cols
    print("=== Primeras 10 filas enriquecidas ===")
    print(df_enriched[display_cols].head(10).to_string(index=False))

    print("\n=== Stats de los nuevos features ===")
    print(df_enriched[new_cols[:-1]].describe().round(3))

    print("\n=== Distribución de context ===")
    print(df_enriched["context"].value_counts())

    # Demo de get_game_features
    sample = df_raw.iloc[100]
    feats = get_game_features(
        home=sample["home"],
        away=sample["away"],
        date=sample["date"],
        df_hist=df_raw,
    )
    print(f"\n=== get_game_features para {sample['home']} vs {sample['away']} ({sample['date']}) ===")
    for k, v in feats.items():
        print(f"  {k}: {v}")
