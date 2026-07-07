"""
Phase 3 — Predictor de movimiento de línea.

Predice si la línea de apertura se moverá en favor del pick antes del cierre
(señal de que el dinero sharp está de acuerdo con el modelo).

Features usadas:
  - Divergencia modelo vs línea apertura (p_model - p_implied_open)
  - Tamaño de la divergencia absoluta
  - Hora del día (apuestas por la mañana → más movimiento potencial)
  - Sport (MLB vs NBA vs NHL tienen patrones distintos)
  - Edge calculado
  - p_model range (favorito moderado vs débil)

Target:
  - 1 si la línea se movió ≥0.05 unidades decimales en favor del pick
  - 0 en caso contrario

Uso:
    from predictor_movimiento import LineMovementPredictor
    pred = LineMovementPredictor()
    pred.fit(history_df)      # DataFrame con columnas requeridas
    prob = pred.predict_proba(features_dict)  # P(movimiento favorable)
"""

import os
import json
import numpy as np
import warnings

warnings.filterwarnings("ignore")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
_MODEL_PATH = os.path.join(CACHE_DIR, "line_movement_model.json")

# Threshold para considerar "movimiento favorable"
MOVE_THRESHOLD = 0.05   # 0.05 odds decimales = ~2.5% en prob implícita

# Mínima probabilidad de movimiento para señal positiva
SIGNAL_THRESHOLD = 0.60


