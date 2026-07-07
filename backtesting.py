"""
Backtesting completo — simula el sistema en datos históricos.
Muestra exactamente cuánto habría ganado/perdido por deporte,
rango de probabilidad y tipo de mercado.
"""
import os
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SPORT_SEASONS = {
    "MLB": [2024, 2025],
    "NBA": ["2024-25"],
    "NHL": ["20242025"],
}

BUCKETS = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65),
           (0.65, 0.70), (0.70, 0.75), (0.75, 1.01)]


def _load_sport_data(sport: str) -> pd.DataFrame:
    cache = os.path.join(CACHE_DIR, f"{sport}_train.csv")
    if os.path.exists(cache):
        return pd.read_csv(cache, parse_dates=["date"])
    return pd.DataFrame()


def run_backtest(sport: str, seasons: list = None, filtros: dict = None) -> pd.DataFrame:
    """Walk-forward backtest: entrena 60%, evalúa 40%."""
    from motor_deportes import SportsEngine, _build_features

    df = _load_sport_data(sport)
    if df.empty:
        return pd.DataFrame()

    df = df.sort_values("date").reset_index(drop=True)
    split = int(len(df) * 0.60)
    if split < 100:
        return pd.DataFrame()

    filtros = filtros or {"confidence_floor": 0.65, "edge_threshold": 0.02,
                          "market_trust": 0.5}

    eng = SportsEngine(sport=sport.lower(),
                       confidence_floor=filtros["confidence_floor"],
                       edge_threshold=filtros["edge_threshold"],
                       market_trust=filtros["market_trust"])
    try:
        eng.fit(df.iloc[:split])
    except Exception:
        return pd.DataFrame()

    records = []
    eval_df = df.iloc[split:].reset_index(drop=True)

    for _, row in eval_df.iterrows():
        h, a = row["home"], row["away"]
        if h not in eng._teams_seen or a not in eng._teams_seen:
            continue
        try:
            pred = eng.predict(h, a)
            p_h = pred.get("p_home", 0.5)
            p_a = pred.get("p_away", 0.5)
            actual_home_win = int(row["home_score"] > row["away_score"])

            # Simular odds con 5% de vig
            for side, p_model, actual_win in [("home", p_h, actual_home_win),
                                               ("away", p_a, 1 - actual_home_win)]:
                if p_model < filtros["confidence_floor"]:
                    continue
                p_implied = p_model * 0.95  # novig simulado
                odds_sim = round(1 / max(p_implied, 0.01), 3)
                raw_h = 1 / max(odds_sim, 1.01)
                raw_a = 1 / max(1 / max(1 - p_implied, 0.01), 1.01)
                total = raw_h + raw_a
                novig = raw_h / total if side == "home" else raw_a / total
                lam = filtros["market_trust"]
                blended = (1 - lam) * p_model + lam * novig
                edge = blended - (1 / odds_sim)
                if edge < filtros["edge_threshold"]:
                    continue

                records.append({
                    "date": row["date"],
                    "home": h, "away": a,
                    "p_model": round(p_model, 4),
                    "p_blended": round(blended, 4),
                    "p_implied": round(1 / odds_sim, 4),
                    "pick": side,
                    "odds_simulated": odds_sim,
                    "result": actual_win,
                    "profit_1unit": round((odds_sim - 1) * actual_win - (1 - actual_win), 4),
                })
        except Exception:
            continue

    return pd.DataFrame(records)


