"""
Phase 1.4 — Protocolo DEV/VAL ciego.

Reglas:
  1. DEV = primera mitad temporal de los datos  → tunear aquí.
  2. VAL = segunda mitad                         → evaluar SOLO top-3 configs de DEV.
  3. Nunca mirar VAL antes de fijar la config.
  4. Si ROI/CLV en VAL diverge de DEV → config descartada (overfit).
  5. Resultados VAL son la verdad: lo que se publicará.

Criterio de aceptación (ambos deben cumplirse):
  - CLV promedio VAL > +1.5%
  - ROI VAL > 0%  (positivo, no importa cuánto)
  - Signo consistente: sign(ROI_DEV) == sign(ROI_VAL)

Uso:
    python validacion.py --deporte MLB --configs configs.json
    python validacion.py --deporte NBA --quick   # solo muestra el split
"""

import os
import json
import warnings
import argparse
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")

# Criterios de aceptación
CLV_MIN_VAL   = 0.015   # 1.5%
ROI_MIN_VAL   = 0.0     # positivo
MAX_CONFIGS   = 3       # evaluar máximo top-3 en VAL


def _load_sport_data(sport: str) -> pd.DataFrame | None:
    path = os.path.join(CACHE_DIR, f"{sport}_train.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    return df if len(df) >= 200 else None


def get_dev_val_split(sport: str) -> tuple[pd.DataFrame, pd.DataFrame] | tuple[None, None]:
    """
    Retorna (dev_df, val_df) donde dev = primera mitad temporal, val = segunda.
    El split es por fecha para evitar leakage temporal.
    """
    df = _load_sport_data(sport)
    if df is None:
        print(f"  [{sport}] Sin datos suficientes para DEV/VAL split.")
        return None, None

    midpoint = len(df) // 2
    mid_date = df.iloc[midpoint]["date"]

    dev = df[df["date"] < mid_date].copy()
    val = df[df["date"] >= mid_date].copy()

    print(f"  [{sport}] DEV: {len(dev)} juegos ({dev['date'].min().date()} → {dev['date'].max().date()})")
    print(f"  [{sport}] VAL: {len(val)} juegos ({val['date'].min().date()} → {val['date'].max().date()})")
    return dev, val


def _evaluate_config_on_fold(
    sport: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    config: dict,
    api_key: str = None,
) -> dict:
    """Evalúa una config en un fold. Wrapper sobre backtest_completo.backtest_fold."""
    try:
        from backtest_completo import backtest_fold
        res = backtest_fold(
            sport=sport,
            train_df=train_df,
            test_df=test_df,
            min_edge=config.get("edge_min", 0.02),
            conf_floor=config.get("cf_floor", 0.54),
            banco=10000,
            api_key=api_key,
        )
        return res
    except Exception as e:
        return {"error": str(e), "n_bets": 0}


def tune_dev(
    sport: str,
    configs: list[dict],
    api_key: str = None,
) -> list[dict]:
    """
    Fase DEV: evalúa todas las configs con walk-forward sobre la mitad DEV.
    Retorna configs ordenadas por CLV descendente + ROI positivo.
    Solo se puede llamar ANTES de ver VAL.

    configs: lista de dicts {edge_min, cf_floor, market_trust, ...}
    """
    dev_df, _ = get_dev_val_split(sport)
    if dev_df is None:
        return []

    print(f"\n{'─'*60}")
    print(f"  FASE DEV — {sport}  ({len(configs)} configs)")
    print(f"{'─'*60}")

    # Walk-forward sobre DEV: 6 meses train mínimo, 1 mes test
    dev_df["_period"] = dev_df["date"].dt.to_period("M")
    periods = sorted(dev_df["_period"].unique())
    MIN_TRAIN = 6

    results = []
    for cfg_idx, cfg in enumerate(configs):
        fold_rois, fold_clvs = [], []
        for test_idx in range(MIN_TRAIN, len(periods)):
            train_p = periods[:test_idx]
            test_p  = periods[test_idx]
            tr = dev_df[dev_df["_period"].isin(train_p)].drop(columns=["_period"])
            te = dev_df[dev_df["_period"] == test_p].drop(columns=["_period"])
            if len(tr) < 80 or len(te) < 10:
                continue
            res = _evaluate_config_on_fold(sport, tr, te, cfg, api_key)
            if res.get("n_bets", 0) > 0:
                fold_rois.append(res.get("roi_flat", 0))
                fold_clvs.append(res.get("avg_clv", 0))

        if not fold_rois:
            avg_roi, avg_clv = 0.0, 0.0
        else:
            avg_roi = float(np.mean(fold_rois))
            avg_clv = float(np.mean(fold_clvs))

        results.append({
            "config": cfg,
            "roi_dev": round(avg_roi, 4),
            "clv_dev": round(avg_clv, 4),
            "n_folds_dev": len(fold_rois),
        })
        roi_icon = "✅" if avg_roi > 0 else "❌"
        clv_icon = "✅" if avg_clv > 0.015 else ("⚠️" if avg_clv > 0 else "❌")
        print(f"  Config {cfg_idx+1:>2}: edge={cfg.get('edge_min',0):.2f} cf={cfg.get('cf_floor',0):.2f} "
              f"→ ROI={avg_roi:+.2%} {roi_icon}  CLV={avg_clv:+.2%} {clv_icon}  folds={len(fold_rois)}")

    # Ordenar: primero CLV > 1.5% + ROI > 0, luego por CLV desc
    def _score(r):
        if r["clv_dev"] > CLV_MIN_VAL and r["roi_dev"] > 0:
            return (2, r["clv_dev"])
        if r["clv_dev"] > 0:
            return (1, r["clv_dev"])
        return (0, r["clv_dev"])

    results.sort(key=_score, reverse=True)

    top = results[:MAX_CONFIGS]
    print(f"\n  Top-{len(top)} configs seleccionadas para VAL:")
    for i, r in enumerate(top):
        print(f"    #{i+1}: {r['config']}  DEV_ROI={r['roi_dev']:+.2%}  DEV_CLV={r['clv_dev']:+.2%}")

    return top


def validate_val(
    sport: str,
    top_configs: list[dict],
    api_key: str = None,
) -> list[dict]:
    """
    Fase VAL: evalúa SOLO las top configs de DEV sobre la mitad VAL.
    IMPORTANTE: esta función SOLO se llama una vez — los resultados son definitivos.

    Retorna configs con veredicto final.
    """
    _, val_df = get_dev_val_split(sport)
    if val_df is None:
        return []

    print(f"\n{'═'*60}")
    print(f"  FASE VAL — {sport}  (EVALUACIÓN FINAL — solo una vez)")
    print(f"{'═'*60}")
    print(f"  ⚠️  Estos resultados son definitivos. No ajustar más parámetros.")
    print(f"{'─'*60}")

    val_df["_period"] = val_df["date"].dt.to_period("M")
    periods = sorted(val_df["_period"].unique())
    MIN_TRAIN_VAL = 3  # VAL tiene menos datos, reducimos mínimo

    final_results = []
    for r in top_configs:
        cfg = r["config"]
        fold_rois, fold_clvs = [], []
        for test_idx in range(MIN_TRAIN_VAL, len(periods)):
            train_p = periods[:test_idx]
            test_p  = periods[test_idx]
            tr = val_df[val_df["_period"].isin(train_p)].drop(columns=["_period"])
            te = val_df[val_df["_period"] == test_p].drop(columns=["_period"])
            if len(tr) < 50 or len(te) < 5:
                continue
            res = _evaluate_config_on_fold(sport, tr, te, cfg, api_key)
            if res.get("n_bets", 0) > 0:
                fold_rois.append(res.get("roi_flat", 0))
                fold_clvs.append(res.get("avg_clv", 0))

        avg_roi_val = float(np.mean(fold_rois)) if fold_rois else 0.0
        avg_clv_val = float(np.mean(fold_clvs)) if fold_clvs else 0.0

        # Veredicto
        sign_ok = (r["roi_dev"] > 0) == (avg_roi_val > 0)
        clv_ok  = avg_clv_val > CLV_MIN_VAL
        roi_ok  = avg_roi_val > ROI_MIN_VAL

        if clv_ok and roi_ok and sign_ok:
            veredicto = "✅ ACEPTADA — usar en producción"
        elif sign_ok and avg_clv_val > 0:
            veredicto = "⚠️ MARGINAL — monitorear con CLV rolling"
        else:
            veredicto = "❌ RECHAZADA — overfit o sin edge real"

        entry = {
            "config": cfg,
            "roi_dev":  r["roi_dev"],
            "clv_dev":  r["clv_dev"],
            "roi_val":  round(avg_roi_val, 4),
            "clv_val":  round(avg_clv_val, 4),
            "sign_ok":  sign_ok,
            "veredicto": veredicto,
        }
        final_results.append(entry)

        print(f"\n  Config: {cfg}")
        print(f"    DEV → ROI={r['roi_dev']:+.2%}  CLV={r['clv_dev']:+.2%}")
        print(f"    VAL → ROI={avg_roi_val:+.2%}  CLV={avg_clv_val:+.2%}")
        print(f"    Signo consistente: {'✅' if sign_ok else '❌'}")
        print(f"    VEREDICTO: {veredicto}")

    print(f"\n{'═'*60}")
    accepted = [r for r in final_results if "ACEPTADA" in r["veredicto"]]
    marginal = [r for r in final_results if "MARGINAL" in r["veredicto"]]
    print(f"  Aceptadas: {len(accepted)}  |  Marginales: {len(marginal)}  |  Rechazadas: {len(final_results)-len(accepted)-len(marginal)}")
    if accepted:
        best = max(accepted, key=lambda r: r["clv_val"])
        print(f"  CONFIG RECOMENDADA: {best['config']}")
        print(f"    CLV_VAL={best['clv_val']:+.2%}  ROI_VAL={best['roi_val']:+.2%}")
    print(f"{'═'*60}\n")

    return final_results


def save_validation_results(sport: str, results: list[dict]):
    """Guarda resultados de validación en _cache/validation_{sport}.json."""
    path = os.path.join(CACHE_DIR, f"validation_{sport}.json")
    os.makedirs(CACHE_DIR, exist_ok=True)
    import datetime
    data = {
        "sport": sport,
        "timestamp": datetime.datetime.now().isoformat(),
        "results": results,
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Resultados guardados en {path}")


def load_best_config(sport: str) -> dict | None:
    """Carga la mejor config aceptada de la última validación."""
    path = os.path.join(CACHE_DIR, f"validation_{sport}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        data = json.load(f)
    accepted = [r for r in data.get("results", []) if "ACEPTADA" in r.get("veredicto", "")]
    if not accepted:
        return None
    return max(accepted, key=lambda r: r["clv_val"])["config"]


# ─── Grid de configs estándar para tuning ───────────────────────────

DEFAULT_GRID = [
    {"edge_min": 0.020, "cf_floor": 0.54, "market_trust": 0.50},
    {"edge_min": 0.025, "cf_floor": 0.56, "market_trust": 0.50},
    {"edge_min": 0.030, "cf_floor": 0.58, "market_trust": 0.55},
    {"edge_min": 0.035, "cf_floor": 0.60, "market_trust": 0.55},
    {"edge_min": 0.020, "cf_floor": 0.60, "market_trust": 0.40},
    {"edge_min": 0.025, "cf_floor": 0.62, "market_trust": 0.45},
    {"edge_min": 0.030, "cf_floor": 0.62, "market_trust": 0.60},
    {"edge_min": 0.040, "cf_floor": 0.64, "market_trust": 0.65},
]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--deporte",  default="MLB")
    ap.add_argument("--configs",  default=None, help="JSON con lista de configs")
    ap.add_argument("--api-key",  default=None)
    ap.add_argument("--quick",    action="store_true", help="Solo mostrar el split")
    ap.add_argument("--solo-val", action="store_true", help="Saltar DEV, ir a VAL con configs guardadas")
    args = ap.parse_args()

    sport = args.deporte.upper()

    if args.quick:
        get_dev_val_split(sport)
    else:
        configs = DEFAULT_GRID
        if args.configs:
            with open(args.configs) as f:
                configs = json.load(f)

        if args.solo_val:
            path = os.path.join(CACHE_DIR, f"dev_top_{sport}.json")
            if not os.path.exists(path):
                print(f"  ERROR: No hay top configs de DEV. Ejecuta primero sin --solo-val.")
            else:
                with open(path) as f:
                    top = json.load(f)
                final = validate_val(sport, top, args.api_key)
                save_validation_results(sport, final)
        else:
            top = tune_dev(sport, configs, args.api_key)
            # Guardar top configs para VAL posterior
            top_path = os.path.join(CACHE_DIR, f"dev_top_{sport}.json")
            with open(top_path, "w") as f:
                json.dump(top, f, indent=2)
            print(f"\n  Top configs guardadas en {top_path}")
            print(f"  Para validar: python validacion.py --deporte {sport} --solo-val")
