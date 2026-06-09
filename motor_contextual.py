"""
motor_contextual.py — ContextualEngine: enruta predicciones a sub-modelos
especializados según el contexto del partido.

Contextos reconocidos:
  playoff      — is_playoff=True en los datos
  early_season — primeros 20% de partidos de cada equipo en la temporada
  late_season  — últimos 20% de partidos de cada equipo en la temporada
  back_to_back — algún equipo jugó el día anterior
  regular      — resto de partidos

Cada contexto con ≥100 partidos obtiene su propio SportsEngine. Los demás
comparten el motor default entrenado sobre todos los datos.

Funciones adicionales:
  blend_predictions(preds, weights) → dict promediado ponderado
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Optional

from motor_deportes import SportsEngine

warnings.filterwarnings("ignore")

# Contextos en orden de prioridad (el primero que coincide gana)
CONTEXT_PRIORITY = ["playoff", "back_to_back", "early_season", "late_season", "regular"]
MIN_GAMES_SUBMODEL = 100  # mínimo de partidos para entrenar un sub-modelo propio


# ---------------------------------------------------------------------------
# Utilidades de detección de contexto
# ---------------------------------------------------------------------------

def _season_from_date(date: pd.Timestamp, sport: str = "generic") -> int:
    """
    Heurística simple: para la NBA/NHL la temporada cambia en octubre.
    Para MLB en abril. Resto: año calendario.
    """
    sport = sport.lower()
    if sport in ("nba", "nhl"):
        return date.year if date.month >= 10 else date.year - 1
    if sport == "mlb":
        return date.year if date.month >= 4 else date.year - 1
    return date.year


def _label_contexts(df: pd.DataFrame, sport: str = "generic") -> pd.Series:
    """
    Asigna un contexto a cada fila de df.
    df debe tener: home, away, date  [+ is_playoff opcional].
    Devuelve una pd.Series con strings de contexto.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    has_playoff = "is_playoff" in df.columns

    # ── Paso 1: contar partidos por equipo en cada temporada ──────────────
    # Construir índice de aparición: (team, season) → lista de índices de fila
    team_season_rows: dict = defaultdict(list)
    for idx, row in df.iterrows():
        season_h = _season_from_date(pd.Timestamp(row["date"]), sport)
        season_a = season_h  # mismo partido → misma fecha → misma temporada
        team_season_rows[(row["home"], season_h)].append(idx)
        team_season_rows[(row["away"], season_a)].append(idx)

    # ── Paso 2: marcar early/late por equipo ─────────────────────────────
    # Para cada (team, season) los primeros 20% → early, últimos 20% → late
    early_set: set = set()
    late_set: set = set()
    for (team, season), rows in team_season_rows.items():
        n = len(rows)
        if n < 5:
            continue
        cutoff_early = max(1, int(np.ceil(n * 0.20)))
        cutoff_late  = max(1, int(np.ceil(n * 0.20)))
        for r in rows[:cutoff_early]:
            early_set.add(r)
        for r in rows[-cutoff_late:]:
            late_set.add(r)

    # ── Paso 3: detectar back-to-back ────────────────────────────────────
    last_date: dict = {}
    b2b_set: set = set()
    for idx, row in df.iterrows():
        gd = pd.Timestamp(row["date"])
        for team in (row["home"], row["away"]):
            prev = last_date.get(team)
            if prev is not None and (gd - prev).days == 1:
                b2b_set.add(idx)
        # actualizar last_date después de revisar
        last_date[row["home"]] = gd
        last_date[row["away"]] = gd

    # ── Paso 4: asignar contexto en orden de prioridad ───────────────────
    contexts = []
    for idx, row in df.iterrows():
        is_po = bool(row.get("is_playoff", False)) if has_playoff else False
        if is_po:
            ctx = "playoff"
        elif idx in b2b_set:
            ctx = "back_to_back"
        elif idx in early_set:
            ctx = "early_season"
        elif idx in late_set:
            ctx = "late_season"
        else:
            ctx = "regular"
        contexts.append(ctx)

    return pd.Series(contexts, index=df.index, name="context")


# ---------------------------------------------------------------------------
# blend_predictions
# ---------------------------------------------------------------------------