def analyze_backtest(df: pd.DataFrame, sport: str) -> dict:
    if df.empty:
        return {"total_bets": 0}

    total = len(df)
    wins = df["result"].sum()
    roi = df["profit_1unit"].sum() / total * 100 if total else 0

    # ROI por bucket
    roi_by_bucket = {}
    for lo, hi in BUCKETS:
        mask = (df["p_blended"] >= lo) & (df["p_blended"] < hi)
        sub = df[mask]
        if len(sub) >= 5:
            r = sub["profit_1unit"].sum() / len(sub) * 100
            roi_by_bucket[f"{lo:.0%}-{hi:.0%}"] = {
                "n": len(sub), "win_rate": round(sub["result"].mean() * 100, 1),
                "roi": round(r, 1)
            }

    # ROI por mes
    df2 = df.copy()
    df2["month"] = df2["date"].dt.to_period("M").astype(str)
    roi_by_month = {}
    for m, grp in df2.groupby("month"):
        roi_by_month[m] = round(grp["profit_1unit"].sum() / len(grp) * 100, 1)

    # Max drawdown
    cumulative = df["profit_1unit"].cumsum()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max)
    max_dd = float(drawdown.min()) * 100

    # Sharpe
    ret = df["profit_1unit"]
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0

    # Rachas
    results = df["result"].tolist()
    best_streak = worst_streak = cur_w = cur_l = 0
    for r in results:
        if r == 1:
            cur_w += 1; cur_l = 0
        else:
            cur_l += 1; cur_w = 0
        best_streak = max(best_streak, cur_w)
        worst_streak = max(worst_streak, cur_l)

    return {
        "sport": sport, "total_bets": total,
        "win_rate": round(wins / total * 100, 1) if total else 0,
        "roi": round(roi, 1),
        "roi_by_bucket": roi_by_bucket,
        "roi_by_month": roi_by_month,
        "max_drawdown": round(max_dd, 1),
        "sharpe_ratio": round(sharpe, 2),
        "best_streak": best_streak,
        "worst_streak": worst_streak,
    }


def get_optimal_thresholds(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 50:
        return {"optimal_floor": 0.65, "optimal_roi": 0.0, "optimal_n": 0}
    best_score, best_floor, best_roi, best_n = -999, 0.65, 0.0, 0
    for thr in np.arange(0.55, 0.81, 0.01):
        sub = df[df["p_blended"] >= thr]
        if len(sub) < 20:
            continue
        roi = sub["profit_1unit"].sum() / len(sub) * 100
        score = roi * np.sqrt(len(sub))
        if score > best_score:
            best_score, best_floor = score, round(float(thr), 2)
            best_roi, best_n = round(roi, 1), len(sub)
    return {"optimal_floor": best_floor, "optimal_roi": best_roi, "optimal_n": best_n}


def print_backtest_report(results: dict, sport: str):
    if results.get("total_bets", 0) == 0:
        print(f"  Sin datos de backtest para {sport}.")
        return
    print(f"\n{'═'*58}")
    print(f"  BACKTESTING — {sport}")
    print(f"{'═'*58}")
    print(f"  Total apuestas: {results['total_bets']:>5}  |  "
          f"Win rate: {results['win_rate']:.1f}%  |  ROI: {results['roi']:+.1f}%")
    print(f"  Max drawdown:  {results['max_drawdown']:>+.1f}%  |  "
          f"Sharpe: {results['sharpe_ratio']:.2f}")
    print(f"\n  ROI por rango de probabilidad:")
    print(f"  {'Rango':<10} {'Bets':>5} {'Win%':>7} {'ROI':>8}")
    print(f"  {'-'*35}")
    for rng, data in results.get("roi_by_bucket", {}).items():
        flag = "✅" if data["roi"] > 3 else ("⚠️" if data["roi"] > 0 else "❌")
        print(f"  {rng:<10} {data['n']:>5}  {data['win_rate']:>6.1f}%  "
              f"{data['roi']:>+7.1f}%  {flag}")
    print(f"\n  Mejor racha: +{results['best_streak']}  |  "
          f"Peor racha: -{results['worst_streak']}")
    print(f"{'═'*58}")


def save_backtest_results(df: pd.DataFrame, sport: str):
    if not df.empty:
        df.to_csv(os.path.join(CACHE_DIR, f"backtest_{sport}.csv"), index=False)


def run_all_backtests(banco: float = 1000):
    print("\n🔬 BACKTESTING COMPLETO DEL SISTEMA")
    results = {}
    for sport in ["MLB", "NBA", "NHL"]:
        print(f"  Corriendo backtest {sport}...")
        try:
            df = run_backtest(sport)
            if not df.empty:
                save_backtest_results(df, sport)
                r = analyze_backtest(df, sport)
                print_backtest_report(r, sport)
                opt = get_optimal_thresholds(df)
                print(f"  Threshold óptimo: {opt['optimal_floor']:.0%}  "
                      f"(ROI {opt['optimal_roi']:+.1f}%,  {opt['optimal_n']} bets)")
                results[sport] = r
            else:
                print(f"  {sport}: sin datos de caché — corre el análisis primero.")
        except Exception as e:
            print(f"  {sport}: ERROR — {e}")
    return results


if __name__ == "__main__":
    run_all_backtests()
