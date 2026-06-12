"""
Tracking de picks y resultados para calcular ROI acumulado.
Guarda picks en CSV y actualiza resultados automáticamente.
"""
import os
import csv
import datetime
import requests
import pandas as pd
from pathlib import Path

TRACKER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "_cache", "picks_history.csv")

COLS = ["date", "sport", "home", "away", "pick_team", "pick_side",
        "market", "model_p", "odds", "stake", "result", "profit"]


def _ensure_file():
    Path(os.path.dirname(TRACKER_FILE)).mkdir(exist_ok=True)
    if not os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=COLS).writeheader()


def save_picks(picks: list, date_str: str, stake_per_pick: float = 100.0):
    """
    Guarda picks del día en el CSV. result="pending" hasta actualizarse.
    picks: lista de dicts {sport, home, away, pick_team, pick_side,
                           market, model_p, odds_offered, kelly_frac}
    """
    _ensure_file()
    rows = []
    for p in picks:
        rows.append({
            "date": date_str,
            "sport": p.get("sport", ""),
            "home": p.get("home", ""),
            "away": p.get("away", ""),
            "pick_team": p.get("pick_team", p.get("label", "")),
            "pick_side": p.get("pick_side", p.get("market", "")),
            "market": p.get("market", "ML"),
            "model_p": round(p.get("model_p", 0), 4),
            "odds": p.get("odds_offered", p.get("odds", 0)),
            "stake": round(stake_per_pick, 2),
            "result": "pending",
            "profit": 0.0,
        })
    with open(TRACKER_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLS)
        writer.writerows(rows)
    print(f"  📝 Guardados {len(rows)} picks en historial.")


def _fetch_mlb_results(date_str: str, retries: int = 3) -> dict:
    """
    P3.4 — Descarga resultados MLB con reintentos y manejo de partidos pospuestos.
    Devuelve {game_id: {home, away, home_score, away_score, status}}.
    game_id = MLB statsapi gamePk (evita falsos positivos por nombre).
    """
    url = "https://statsapi.mlb.com/api/v1/schedule"
    for attempt in range(retries):
        try:
            r = requests.get(
                url,
                params={"sportId": 1, "date": date_str, "hydrate": "linescore"},
                timeout=20,
            )
            r.raise_for_status()
            results = {}
            for day in r.json().get("dates", []):
                for g in day.get("games", []):
                    status = g.get("status", {}).get("abstractGameState", "")
                    game_pk = g.get("gamePk")
                    home_team = g["teams"]["home"]["team"]["name"]
                    away_team = g["teams"]["away"]["team"]["name"]

                    if status == "Postponed":
                        # P3.4: partido pospuesto → void (no win/loss)
                        results[game_pk] = {
                            "home": home_team, "away": away_team,
                            "status": "postponed",
                            "home_score": None, "away_score": None,
                        }
                        continue

                    if status != "Final":
                        continue

                    ls = g.get("linescore", {})
                    hs = ls.get("teams", {}).get("home", {}).get("runs")
                    as_ = ls.get("teams", {}).get("away", {}).get("runs")
                    if hs is None:
                        continue
                    results[game_pk] = {
                        "home": home_team, "away": away_team,
                        "status": "final",
                        "home_score": int(hs), "away_score": int(as_),
                    }
            return results
        except Exception as e:
            if attempt < retries - 1:
                import time; time.sleep(2 ** attempt)
            else:
                print(f"  ⚠️ MLB results fetch falló tras {retries} intentos: {e}")
    return {}