def blend_predictions(preds: list[dict], weights: list[float]) -> dict:
    """
    Promedia predicciones de múltiples motores ponderadas.

    preds   — lista de dicts devueltos por ContextualEngine.predict() o
              SportsEngine.predict()
    weights — lista de pesos (no necesitan sumar 1; se normalizan)

    Devuelve un dict con las probabilidades promediadas. Los campos no
    numéricos (home, away, value_bets, engine_used) se toman del primer pred.
    """
    if not preds:
        raise ValueError("preds no puede estar vacía")
    if len(preds) != len(weights):
        raise ValueError("preds y weights deben tener la misma longitud")

    w = np.array(weights, dtype=float)
    w = w / w.sum()

    base = preds[0].copy()

    numeric_keys = [
        "p_home", "p_away",
        "fair_odds_home", "fair_odds_away",
        "blended_p_home", "blended_p_away",
        "novig_p_home", "novig_p_away",
    ]

    for key in numeric_keys:
        vals = [p.get(key) for p in preds]
        if any(v is None for v in vals):
            continue
        blended = float(np.dot(w, vals))
        base[key] = round(blended, 4)

    # Recalcular fair_odds desde p_home/p_away combinadas
    if "p_home" in base and base["p_home"] > 0:
        base["fair_odds_home"] = round(1.0 / base["p_home"], 3)
    if "p_away" in base and base["p_away"] > 0:
        base["fair_odds_away"] = round(1.0 / base["p_away"], 3)

    # Marcar como blend
    base["engine_used"] = "blend"
    base["blend_weights"] = [round(float(wi), 4) for wi in w]
    base["value_bets"] = []  # conservador: no propagar value_bets del blend sin recalcular

    return base


# ---------------------------------------------------------------------------
# ContextualEngine
# ---------------------------------------------------------------------------

