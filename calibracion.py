"""
Calibración del modelo por deporte y rango de probabilidad.
Genera reliability diagrams y detecta over/under confidence.
"""

import os
import csv
from typing import Optional

PICKS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "_cache", "picks_history.csv")

# Buckets: (low_inclusive, high_exclusive, label)
BUCKETS = [
    (0.50, 0.55, "50-55%"),
    (0.55, 0.60, "55-60%"),
    (0.60, 0.65, "60-65%"),
    (0.65, 0.70, "65-70%"),
    (0.70, 0.75, "70-75%"),
    (0.75, 1.01, "75%+  "),
]


def _load_resolved(picks_csv_path: str, sport: Optional[str]) -> list:
    """Lee el CSV y devuelve solo filas con result win/loss, filtrando por sport."""
    rows = []
    if not os.path.exists(picks_csv_path):
        return rows
    with open(picks_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("result", "").lower() not in ("win", "loss"):
                continue
            if sport and row.get("sport", "").upper() != sport.upper():
                continue
            try:
                model_p = float(row["model_p"])
                is_win = row["result"].lower() == "win"
                rows.append({"model_p": model_p, "win": is_win, "sport": row.get("sport", "")})
            except (ValueError, KeyError):
                continue
    return rows


def compute_calibration(picks_csv_path: str = PICKS_CSV, sport: Optional[str] = None) -> dict:
    """
    Lee picks resueltos, calcula calibración por bucket de probabilidad.

    Returns dict con:
    - sport: str
    - n_total: int
    - buckets: list of dicts {label, lo, hi, n_picks, win_rate, avg_model_p, error}
    - brier_score: float
    - ece: float (Expected Calibration Error, as %)
    """
    rows = _load_resolved(picks_csv_path, sport)

    # Brier score acumulado
    brier_sum = 0.0
    n_total = len(rows)

    # Preparar buckets
    bucket_data = []
    for lo, hi, label in BUCKETS:
        bucket_rows = [r for r in rows if lo <= r["model_p"] < hi]
        n = len(bucket_rows)
        if n == 0:
            bucket_data.append({
                "label": label, "lo": lo, "hi": hi,
                "n_picks": 0, "win_rate": None, "avg_model_p": None, "error": None
            })
            continue
        wins = sum(1 for r in bucket_rows if r["win"])
        win_rate = wins / n
        avg_p = sum(r["model_p"] for r in bucket_rows) / n
        error = win_rate - avg_p  # positive = model underestimates, negative = overestimates
        bucket_data.append({
            "label": label, "lo": lo, "hi": hi,
            "n_picks": n, "win_rate": win_rate, "avg_model_p": avg_p, "error": error
        })

    # Brier score: mean((p - outcome)^2)
    if n_total > 0:
        brier_sum = sum((r["model_p"] - (1.0 if r["win"] else 0.0)) ** 2 for r in rows)
        brier_score = brier_sum / n_total
    else:
        brier_score = None

    # ECE: weighted average of |error| per bucket
    if n_total > 0:
        ece = sum(
            b["n_picks"] / n_total * abs(b["error"])
            for b in bucket_data if b["error"] is not None
        )
    else:
        ece = None

    return {
        "sport": sport or "ALL",
        "n_total": n_total,
        "buckets": bucket_data,
        "brier_score": round(brier_score, 4) if brier_score is not None else None,
        "ece": round(ece * 100, 2) if ece is not None else None,  # as percentage
    }


def print_calibration_report(sport: Optional[str] = None) -> None:
    """Imprime tabla de calibración por bucket con indicadores visuales."""
    cal = compute_calibration(sport=sport)
    sport_label = cal["sport"]

    print(f"\n{'═' * 55}")
    print(f"  CALIBRACIÓN DEL MODELO — {sport_label}")
    print(f"{'═' * 55}")

    if cal["n_total"] == 0:
        print("  Sin datos históricos resueltos.")
        print(f"{'═' * 55}\n")
        return

    print(f"  {'Rango p':<10} | {'Picks':>5} | {'Win% real':>9} | {'Modelo p':>8} | {'Error':>7}")
    print(f"  {'-'*10}-+-{'-'*5}-+-{'-'*9}-+-{'-'*8}-+-{'-'*10}")

    for b in cal["buckets"]:
        if b["n_picks"] == 0:
            print(f"  {b['label']:<10} | {'—':>5} | {'—':>9} | {'—':>8} |  sin datos")
            continue
        err_pct = b["error"] * 100
        abs_err = abs(err_pct)
        if abs_err < 5:
            indicator = "✅"
        elif abs_err < 10:
            indicator = "⚠️ "
        else:
            indicator = "❌"
        sign = "+" if err_pct >= 0 else ""
        print(
            f"  {b['label']:<10} | {b['n_picks']:>5} | {b['win_rate']:>8.1%}  "
            f"| {b['avg_model_p']:>7.1%}  | {sign}{err_pct:.1f}%  {indicator}"
        )

    brier_str = f"{cal['brier_score']:.3f}" if cal["brier_score"] is not None else "N/A"
    ece_str = f"{cal['ece']:.1f}%" if cal["ece"] is not None else "N/A"
    print(f"\n  Brier: {brier_str}   ECE: {ece_str}")
    print(f"  Total picks resueltos: {cal['n_total']}")
    print(f"{'═' * 55}\n")


def save_calibration_plot(output_path: str, sport: Optional[str] = None) -> None:
    """
    Genera reliability diagram (diagonal perfecta + puntos del modelo).
    Si matplotlib no está disponible: skip silenciosamente.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    cal = compute_calibration(sport=sport)
    buckets = [b for b in cal["buckets"] if b["n_picks"] > 0 and b["win_rate"] is not None]

    if not buckets:
        return

    fig, ax = plt.subplots(figsize=(6, 6))

    # Diagonal perfecta
    ax.plot([0, 1], [0, 1], "k--", label="Calibración perfecta", linewidth=1.5)

    # Puntos del modelo
    model_ps = [b["avg_model_p"] for b in buckets]
    win_rates = [b["win_rate"] for b in buckets]
    sizes = [max(30, b["n_picks"] * 5) for b in buckets]

    ax.scatter(model_ps, win_rates, s=sizes, color="steelblue", zorder=5, label="Modelo")

    # Anotar cada punto con n
    for b in buckets:
        ax.annotate(
            f"n={b['n_picks']}",
            (b["avg_model_p"], b["win_rate"]),
            textcoords="offset points", xytext=(5, 5), fontsize=8
        )

    ax.set_xlim(0.45, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("Probabilidad del modelo")
    ax.set_ylabel("Win rate real")
    sport_label = cal["sport"]
    ax.set_title(f"Reliability Diagram — {sport_label}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    brier_str = f"{cal['brier_score']:.3f}" if cal["brier_score"] is not None else "N/A"
    ece_str = f"{cal['ece']:.1f}%" if cal["ece"] is not None else "N/A"
    ax.text(
        0.05, 0.95, f"Brier: {brier_str}  ECE: {ece_str}",
        transform=ax.transAxes, fontsize=9, verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5)
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close(fig)


def get_calibration_adjustment(model_p: float, sport: str) -> float:
    """
    Aplica corrección a model_p basada en calibración histórica del sport.

    Reglas:
    - Solo ajusta si hay >= 50 picks resueltos en el deporte.
    - Si el bucket tiene < 10 picks: devuelve model_p sin cambios.
    - Si hay datos suficientes: ajusta model_p hacia win_rate_real del bucket.
    """
    cal = compute_calibration(sport=sport)

    if cal["n_total"] < 50:
        return model_p

    # Encontrar el bucket correspondiente
    for b in cal["buckets"]:
        if b["lo"] <= model_p < b["hi"]:
            if b["n_picks"] < 10 or b["win_rate"] is None:
                return model_p
            # Ajuste: interpolar hacia win_rate histórico
            # Usamos 50% del ajuste para no sobre-corregir
            adjusted = model_p + 0.5 * b["error"]
            # Clampar entre 0.01 y 0.99
            return max(0.01, min(0.99, adjusted))

    return model_p


if __name__ == "__main__":
    print_calibration_report()
    for sport in ("MLB", "NBA", "NHL"):
        print_calibration_report(sport=sport)
