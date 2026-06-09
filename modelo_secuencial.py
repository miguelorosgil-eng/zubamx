"""
Modelo de secuencias temporales para capturar momentum y tendencias de equipos.

Complementa al SportsEngine (motor_deportes.py) sin reemplazarlo.
No requiere PyTorch/TensorFlow: usa numpy puro.

Captura patrones que el modelo estático (XGBoost+LR) no ve:
- Equipo que gana 3 seguidos tiene mayor P(ganar 4to) que uno que ganó 1 de 3
  aunque el win rate total sea igual.
- Forma reciente como local vs. visitante
- Head-to-head reciente entre los dos equipos específicos
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes por defecto
# ---------------------------------------------------------------------------
MAX_MOMENTUM = 0.10   # ±10% máximo ajuste de momentum
MAX_H2H_EDGE = 0.06   # ±6% máximo ajuste H2H
MAX_SPLIT_ADJ = 0.07  # ±7% máximo ajuste home/away split


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _weighted_winrate(results: list[int], decay: float) -> float:
    """
    Win rate ponderado con decay exponencial (más reciente = más peso).
    results: lista de 0/1 ordenados del más antiguo al más reciente.
    """
    if not results:
        return 0.5
    n = len(results)
    weights = np.array([decay ** (n - 1 - i) for i in range(n)])
    weights /= weights.sum()
    return float(np.dot(weights, results))


def _current_streak(results: list[int]) -> int:
    """
    Racha actual: +k si los últimos k resultados son victorias, -k si derrotas.
    results: lista de 0/1, el último es el más reciente.
    """
    if not results:
        return 0
    last = results[-1]
    streak = 0
    for r in reversed(results):
        if r == last:
            streak += 1
        else:
            break
    return streak if last == 1 else -streak


def _momentum_to_adjustment(wrate: float, decay: float = 0.85) -> float:
    """
    Convierte win rate ponderado a ajuste de probabilidad.
    Centrado en 0.5: valores > 0.5 dan ajuste positivo, < 0.5 negativo.
    Escala: ±MAX_MOMENTUM cuando wrate está en los extremos (0 o 1).
    """
    raw = (wrate - 0.5) * 2  # [-1, 1]
    return float(np.clip(raw * MAX_MOMENTUM, -MAX_MOMENTUM, MAX_MOMENTUM))


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------

class SequenceModel:
    """
    Modelo de secuencia basado en patrones de los últimos N partidos.
    Usa una combinación de:
    - Weighted recent form (decay exponencial sobre últimos `window` partidos)
    - Streak detector (rachas actuales)
    - Head-to-head reciente (últimos 5 H2H)
    - Home/away splits recientes (últimos 15 como local/visitante)

    No requiere entrenamiento supervisado: es un modelo descriptivo/estadístico
    sobre el historial de resultados.
    """

    def __init__(self, window: int = 10, decay: float = 0.85):
        self.window = window
        self.decay = decay
        # team -> lista de dicts: {date, opponent, result(0/1), is_home, home_score, away_score}
        self._history: dict[str, list[dict]] = defaultdict(list)
        # (team_a, team_b) -> lista de dicts con resultados desde perspectiva de team_a
        self._h2h: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self._fitted = False

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> "SequenceModel":
        """
        Construye el historial por equipo a partir del DataFrame de partidos.

        df debe tener columnas: home, away, home_score, away_score, date
        Opcionalmente: game_id, season
        """
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        self._history = defaultdict(list)
        self._h2h = defaultdict(list)

        for _, row in df.iterrows():
            h = row["home"]
            a = row["away"]
            hs = row["home_score"]
            as_ = row["away_score"]
            date = row["date"]

            home_win = int(hs > as_)
            away_win = int(as_ > hs)

            # Historial del equipo local
            self._history[h].append({
                "date": date,
                "opponent": a,
                "result": home_win,
                "is_home": True,
                "home_score": hs,
                "away_score": as_,
            })
            # Historial del equipo visitante
            self._history[a].append({
                "date": date,
                "opponent": h,
                "result": away_win,
                "is_home": False,
                "home_score": hs,
                "away_score": as_,
            })

            # H2H: guardamos desde perspectiva del home (h vs a)
            self._h2h[(h, a)].append({
                "date": date,
                "home_win": home_win,
            })
            # También orden invertido para búsquedas
            self._h2h[(a, h)].append({
                "date": date,
                "home_win": away_win,  # desde perspectiva de 'a' como referencia
            })

        self._fitted = True
        return self

    # ------------------------------------------------------------------
    # get_team_form
    # ------------------------------------------------------------------

    def get_team_form(
        self,
        team: str,
        last_n: int = 5,
        as_home: Optional[bool] = None,
        before_date: Optional[pd.Timestamp] = None,
    ) -> dict:
        """
        Forma reciente de un equipo.

        Parameters
        ----------
        team     : nombre del equipo
        last_n   : cuántos partidos considerar
        as_home  : True=solo local, False=solo visitante, None=todos
        before_date : solo partidos anteriores a esta fecha (para evitar leakage)

        Returns
        -------
        dict con:
            games_found : int
            win_rate    : float (simple)
            weighted_wr : float (decay exponencial)
            streak      : int  (+k victorias, -k derrotas consecutivas)
            avg_score_diff : float  (promedio diferencial de puntos/carreras)
            last_results : list[int]  (más antiguo primero, 0/1)
        """
        if not self._fitted:
            warnings.warn("SequenceModel.fit() no ha sido llamado aún.")
            return self._empty_form()

        history = self._history.get(team, [])
        if before_date is not None:
            history = [g for g in history if g["date"] < before_date]
        if as_home is not None:
            history = [g for g in history if g["is_home"] == as_home]

        history = history[-last_n:]  # los más recientes

        if not history:
            return self._empty_form()

        results = [g["result"] for g in history]
        score_diffs = []
        for g in history:
            diff = g["home_score"] - g["away_score"]
            if not g["is_home"]:
                diff = -diff
            score_diffs.append(diff)

        return {
            "games_found": len(results),
            "win_rate": float(np.mean(results)),
            "weighted_wr": _weighted_winrate(results, self.decay),
            "streak": _current_streak(results),
            "avg_score_diff": float(np.mean(score_diffs)) if score_diffs else 0.0,
            "last_results": results,
        }

    @staticmethod
    def _empty_form() -> dict:
        return {
            "games_found": 0,
            "win_rate": 0.5,
            "weighted_wr": 0.5,
            "streak": 0,
            "avg_score_diff": 0.0,
            "last_results": [],
        }

    # ------------------------------------------------------------------
    # predict_adjustment
    # ------------------------------------------------------------------

    def predict_adjustment(
        self,
        home: str,
        away: str,
        date: Optional[pd.Timestamp] = None,
    ) -> dict:
        """
        Devuelve el ajuste secuencial a aplicar sobre la predicción base del SportsEngine.

        Returns
        -------
        dict:
            home_momentum     : float (-0.10 a +0.10)  ajuste de probabilidad por momentum
            away_momentum     : float
            home_streak       : int   (+5 = 5 victorias seguidas)
            away_streak       : int
            h2h_edge          : float  edge H2H reciente (desde perspectiva home)
            home_home_form    : float  forma reciente como local (0-1)
            away_away_form    : float  forma reciente como visitante (0-1)
            confidence_boost  : float  cuánto aumenta la confianza con este contexto
            warnings          : list[str]
        """
        if not self._fitted:
            warnings.warn("SequenceModel.fit() no ha sido llamado aún.")
            return self._null_adjustment()

        before = date
        warns: list[str] = []

        # --- Forma general reciente (últimos `window` partidos) ---
        home_form = self.get_team_form(home, last_n=self.window, before_date=before)
        away_form = self.get_team_form(away, last_n=self.window, before_date=before)

        if home_form["games_found"] < 3:
            warns.append(f"Pocos datos para {home} ({home_form['games_found']} partidos)")
        if away_form["games_found"] < 3:
            warns.append(f"Pocos datos para {away} ({away_form['games_found']} partidos)")

        home_momentum = _momentum_to_adjustment(home_form["weighted_wr"], self.decay)
        away_momentum = _momentum_to_adjustment(away_form["weighted_wr"], self.decay)

        # --- Home/away splits (últimos 15) ---
        home_home_form = self.get_team_form(home, last_n=15, as_home=True, before_date=before)
        away_away_form = self.get_team_form(away, last_n=15, as_home=False, before_date=before)

        hhf = home_home_form["weighted_wr"]  # 0-1
        aaf = away_away_form["weighted_wr"]  # 0-1

        # Ajuste adicional por splits: si el local es muy bueno en casa
        home_split_adj = float(np.clip((hhf - 0.5) * MAX_SPLIT_ADJ * 2, -MAX_SPLIT_ADJ, MAX_SPLIT_ADJ))
        away_split_adj = float(np.clip((aaf - 0.5) * MAX_SPLIT_ADJ * 2, -MAX_SPLIT_ADJ, MAX_SPLIT_ADJ))

        # --- H2H reciente (últimos 5) ---
        h2h_key = (home, away)
        h2h_records = self._h2h.get(h2h_key, [])
        if before is not None:
            h2h_records = [r for r in h2h_records if r["date"] < before]
        h2h_records = h2h_records[-5:]

        h2h_edge = 0.0
        if h2h_records:
            h2h_wins = [r["home_win"] for r in h2h_records]
            h2h_wr = _weighted_winrate(h2h_wins, self.decay)
            h2h_edge = float(np.clip((h2h_wr - 0.5) * MAX_H2H_EDGE * 2, -MAX_H2H_EDGE, MAX_H2H_EDGE))
        else:
            warns.append(f"Sin datos H2H para {home} vs {away}")

        # --- Streaks ---
        home_streak = home_form["streak"]
        away_streak = away_form["streak"]

        # Streak boost adicional: racha larga amplifica momentum
        # Racha de ≥4 victorias seguidas: +1% extra; ≥6: +2%
        def _streak_bonus(streak: int) -> float:
            abs_s = abs(streak)
            sign = 1 if streak > 0 else -1
            if abs_s >= 6:
                return sign * 0.02
            elif abs_s >= 4:
                return sign * 0.01
            return 0.0

        home_momentum += _streak_bonus(home_streak)
        away_momentum += _streak_bonus(away_streak)

        # Clamp final
        home_momentum = float(np.clip(home_momentum + home_split_adj, -MAX_MOMENTUM, MAX_MOMENTUM))
        away_momentum = float(np.clip(away_momentum + away_split_adj, -MAX_MOMENTUM, MAX_MOMENTUM))

        # --- Confidence boost ---
        # Cuánto contexto útil tenemos: más datos + streaks claros = más confianza
        data_quality = min(1.0, (home_form["games_found"] + away_form["games_found"]) / (2 * self.window))
        streak_signal = (abs(home_streak) + abs(away_streak)) / 12  # normalizado
        h2h_signal = (len(h2h_records) / 5) * 0.5
        confidence_boost = float(np.clip(data_quality * 0.4 + streak_signal * 0.4 + h2h_signal * 0.2, 0.0, 1.0))

        return {
            "home_momentum": round(home_momentum, 4),
            "away_momentum": round(away_momentum, 4),
            "home_streak": home_streak,
            "away_streak": away_streak,
            "h2h_edge": round(h2h_edge, 4),
            "home_home_form": round(hhf, 4),
            "away_away_form": round(aaf, 4),
            "confidence_boost": round(confidence_boost, 4),
            "warnings": warns,
        }

    @staticmethod
    def _null_adjustment() -> dict:
        return {
            "home_momentum": 0.0,
            "away_momentum": 0.0,
            "home_streak": 0,
            "away_streak": 0,
            "h2h_edge": 0.0,
            "home_home_form": 0.5,
            "away_away_form": 0.5,
            "confidence_boost": 0.0,
            "warnings": ["Modelo no entrenado"],
        }

    # ------------------------------------------------------------------
    # Utilidades públicas
    # ------------------------------------------------------------------

    def top_teams_by_form(self, last_n: int = 10, min_games: int = 5) -> list[dict]:
        """
        Devuelve lista de equipos ordenados por forma reciente ponderada (mejor primero).
        Útil para el bloque __main__.
        """
        if not self._fitted:
            return []
        results = []
        for team in self._history:
            form = self.get_team_form(team, last_n=last_n)
            if form["games_found"] >= min_games:
                results.append({
                    "team": team,
                    "weighted_wr": form["weighted_wr"],
                    "win_rate": form["win_rate"],
                    "streak": form["streak"],
                    "games": form["games_found"],
                    "avg_score_diff": form["avg_score_diff"],
                })
        results.sort(key=lambda x: x["weighted_wr"], reverse=True)
        return results


# ---------------------------------------------------------------------------
# apply_sequence_adjustment
# ---------------------------------------------------------------------------

def apply_sequence_adjustment(base_pred: dict, seq_adj: dict) -> dict:
    """
    Combina la predicción base del SportsEngine con el ajuste secuencial.

    Parameters
    ----------
    base_pred : dict retornado por SportsEngine.predict()
        Debe contener: 'p_home', 'p_away', 'confidence' (y cualquier otra clave)
    seq_adj   : dict retornado por SequenceModel.predict_adjustment()

    Returns
    -------
    dict con todas las claves originales de base_pred más:
        'p_home_adj'       : probabilidad home ajustada y renormalizada
        'p_away_adj'       : probabilidad away ajustada y renormalizada
        'confidence_adj'   : confianza ajustada
        'seq_home_momentum': float
        'seq_away_momentum': float
        'seq_home_streak'  : int
        'seq_away_streak'  : int
        'seq_h2h_edge'     : float
        'seq_warnings'     : list[str]
        'seq_applied'      : bool  (siempre True cuando se aplica)
    """
    result = dict(base_pred)

    p_home = float(base_pred.get("p_home", 0.5))
    p_away = float(base_pred.get("p_away", 1 - p_home))
    confidence = float(base_pred.get("confidence", 0.5))

    home_adj = seq_adj.get("home_momentum", 0.0) + seq_adj.get("h2h_edge", 0.0) * 0.5
    away_adj = seq_adj.get("away_momentum", 0.0) - seq_adj.get("h2h_edge", 0.0) * 0.5

    p_home_new = max(0.01, min(0.99, p_home + home_adj))
    p_away_new = max(0.01, min(0.99, p_away + away_adj))

    # Renormalizar (no garantizamos que sumen exactamente 1 antes)
    total = p_home_new + p_away_new
    p_home_new /= total
    p_away_new /= total

    # Boost de confianza: la confianza base se incrementa hasta un 15% adicional
    confidence_boost = seq_adj.get("confidence_boost", 0.0)
    confidence_new = min(1.0, confidence + confidence_boost * 0.15)

    result.update({
        "p_home_adj": round(p_home_new, 4),
        "p_away_adj": round(p_away_new, 4),
        "confidence_adj": round(confidence_new, 4),
        "seq_home_momentum": seq_adj.get("home_momentum", 0.0),
        "seq_away_momentum": seq_adj.get("away_momentum", 0.0),
        "seq_home_streak": seq_adj.get("home_streak", 0),
        "seq_away_streak": seq_adj.get("away_streak", 0),
        "seq_h2h_edge": seq_adj.get("h2h_edge", 0.0),
        "seq_home_home_form": seq_adj.get("home_home_form", 0.5),
        "seq_away_away_form": seq_adj.get("away_away_form", 0.5),
        "seq_warnings": seq_adj.get("warnings", []),
        "seq_applied": True,
    })
    return result


# ---------------------------------------------------------------------------
# Demo / __main__
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    CACHE_DIR = os.path.join(os.path.dirname(__file__), "_cache")

    def _load_and_show(sport: str, csv_name: str, top_n: int = 5):
        path = os.path.join(CACHE_DIR, csv_name)
        if not os.path.exists(path):
            print(f"  [!] No encontrado: {path}")
            return

        df = pd.read_csv(path)
        df["date"] = pd.to_datetime(df["date"])

        model = SequenceModel(window=10, decay=0.85)
        model.fit(df)

        rankings = model.top_teams_by_form(last_n=10, min_games=5)

        print(f"\n{'='*60}")
        print(f"  TOP {top_n} equipos por FORMA RECIENTE — {sport}")
        print(f"{'='*60}")
        print(f"  {'#':<3} {'Equipo':<30} {'WR pond':>7}  {'WR simple':>9}  {'Racha':>6}  {'Diff/j':>7}")
        print(f"  {'-'*3} {'-'*30} {'-'*7}  {'-'*9}  {'-'*6}  {'-'*7}")
        for i, row in enumerate(rankings[:top_n], 1):
            streak_str = f"+{row['streak']}" if row["streak"] > 0 else str(row["streak"])
            print(
                f"  {i:<3} {row['team']:<30} "
                f"{row['weighted_wr']:>7.1%}  "
                f"{row['win_rate']:>9.1%}  "
                f"{streak_str:>6}  "
                f"{row['avg_score_diff']:>+7.2f}"
            )

        # Ejemplo de ajuste para el partido #1 vs #2
        if len(rankings) >= 2:
            t1 = rankings[0]["team"]
            t2 = rankings[1]["team"]
            adj = model.predict_adjustment(t1, t2)
            print(f"\n  Ejemplo de ajuste para {t1} (local) vs {t2} (visitante):")
            print(f"    home_momentum : {adj['home_momentum']:+.2%}")
            print(f"    away_momentum : {adj['away_momentum']:+.2%}")
            print(f"    h2h_edge      : {adj['h2h_edge']:+.2%}")
            print(f"    home_streak   : {adj['home_streak']:+d}")
            print(f"    away_streak   : {adj['away_streak']:+d}")
            print(f"    confidence_boost: {adj['confidence_boost']:.2f}")
            if adj["warnings"]:
                print(f"    warnings: {adj['warnings']}")

            # Simular apply_sequence_adjustment
            fake_base = {"p_home": 0.52, "p_away": 0.48, "confidence": 0.60}
            combined = apply_sequence_adjustment(fake_base, adj)
            print(f"\n  apply_sequence_adjustment(base p_home=52%, p_away=48%):")
            print(f"    p_home_adj    : {combined['p_home_adj']:.1%}")
            print(f"    p_away_adj    : {combined['p_away_adj']:.1%}")
            print(f"    confidence_adj: {combined['confidence_adj']:.2f}")

    print("\nModelo Secuencial — Demo")
    print("Usando datos del caché local\n")

    _load_and_show("MLB", "MLB_train.csv", top_n=5)
    _load_and_show("NBA", "NBA_train.csv", top_n=5)