class ContextualEngine:
    """
    Motor de predicción que delega a sub-modelos especializados por contexto.

    Interfaz compatible con SportsEngine:
      fit(df)
      predict(home, away, context=None, **kwargs)
      expected_scores(home, away, **kwargs)

    Parámetros extra:
      min_games    — mínimo de partidos para crear sub-modelo (default 100)
    """

    def __init__(self, sport: str = "generic", min_games: int = MIN_GAMES_SUBMODEL, **kwargs):
        self.sport = sport
        self.min_games = min_games
        self._engine_kwargs = kwargs

        # Sub-modelos por contexto; se populan en fit()
        self._engines: dict[str, SportsEngine] = {}
        # Motor default: entrenado sobre todos los datos
        self._default = SportsEngine(sport, **kwargs)

        self._trained = False
        self._trained_df: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # fit
    # ------------------------------------------------------------------
    def fit(self, df: pd.DataFrame) -> "ContextualEngine":
        """
        Detecta el contexto de cada fila y entrena sub-modelos por contexto.
        Requiere mínimo `min_games` partidos por contexto para crear sub-modelo;
        si hay menos, ese contexto usará el motor default.
        """
        df = df.sort_values("date").reset_index(drop=True)
        self._trained_df = df.copy()

        # 1. Entrenar motor default con todos los datos
        print(f"\n[ContextualEngine:{self.sport}] Entrenando motor default...")
        self._default.fit(df)

        # 2. Etiquetar contextos
        ctx_labels = _label_contexts(df, sport=self.sport)
        df_ctx = df.copy()
        df_ctx["_context"] = ctx_labels

        # 3. Entrenar sub-modelos donde haya suficientes datos
        ctx_counts = ctx_labels.value_counts()
        print(f"\n[ContextualEngine:{self.sport}] Distribución de contextos:")
        for ctx in CONTEXT_PRIORITY:
            n = ctx_counts.get(ctx, 0)
            print(f"  {ctx:15s}: {n:5d} partidos", end="")
            if n >= self.min_games:
                sub_df = df_ctx[df_ctx["_context"] == ctx].drop(columns=["_context"])
                sub_engine = SportsEngine(self.sport, **self._engine_kwargs)
                try:
                    sub_engine.fit(sub_df)
                    self._engines[ctx] = sub_engine
                    print(f"  → sub-modelo entrenado")
                except Exception as e:
                    print(f"  → error al entrenar ({e}), usará default")
            else:
                print(f"  → insuficiente (mín {self.min_games}), usará default")

        self._trained = True
        # Exponer _teams_seen y _sport del motor default para compatibilidad
        self._teams_seen = self._default._teams_seen
        self._sport = self._default._sport
        print(f"\n[ContextualEngine:{self.sport}] Listo. "
              f"Sub-modelos: {list(self._engines.keys()) or ['ninguno (todo al default)']}")
        return self

    # ------------------------------------------------------------------
    # detect_context
    # ------------------------------------------------------------------
    def detect_context(self, home: str, away: str,
                       date: pd.Timestamp,
                       df_hist: Optional[pd.DataFrame] = None) -> str:
        """
        Detecta automáticamente el contexto dado fecha y (opcionalmente) historial.

        Si no se proporciona df_hist se usa el dataframe de entrenamiento.
        Devuelve string del contexto.
        """
        date = pd.Timestamp(date)
        ref_df = df_hist if df_hist is not None else self._trained_df

        # ── Back-to-back: alguno de los dos equipos jugó ayer ─────────────
        if ref_df is not None and len(ref_df) > 0:
            yesterday = date - pd.Timedelta(days=1)
            prev = ref_df[ref_df["date"].astype(str) == str(yesterday.date())]
            teams_yesterday = set(prev["home"].tolist() + prev["away"].tolist())
            if home in teams_yesterday or away in teams_yesterday:
                return "back_to_back"

        # ── Early/late season: contar partidos del equipo en la temporada ──
        season = _season_from_date(date, self.sport)
        if ref_df is not None and len(ref_df) > 0:
            ref_df_copy = ref_df.copy()
            ref_df_copy["_date"] = pd.to_datetime(ref_df_copy["date"])
            ref_df_copy["_season"] = ref_df_copy["_date"].apply(
                lambda d: _season_from_date(d, self.sport))

            for team in (home, away):
                team_games = ref_df_copy[
                    (ref_df_copy["_season"] == season) &
                    ((ref_df_copy["home"] == team) | (ref_df_copy["away"] == team))
                ]
                n_season = len(team_games)
                if n_season < 5:
                    continue
                # Partidos de este equipo en la temporada hasta hoy
                past_games = team_games[team_games["_date"] < date]
                n_past = len(past_games)
                cutoff = max(1, int(np.ceil(n_season * 0.20)))
                if n_past <= cutoff:
                    return "early_season"
                if n_past >= n_season - cutoff:
                    return "late_season"

        return "regular"

    # ------------------------------------------------------------------
    # predict
    # ------------------------------------------------------------------
    def predict(self, home: str, away: str,
                context: Optional[str] = None,
                market_odds: dict = None,
                game_date: pd.Timestamp = None,
                is_playoff: bool = False,
                auto_detect: bool = False,
                **kwargs) -> dict:
        """
        Predice el resultado home vs away.

        context     — contexto explícito ("playoff", "back_to_back", etc.).
                      Si es None y auto_detect=True, se detecta automáticamente.
                      Si no se especifica, usa el motor default.
        auto_detect — si True, llama detect_context() cuando context es None.
        market_odds — {"home": float, "away": float} cuotas decimales.
        game_date   — fecha del partido para rest days y detección.
        is_playoff  — fuerza contexto playoff a nivel de feature del modelo.

        Devuelve dict compatible con SportsEngine.predict() + metadato
        "engine_used" con el nombre del contexto utilizado.
        """
        if not self._trained:
            raise RuntimeError("Modelo no entrenado. Llama fit() primero.")

        # Resolver contexto
        resolved_ctx = context
        if resolved_ctx is None and auto_detect and game_date is not None:
            resolved_ctx = self.detect_context(home, away, date=game_date)

        # Seleccionar motor
        if resolved_ctx is not None and resolved_ctx in self._engines:
            engine = self._engines[resolved_ctx]
            engine_label = resolved_ctx
        else:
            engine = self._default
            engine_label = "default" if resolved_ctx is None else f"default(fallback:{resolved_ctx})"

        # Llamar al sub-motor
        pred = engine.predict(
            home, away,
            market_odds=market_odds,
            game_date=game_date,
            is_playoff=(is_playoff or resolved_ctx == "playoff"),
            **kwargs,
        )
        pred["engine_used"] = engine_label
        pred["context_requested"] = resolved_ctx
        return pred

    # ------------------------------------------------------------------
    # expected_scores
    # ------------------------------------------------------------------
    def expected_scores(self, home: str, away: str,
                        context: Optional[str] = None,
                        **kwargs):
        """
        Delegamos a sub-motor si existe, si no al default.
        Retorna (mu_home, mu_away).
        """
        if not self._trained:
            raise RuntimeError("Modelo no entrenado. Llama fit() primero.")

        engine = self._engines.get(context, self._default) if context else self._default
        return engine.expected_scores(home, away, **kwargs)

    # ------------------------------------------------------------------
    # walk_forward_validate (delegado al default)
    # ------------------------------------------------------------------
    def walk_forward_validate(self, df: pd.DataFrame, min_train: int = 200) -> dict:
        """Valida el motor default con walk-forward."""
        return self._default.walk_forward_validate(df, min_train=min_train)

    # ------------------------------------------------------------------
    # Representación
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        trained = "entrenado" if self._trained else "sin entrenar"
        engines = list(self._engines.keys()) or ["ninguno"]
        return (f"ContextualEngine(sport={self.sport!r}, {trained}, "
                f"sub-modelos={engines})")