class LineMovementPredictor:
    """
    Clasificador binario: ¿la línea se moverá a tu favor antes del cierre?

    Usa XGBoost si disponible, LogisticRegression como fallback.
    Entrenado sobre historial de movimientos de línea del CLV tracker.
    """

    def __init__(self):
        self._model = None
        self._feature_names = [
            "div_model_market",   # p_model - p_implied_apertura
            "div_abs",            # |div_model_market|
            "edge",               # edge calculado (p_model - p_implied_vig)
            "p_model",            # probabilidad del modelo
            "p_implied_open",     # prob implícita apertura (sin vig)
            "sport_mlb",          # dummy MLB
            "sport_nba",          # dummy NBA
            "sport_nhl",          # dummy NHL
            "is_morning",         # apertura es ≤12h antes del partido
            "line_size",          # tamaño de la cuota (favorito=bajo, perro=alto)
        ]
        self._fitted = False
        self._n_train = 0
        self._load()

    # ── Feature extraction ──────────────────────────────────────────────────

    @staticmethod
    def extract_features(record: dict) -> np.ndarray | None:
        """
        record: {sport, p_model, odds_open, hours_to_game, edge}
        Retorna array de features o None si hay datos inválidos.
        """
        try:
            sport    = str(record.get("sport", "")).upper()
            p_model  = float(record.get("p_model", 0.5))
            odds_open = float(record.get("odds_open", 2.0))
            edge     = float(record.get("edge", 0.0))
            hours    = float(record.get("hours_to_game", 12))

            if odds_open <= 1.0 or not (0 < p_model < 1):
                return None

            # No-vig implied prob de apertura (market de 2 vías)
            odds_open_other = record.get("odds_open_other")
            if odds_open_other and float(odds_open_other) > 1:
                r1 = 1.0 / odds_open
                r2 = 1.0 / float(odds_open_other)
                p_implied_open = r1 / (r1 + r2)
            else:
                p_implied_open = 1.0 / odds_open

            div = p_model - p_implied_open
            div_abs = abs(div)
            line_size = odds_open  # favorito tiene odds bajas
            is_morning = 1 if hours >= 8 else 0

            return np.array([
                div,
                div_abs,
                edge,
                p_model,
                p_implied_open,
                1 if sport == "MLB" else 0,
                1 if sport == "NBA" else 0,
                1 if sport == "NHL" else 0,
                is_morning,
                line_size,
            ])
        except Exception:
            return None

    # ── Training ────────────────────────────────────────────────────────────

    def fit(self, history: list[dict]) -> "LineMovementPredictor":
        """
        history: lista de dicts con campos de apertura Y cierre.
        Cada elemento debe tener: sport, p_model, odds_open, odds_close,
                                   hours_to_game, edge, [odds_open_other]
        El target se calcula automáticamente: ¿la línea cerró mejor?
        """
        X_rows, y_rows = [], []

        for rec in history:
            feats = self.extract_features(rec)
            if feats is None:
                continue
            # Target: ¿la línea se movió favorablemente?
            odds_open  = float(rec.get("odds_open", 0))
            odds_close = float(rec.get("odds_close", 0))
            if odds_open <= 1 or odds_close <= 1:
                continue
            moved_fav = int(odds_close >= odds_open + MOVE_THRESHOLD)
            X_rows.append(feats)
            y_rows.append(moved_fav)

        if len(X_rows) < 50:
            print(f"  [LineMovPred] Datos insuficientes: {len(X_rows)} (<50). Sin entrenar.")
            return self

        X = np.array(X_rows)
        y = np.array(y_rows)
        self._n_train = len(y)

        try:
            import xgboost as xgb
            from sklearn.calibration import CalibratedClassifierCV
            base = xgb.XGBClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss", random_state=42,
                use_label_encoder=False,
            )
            self._model = CalibratedClassifierCV(base, cv=3, method="isotonic")
        except ImportError:
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.linear_model import LogisticRegression
            self._model = Pipeline([
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(C=1.0, max_iter=500)),
            ])

        self._model.fit(X, y)
        self._fitted = True

        pos_rate = float(y.mean())
        print(f"  [LineMovPred] Entrenado: {self._n_train} ejemplos, "
              f"tasa positiva={pos_rate:.1%}")
        self._save()
        return self

    def fit_from_clv_history(self) -> "LineMovementPredictor":
        """
        Intenta construir el dataset de entrenamiento desde el historial CLV
        y los datos de apertura/cierre de líneas guardados.
        """
        # Intentar cargar desde _cache/line_movement_training.json
        path = os.path.join(CACHE_DIR, "line_movement_training.json")
        if not os.path.exists(path):
            print(f"  [LineMovPred] Sin datos de entrenamiento en {path}")
            print("  Para generar: ejecuta analisis_dia.py varios días con --debug")
            return self
        with open(path) as f:
            history = json.load(f)
        return self.fit(history)

    # ── Inference ───────────────────────────────────────────────────────────

    def predict_proba(self, record: dict) -> float:
        """
        Retorna P(movimiento favorable) ∈ [0, 1].
        Si el modelo no está entrenado, devuelve 0.5 (neutral).
        """
        if not self._fitted or self._model is None:
            return 0.5
        feats = self.extract_features(record)
        if feats is None:
            return 0.5
        try:
            p = self._model.predict_proba(feats.reshape(1, -1))[0][1]
            return float(p)
        except Exception:
            return 0.5

    def has_favorable_signal(self, record: dict) -> tuple[bool, float]:
        """
        Retorna (señal_positiva, probabilidad).
        señal_positiva = True si P(movimiento) > SIGNAL_THRESHOLD.
        """
        p = self.predict_proba(record)
        return p >= SIGNAL_THRESHOLD, round(p, 4)

    # ── Persist ─────────────────────────────────────────────────────────────

    def _save(self):
        """Guarda coeficientes (solo para LR; XGBoost usa pickle separado)."""
        try:
            import pickle
            with open(_MODEL_PATH.replace(".json", ".pkl"), "wb") as f:
                pickle.dump(self._model, f)
            meta = {
                "fitted": self._fitted,
                "n_train": self._n_train,
                "feature_names": self._feature_names,
            }
            with open(_MODEL_PATH, "w") as f:
                json.dump(meta, f)
        except Exception:
            pass

    def _load(self):
        """Carga modelo guardado si existe."""
        try:
            pkl = _MODEL_PATH.replace(".json", ".pkl")
            if not os.path.exists(_MODEL_PATH) or not os.path.exists(pkl):
                return
            with open(_MODEL_PATH) as f:
                meta = json.load(f)
            import pickle
            with open(pkl, "rb") as f:
                self._model = pickle.load(f)
            self._fitted = meta.get("fitted", False)
            self._n_train = meta.get("n_train", 0)
        except Exception:
            pass

    def status(self) -> dict:
        return {
            "fitted": self._fitted,
            "n_train": self._n_train,
            "signal_threshold": SIGNAL_THRESHOLD,
            "move_threshold": MOVE_THRESHOLD,
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_predictor: LineMovementPredictor | None = None


def get_predictor() -> LineMovementPredictor:
    global _predictor
    if _predictor is None:
        _predictor = LineMovementPredictor()
    return _predictor


def record_line_movement(
    sport: str,
    home: str,
    away: str,
    p_model: float,
    odds_open: float,
    odds_close: float,
    edge: float,
    hours_to_game: float = 12.0,
    odds_open_other: float = None,
):
    """
    Registra un movimiento de línea para futura reentrenamiento.
    Guarda en _cache/line_movement_training.json.
    """
    path = os.path.join(CACHE_DIR, "line_movement_training.json")
    try:
        history = []
        if os.path.exists(path):
            with open(path) as f:
                history = json.load(f)
        history.append({
            "sport": sport,
            "home": home,
            "away": away,
            "p_model": round(p_model, 4),
            "odds_open": round(odds_open, 4),
            "odds_close": round(odds_close, 4),
            "edge": round(edge, 4),
            "hours_to_game": hours_to_game,
            "odds_open_other": odds_open_other,
        })
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "w") as f:
            json.dump(history, f)
    except Exception:
        pass


if __name__ == "__main__":
    pred = get_predictor()
    if pred._fitted:
        print(f"  Modelo cargado: {pred._n_train} ejemplos de entrenamiento")
        # Demo
        test = {"sport": "MLB", "p_model": 0.68, "odds_open": 1.75,
                "odds_open_other": 2.20, "edge": 0.04, "hours_to_game": 10}
        signal, prob = pred.has_favorable_signal(test)
        print(f"  Demo: p(mov_favorable)={prob:.2%}  señal={'✅' if signal else '❌'}")
    else:
        print("  Modelo no entrenado aún.")
        print("  Ejecuta: pred.fit_from_clv_history() cuando tengas historial de líneas.")
        pred.fit_from_clv_history()
