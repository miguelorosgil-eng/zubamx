"""
Calibración Platt Scaling para corregir sobreconfianza del modelo.

El problema diagnosticado:
  - NBA: predice 75-80% → acierto real 60-62%
  - NHL: predice 70-75% → acierto real 60%
  - MLB: predice 65-70% → acierto real 55%

Solución: LogisticRegression sobre (p_model → resultado real)
entrenada en datos históricos → genera probabilidades calibradas.

Uso:
    cal = PlattCalibrator(sport='nba')
    cal.fit_from_history(df_train)       # df con columnas p_model, result (0/1)
    p_calibrada = cal.transform(0.78)    # 0.78 → 0.63 (más honesto)
    cal.save() / cal.load()              # persiste en _cache/
"""

import os
import json
import numpy as np

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class PlattCalibrator:
    """
    Calibrador logístico: ajusta probabilidades del modelo a realidad histórica.
    Funciona incluso sin sklearn (usa implementación propia de regresión logística).
    """

    def __init__(self, sport: str):
        self.sport = sport.upper()
        self._a = 1.0   # coef multiplicativo (logit space)
        self._b = 0.0   # intercepto
        self._fitted = False
        self._n_samples = 0

    # ── Fit ─────────────────────────────────────────────────────────────────

    def fit_from_history(self, df):
        """
        Entrena con DataFrame que tiene columnas 'p_model' y 'result' (0/1).
        Requiere mínimo 50 observaciones.
        """
        if df is None or len(df) < 50:
            return self

        ps = np.array(df["p_model"].astype(float))
        ys = np.array(df["result"].astype(float))

        # Clamp para evitar log(0)
        ps = np.clip(ps, 1e-6, 1 - 1e-6)
        logits = np.log(ps / (1 - ps))

        # Regresión logística manual (gradiente descendente)
        a, b = 1.0, 0.0
        lr = 0.01
        for _ in range(2000):
            z = a * logits + b
            p_hat = 1 / (1 + np.exp(-z))
            err = p_hat - ys
            a -= lr * np.dot(err, logits) / len(ys)
            b -= lr * err.mean()

        self._a = float(a)
        self._b = float(b)
        self._fitted = True
        self._n_samples = len(df)
        return self

    def fit_from_backtest(self, sport: str):
        """
        Entrena directamente desde los datos de backtesting histórico ya calculados.
        Soporta tanto backtest v1 (columna p_model) como v2 (columna p_raw).
        """
        import pandas as pd
        # Intentar primero v2, luego v1
        for fname in [f"backtest_v2_{sport}.csv", f"backtest_{sport}.csv"]:
            cache = os.path.join(CACHE_DIR, fname)
            if not os.path.exists(cache):
                continue
            df = pd.read_csv(cache)
            # Normalizar nombre de columna de probabilidad
            if "p_raw" in df.columns:
                df = df.rename(columns={"p_raw": "p_model"})
            if "p_model" not in df.columns or "result" not in df.columns:
                continue
            return self.fit_from_history(df)
        return self

    # ── Transform ────────────────────────────────────────────────────────────

    def transform(self, p: float) -> float:
        """Convierte p_model en p_calibrada. Sin datos: devuelve p sin cambio."""
        if not self._fitted or self._n_samples < 50:
            return p
        p = float(np.clip(p, 1e-6, 1 - 1e-6))
        logit = np.log(p / (1 - p))
        z = self._a * logit + self._b
        return float(1 / (1 + np.exp(-z)))

    def transform_batch(self, ps):
        return [self.transform(p) for p in ps]

    # ── Persist ──────────────────────────────────────────────────────────────

    def save(self):
        path = os.path.join(CACHE_DIR, f"platt_{self.sport.lower()}.json")
        with open(path, "w") as f:
            json.dump({"a": self._a, "b": self._b,
                       "fitted": self._fitted, "n": self._n_samples}, f)

    def load(self):
        path = os.path.join(CACHE_DIR, f"platt_{self.sport.lower()}.json")
        if not os.path.exists(path):
            return self
        with open(path) as f:
            d = json.load(f)
        self._a = d["a"]; self._b = d["b"]
        self._fitted = d["fitted"]; self._n_samples = d["n"]
        return self

    # ── Report ───────────────────────────────────────────────────────────────

    def report(self) -> str:
        if not self._fitted:
            return f"[Platt-{self.sport}] Sin calibrar (necesita ≥50 muestras)"
        direction = "sobreconfiado" if self._a < 1 else "subestima"
        return (f"[Platt-{self.sport}] a={self._a:.3f} b={self._b:.3f} "
                f"n={self._n_samples}  ({direction})")


def get_calibrator(sport: str, auto_fit: bool = True) -> PlattCalibrator:
    """
    Devuelve un calibrador listo para usar.
    Intenta cargar de disco; si no existe, entrena desde backtest histórico.
    """
    cal = PlattCalibrator(sport)
    cal.load()
    if not cal._fitted and auto_fit:
        cal.fit_from_backtest(sport)
        if cal._fitted:
            cal.save()
    return cal


def calibrate_all_sports():
    """Entrena y guarda calibradores para MLB, NBA, NHL desde datos históricos."""
    print("\nCalibrando modelos con Platt Scaling...")
    for sport in ["MLB", "NBA", "NHL"]:
        cal = PlattCalibrator(sport)
        cal.fit_from_backtest(sport)
        if cal._fitted:
            cal.save()
            print(f"  {cal.report()}")
        else:
            print(f"  {sport}: sin datos de backtest — corre backtesting primero")
    print()


if __name__ == "__main__":
    calibrate_all_sports()

    # Mostrar efecto de calibración en cada deporte
    import pandas as pd
    print("Efecto de calibración (p_modelo → p_calibrada):")
    print(f"{'Deporte':<8} {'p_raw':>8} {'p_cal':>8} {'ajuste':>8}")
    print("-" * 36)
    for sport in ["MLB", "NBA", "NHL"]:
        cal = get_calibrator(sport)
        for p_raw in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]:
            p_cal = cal.transform(p_raw)
            diff = p_cal - p_raw
            print(f"  {sport:<6} {p_raw:.0%}     {p_cal:.0%}    {diff:+.0%}")
        print()