def update_results(date_str: str = None):
    """
    Actualiza picks pendientes de una fecha con resultados reales.
    date_str: YYYY-MM-DD. Por defecto: ayer.
    """
    _ensure_file()
    date_str = date_str or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    df = pd.read_csv(TRACKER_FILE)
    pending = df[(df["date"] == date_str) & (df["result"] == "pending")]
    if pending.empty:
        print(f"  No hay picks pendientes para {date_str}")
        return

    # Descargar resultados por deporte
    results_mlb = _fetch_mlb_results(date_str)

    updated = 0
    voided = 0
    from difflib import SequenceMatcher

    def _match_game(home, away, results_by_pk):
        """P3.4: empareja por ID (gamePk) via fuzzy del nombre."""
        best_pk, best_score = None, 0.0
        for pk, g in results_by_pk.items():
            sh = SequenceMatcher(None, home.lower(), g["home"].lower()).ratio()
            sa = SequenceMatcher(None, away.lower(), g["away"].lower()).ratio()
            score = (sh + sa) / 2
            if score > best_score:
                best_pk, best_score = pk, score
        return (best_pk, results_by_pk[best_pk]) if best_pk and best_score > 0.55 else (None, None)

    for idx, row in pending.iterrows():
        sport = str(row.get("sport", "")).upper()
        home, away = str(row["home"]), str(row["away"])
        pick = str(row["pick_team"])
        odds = float(row["odds"])
        stake = float(row["stake"])

        if sport == "MLB":
            game_pk, game = _match_game(home, away, results_mlb)
            if game is None:
                continue

            # P3.4: partido pospuesto → void (no win/loss, stake devuelto)
            if game["status"] == "postponed":
                df.at[idx, "result"] = "void"
                df.at[idx, "profit"] = 0.0
                voided += 1
                continue

            hs, as_ = game["home_score"], game["away_score"]
            winner = game["home"] if hs > as_ else game["away"]

            if row["market"] == "ML":
                won = (pick == winner or pick in winner or winner in pick)
                profit = round(stake * (odds - 1) if won else -stake, 2)
                df.at[idx, "result"] = "win" if won else "loss"
                df.at[idx, "profit"] = profit
                updated += 1

    df.to_csv(TRACKER_FILE, index=False)
    if voided:
        print(f"  🔄 {voided} picks marcados como VOID (pospuestos) para {date_str}")
    print(f"  ✅ Actualizados {updated} picks para {date_str}")


def get_stats() -> dict:
    """Devuelve estadísticas acumuladas de todos los picks resueltos."""
    _ensure_file()
    df = pd.read_csv(TRACKER_FILE)
    resolved = df[df["result"].isin(["win", "loss", "void"])]
    if resolved.empty:
        return {"total": 0}

    # Excluir voids del cálculo de ROI (no son pérdidas reales)
    active = resolved[resolved["result"].isin(["win", "loss"])]
    n_void = int((resolved["result"] == "void").sum())
    wins = int((active["result"] == "win").sum())
    total = len(active)
    invested = active["stake"].sum()
    profit = active["profit"].sum()

    by_sport = {}
    for sport, grp in active.groupby("sport"):
        w = (grp["result"] == "win").sum()
        inv = grp["stake"].sum()
        prf = grp["profit"].sum()
        by_sport[sport] = {
            "wins": int(w), "total": len(grp),
            "pct": round(w / len(grp) * 100, 1),
            "roi": round(prf / inv * 100 if inv > 0 else 0, 1),
        }

    return {
        "total": total,
        "void": n_void,
        "wins": wins,
        "pct": round(wins / total * 100, 1),
        "invested": round(float(invested), 2),
        "profit": round(float(profit), 2),
        "roi": round(float(profit / invested * 100) if invested > 0 else 0, 1),
        "by_sport": by_sport,
    }


def print_stats():
    """Imprime tabla de estadísticas acumuladas."""
    stats = get_stats()
    if stats.get("total", 0) == 0:
        print("  📊 Sin historial de picks todavía.")
        return
    print(f"\n{'═'*55}")
    print(f"  📊 HISTORIAL ACUMULADO ({stats['total']} picks)")
    print(f"{'═'*55}")
    print(f"  Aciertos: {stats['wins']}/{stats['total']} ({stats['pct']}%)")
    print(f"  Invertido: ${stats['invested']:,.0f}  |  Profit: ${stats['profit']:+,.0f}  |  ROI: {stats['roi']:+.1f}%")
    if stats.get("by_sport"):
        print(f"  {'Deporte':<8} {'W/T':>8} {'%Acier':>7} {'ROI':>8}")
        print(f"  {'-'*35}")
        for sp, s in stats["by_sport"].items():
            print(f"  {sp:<8} {s['wins']}/{s['total']:>5}  {s['pct']:>6.1f}%  {s['roi']:>+7.1f}%")
    print(f"{'═'*55}\n")


if __name__ == "__main__":
    # Test: actualizar resultados de ayer y ver stats
    update_results()
    print_stats()
