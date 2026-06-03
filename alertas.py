"""
Alertas push via Telegram Bot API (gratis, sin servidor propio).

SETUP:
1. Busca @BotFather en Telegram → /newbot → sigue instrucciones
2. Copia el token (ej: 1234567890:ABCdef...)
3. Escríbele al bot para obtener chat_id:
   https://api.telegram.org/bot{TOKEN}/getUpdates
4. Configura:
   python -c "from alertas import setup_telegram; setup_telegram('TOKEN', 'CHAT_ID')"
"""
import os, json, requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
CONFIG_FILE = os.path.join(CACHE_DIR, "telegram_config.json")


def _get_config() -> dict:
    cfg = {}
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
    except Exception:
        pass
    return {
        "token":   cfg.get("token")   or os.getenv("TELEGRAM_TOKEN", ""),
        "chat_id": cfg.get("chat_id") or os.getenv("TELEGRAM_CHAT_ID", ""),
    }


def setup_telegram(token: str, chat_id: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump({"token": token, "chat_id": chat_id}, f)
    print(f"✅ Telegram configurado. Enviando mensaje de prueba...")
    if test_connection():
        print("✅ Conexión exitosa — recibirás alertas en Telegram.")
    else:
        print("❌ No se pudo conectar. Verifica el token y chat_id.")


def is_configured() -> bool:
    cfg = _get_config()
    return bool(cfg.get("token") and cfg.get("chat_id"))


def send_alert(message: str, parse_mode: str = "HTML") -> bool:
    cfg = _get_config()
    if not cfg["token"] or not cfg["chat_id"]:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{cfg['token']}/sendMessage",
            json={"chat_id": cfg["chat_id"], "text": message,
                  "parse_mode": parse_mode},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


def send_daily_picks(picks: list, bankroll: float, date_str: str) -> bool:
    if not picks:
        return False
    lines = [f"<b>🎯 PICKS DEL DÍA — {date_str}</b>",
             f"<b>Banco: ${bankroll:,.0f}</b>\n"]
    total_stake = 0
    for p in picks:
        stake = bankroll * p.get("kelly_frac", 0.02) * 0.25
        total_stake += stake
        sport = p.get("sport", p.get("label", "")[:3])
        home  = p.get("home", "")
        away  = p.get("away", "")
        odds  = p.get("odds_offered", 0)
        prob  = p.get("model_p", 0)
        edge  = p.get("edge", 0)
        pick  = p.get("pick_team", p.get("label", ""))
        lines += [
            f"{'🔥' if edge > 0.07 else '💡'} <b>{sport}</b> — {home} vs {away}",
            f"Pick: <b>{pick}</b> @{odds:.2f}",
            f"Prob modelo: {prob:.0%} | Edge: {edge:+.1%}",
            f"Stake sugerido: ${stake:.0f}\n",
        ]
    lines.append(f"📊 <b>{len(picks)} picks | Stake total: ${total_stake:.0f}</b>")
    return send_alert("\n".join(lines))


def send_steam_alert(alert: dict) -> bool:
    home  = alert.get("home", "")
    away  = alert.get("away", "")
    sport = alert.get("sport", "")
    sharp = alert.get("sharp_side", "?").upper()
    steam = alert.get("steam", False)
    prob  = alert.get("model_p", 0)
    odds  = alert.get("odds", 0)
    edge  = alert.get("edge", 0)
    title = "🚨 <b>STEAM + VALUE</b>" if steam else "💡 <b>VALUE BET</b>"
    msg = (f"{title}\n"
           f"{sport}: {home} vs {away}\n"
           f"Sharp side: <b>{sharp}</b>\n"
           f"Modelo: {prob:.0%} @{odds:.2f} | Edge: {edge:+.1%}")
    return send_alert(msg)


def test_connection() -> bool:
    return send_alert("🤖 Sistema de pronósticos deportivos conectado. ¡Listo para enviarte picks!")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        setup_telegram(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python alertas.py TOKEN CHAT_ID")
        print(is_configured() and "Telegram ya configurado." or "Telegram NO configurado.")