# ---------------------------------------------------------------------------
# __main__: comparar ContextualEngine vs SportsEngine en datos NBA
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from sklearn.metrics import brier_score_loss, log_loss

    CACHE = os.path.join(os.path.dirname(__file__), "_cache", "NBA_train.csv")
    print("=" * 65)
    print("  Demo ContextualEngine vs SportsEngine — NBA")
    print("=" * 65)

    # ── Cargar datos ──────────────────────────────────────────────────
    df = pd.read_csv(CACHE)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    print(f"\nDataset: {len(df)} partidos  "
          f"({df['date'].min().date()} → {df['date'].max().date()})")

    # ── Split temporal 80/20 ──────────────────────────────────────────
    split_idx = int(len(df) * 0.80)
    df_train = df.iloc[:split_idx].reset_index(drop=True)
    df_val   = df.iloc[split_idx:].reset_index(drop=True)
    print(f"Train: {len(df_train)} | Val: {len(df_val)}\n")

    # ── Entrenar motores ──────────────────────────────────────────────
    print("─" * 65)
    simple_engine = SportsEngine(sport="nba")
    simple_engine.fit(df_train)

    print("\n" + "─" * 65)
    ctx_engine = ContextualEngine(sport="nba", min_games=80)
    ctx_engine.fit(df_train)

    # ── Evaluar en validación ─────────────────────────────────────────
    print("\n" + "─" * 65)
    print("Evaluando en set de validación...")

    results_simple = []
    results_ctx    = []
    true_labels    = []

    for _, row in df_val.iterrows():
        home, away = row["home"], row["away"]
        actual_home_win = int(row["home_score"] > row["away_score"])
        true_labels.append(actual_home_win)

        # Motor simple
        try:
            pred_s = simple_engine.predict(home, away, game_date=row["date"])
            results_simple.append(pred_s["p_home"])
        except Exception:
            results_simple.append(0.5)

        # Motor contextual (auto-detect)
        try:
            pred_c = ctx_engine.predict(
                home, away,
                game_date=row["date"],
                auto_detect=True,
            )
            results_ctx.append(pred_c["p_home"])
        except Exception:
            results_ctx.append(0.5)

    y_true = np.array(true_labels)
    p_simple = np.array(results_simple)
    p_ctx    = np.array(results_ctx)

    # Métricas
    acc_simple = float(np.mean((p_simple > 0.5).astype(int) == y_true))
    acc_ctx    = float(np.mean((p_ctx    > 0.5).astype(int) == y_true))
    brier_simple = brier_score_loss(y_true, p_simple)
    brier_ctx    = brier_score_loss(y_true, p_ctx)
    ll_simple = log_loss(y_true, np.column_stack([1 - p_simple, p_simple]))
    ll_ctx    = log_loss(y_true, np.column_stack([1 - p_ctx,    p_ctx]))

    print(f"\n{'Motor':<22} {'Accuracy':>10} {'Brier':>10} {'LogLoss':>10}")
    print("-" * 55)
    print(f"{'SportsEngine (simple)':<22} {acc_simple:>10.4f} {brier_simple:>10.4f} {ll_simple:>10.4f}")
    print(f"{'ContextualEngine':<22} {acc_ctx:>10.4f} {brier_ctx:>10.4f} {ll_ctx:>10.4f}")

    delta_acc   = acc_ctx    - acc_simple
    delta_brier = brier_ctx  - brier_simple
    delta_ll    = ll_ctx     - ll_simple
    print(f"{'Delta (ctx - simple)':<22} {delta_acc:>+10.4f} {delta_brier:>+10.4f} {delta_ll:>+10.4f}")
    print()

    # ── Demo de blend_predictions ─────────────────────────────────────
    print("─" * 65)
    print("Demo blend_predictions:")
    sample = df_val.iloc[0]
    home_ex, away_ex = sample["home"], sample["away"]
    pred_a = simple_engine.predict(home_ex, away_ex)
    pred_b = ctx_engine.predict(home_ex, away_ex, auto_detect=True,
                                game_date=sample["date"])
    blended = blend_predictions([pred_a, pred_b], weights=[0.4, 0.6])
    print(f"  Partido: {home_ex} vs {away_ex}")
    print(f"  SportsEngine    p_home={pred_a['p_home']:.4f}  p_away={pred_a['p_away']:.4f}")
    print(f"  ContextualEngine p_home={pred_b['p_home']:.4f}  p_away={pred_b['p_away']:.4f}"
          f"  [motor={pred_b['engine_used']}]")
    print(f"  Blend (0.4/0.6)  p_home={blended['p_home']:.4f}  p_away={blended['p_away']:.4f}")

    # ── Sub-motores disponibles ───────────────────────────────────────
    print("\n" + "─" * 65)
    print("Sub-modelos entrenados por contexto:")
    for ctx in CONTEXT_PRIORITY:
        status = "PROPIO" if ctx in ctx_engine._engines else "default"
        print(f"  {ctx:15s}: {status}")

    print("\nFin del demo.")
