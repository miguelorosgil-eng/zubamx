"""
Monitor de líneas en tiempo real.
Revisa odds cada 30 minutos y alerta cuando detecta value bets o steam moves.
Uso: python monitor.py [--intervalo 30] [--deportes MLB NBA NHL] [--once]
"""
import os, json, time, datetime, warnings
warnings.filterwarnings("ignore")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
STATE_FILE = os.path.join(CACHE_DIR, "monitor_state.json")

SPORT_KEYS = {"MLB": "baseball_mlb", "NBA": "basketball_nba", "NHL": "icehockey_nhl"}


def get_monitor_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_monitor_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, default=str)


def _format_alert(alert: dict) -> str:
    icons = {"steam_move": "📈", "value_bet": "💡", "sharp_confirm": "🔥"}
    icon = icons.get(alert.get("alert_type", ""), "⚡")
    t = alert.get("alert_type", "").upper().replace("_", " ")
    return (f"{icon} [{alert.get('sport','')}] {alert.get('home','')} vs "
            f"{alert.get('away','')} | {t} | "
            f"model={alert.get('model_p', 0):.0%} "
            f"@{alert.get('odds', 0):.2f} | edge={alert.get('edge', 0):+.1%}")


def check_once(sports: list = None, banco: float = 1000,
               filtros: dict = None) -> list:
    from conector_odds import fetch_odds
    from line_movement import get_line_movement, save_opening_lines, format_movement_summary

    sports = sports or ["MLB", "NBA", "NHL"]
    filtros = filtros or {"confidence_floor": 0.65, "edge_threshold": 0.02,
                          "market_trust": 0.5}
    today = datetime.date.today().isoformat()
    alerts = []

    for sport in sports:
        try:
            ml = fetch_odds(sport, region="us")
            if not ml:
                continue
            save_opening_lines(sport, ml, today)
            moves = get_line_movement(sport, ml, today)

            for move in moves:
                alert_type = None
                if move.get("steam_move"):
                    alert_type = "steam_move"

                # Intentar cargar modelo para value bet
                try:
                    from motor_deportes import SportsEngine
                    import pandas as pd
                    cache = os.path.join(CACHE_DIR, f"{sport}_train.csv")
                    if os.path.exists(cache):
                        df = pd.read_csv(cache, parse_dates=["date"])
                        eng = SportsEngine(sport=sport.lower(),
                                           confidence_floor=filtros["confidence_floor"],
                                           edge_threshold=filtros["edge_threshold"],
                                           market_trust=filtros["market_trust"])
                        eng.fit(df)
                        h, a = move["home"], move["away"]
                        if h in eng._teams_seen and a in eng._teams_seen:
                            odds_h = move.get("curr_home", 2.0)
                            odds_a = move.get("curr_away", 2.0)
                            pred = eng.predict(h, a, {"home": odds_h, "away": odds_a})
                            for vb in pred.get("value_bets", []):
                                at = "sharp_confirm" if alert_type == "steam_move" else "value_bet"
                                side = vb["market"]
                                alerts.append({
                                    "sport": sport, "home": h, "away": a,
                                    "alert_type": at,
                                    "model_p": vb["model_p"],
                                    "odds": vb["odds_offered"],
                                    "edge": vb["edge"],
                                    "summary": _format_alert({
                                        "sport": sport, "home": h, "away": a,
                                        "alert_type": at, "model_p": vb["model_p"],
                                        "odds": vb["odds_offered"], "edge": vb["edge"],
                                    }),
                                    "sharp_side": move.get("sharp_side"),
                                    "steam": move.get("steam_move", False),
                                })
                except Exception:
                    if alert_type:
                        alerts.append({
                            "sport": sport, "home": move["home"], "away": move["away"],
                            "alert_type": alert_type,
                            "model_p": 0, "odds": move.get("curr_home", 0),
                            "edge": 0,
                            "summary": format_movement_summary(move),
                        })
        except Exception as e:
            print(f"  [{sport}] Error: {e}")

    return alerts


def run_monitor(sports: list = None, interval_min: int = 30,
                banco: float = 1000, filtros: dict = None):
    try:
        from alertas import send_steam_alert, is_configured
        _has_telegram = is_configured()
    except Exception:
        _has_telegram = False

    sports = sports or ["MLB", "NBA", "NHL"]
    print(f"🔍 Monitor activo — revisando cada {interval_min} min")
    print(f"   Deportes: {', '.join(sports)}")
    print(f"   Telegram: {'✅' if _has_telegram else '❌ (configura alertas.py)'}")
    print("   Ctrl+C para detener\n")

    cycle = 0
    while True:
        cycle += 1
        now = datetime.datetime.now().strftime("%H:%M")
        try:
            alerts = check_once(sports, banco, filtros)
            steam = [a for a in alerts if a["alert_type"] == "steam_move"]
            value = [a for a in alerts if a["alert_type"] == "value_bet"]
            sharp = [a for a in alerts if a["alert_type"] == "sharp_confirm"]
            print(f"[{now}] Ciclo {cycle} | {len(alerts)} alertas "
                  f"(steam={len(steam)} value={len(value)} sharp={len(sharp)})")

            for a in alerts:
                print(f"  {a['summary']}")
                if _has_telegram and a["alert_type"] in ("steam_move", "sharp_confirm"):
                    try:
                        from alertas import send_steam_alert
                        send_steam_alert(a)
                    except Exception:
                        pass

            save_monitor_state({"last_run": str(datetime.datetime.now()),
                                 "cycle": cycle, "last_alerts": len(alerts)})
        except Exception as e:
            print(f"[{now}] Error en ciclo {cycle}: {e}")

        time.sleep(interval_min * 60)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--intervalo", type=int, default=30)
    p.add_argument("--deportes", nargs="*", default=["MLB", "NBA", "NHL"])
    p.add_argument("--banco", type=float, default=1000)
    p.add_argument("--once", action="store_true")
    a = p.parse_args()

    if a.once:
        alerts = check_once(a.deportes, a.banco)
        if alerts:
            for al in alerts:
                print(al["summary"])
        else:
            print("Sin alertas en este momento.")
    else:
        run_monitor(a.deportes, a.intervalo, a.banco)
