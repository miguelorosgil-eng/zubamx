"""
Tracking de movimiento de línea (line movement).
Guarda la línea de apertura y detecta movimiento sharp vs público.
"""

import json
import os

CACHE_DIR = "_cache"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_path(sport: str, date_str: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"opening_lines_{sport}_{date_str}.json")


def _event_key(event: dict) -> str:
    return f"{event['home']}|{event['away']}"


def _implied_prob(odds: float) -> float:
    """Convierte odds decimales a probabilidad implícita."""
    if odds <= 0:
        return 0.0
    return 1.0 / odds


# ---------------------------------------------------------------------------
# 1. Guardar líneas de apertura
# ---------------------------------------------------------------------------

def save_opening_lines(sport: str, events: list, date_str: str):
    """
    Guarda en _cache/opening_lines_{sport}_{date}.json los eventos con sus odds.
    Solo guarda si NO existe ya el archivo (primera corrida del día = opening line).
    events: lista de dicts con {home, away, odds: {home, away, draw?}}
    """
    path = _cache_path(sport, date_str)
    if os.path.exists(path):
        return  # Ya hay opening line guardada, no sobreescribir

    data = {}
    for ev in events:
        key = _event_key(ev)
        data[key] = {
            "home": ev["home"],
            "away": ev["away"],
            "odds": ev.get("odds", {}),
        }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# 2. Obtener movimiento de línea
# ---------------------------------------------------------------------------

def get_line_movement(sport: str, current_events: list, date_str: str) -> list:
    """
    Carga opening lines del día y compara con current_events.
    Devuelve lista de dicts con análisis de movimiento por evento.
    Si no hay opening lines guardadas: devuelve lista vacía.
    """
    path = _cache_path(sport, date_str)
    if not os.path.exists(path):
        return []

    with open(path) as f:
        opening = json.load(f)

    results = []
    for ev in current_events:
        key = _event_key(ev)
        if key not in opening:
            continue

        open_data = opening[key]
        open_odds = open_data.get("odds", {})
        curr_odds = ev.get("odds", {})

        open_home = float(open_odds.get("home") or 0)
        open_away = float(open_odds.get("away") or 0)
        curr_home = float(curr_odds.get("home") or 0)
        curr_away = float(curr_odds.get("away") or 0)

        if not all([open_home, open_away, curr_home, curr_away]):
            continue

        move_home = curr_home - open_home  # negativo = línea bajó = más caro home
        move_away = curr_away - open_away

        sharp_info = estimate_sharp_side(open_home, open_away, curr_home, curr_away)
        sharp_side = sharp_info["sharp_side"]
        confidence = sharp_info["confidence"]

        # Steam move: movimiento >0.10 en odds decimales = acción sharp rápida
        steam_move = abs(move_home) > 0.10 or abs(move_away) > 0.10

        # Descripción
        if sharp_side and steam_move:
            direction = "+" if (move_home if sharp_side == "home" else move_away) > 0 else ""
            move_val = move_home if sharp_side == "home" else move_away
            sharp_signal = f"Steam move {sharp_side.upper()} {direction}{move_val:+.2f} (conf: {confidence})"
        elif sharp_side:
            move_val = move_home if sharp_side == "home" else move_away
            sharp_signal = f"Line move {sharp_side.upper()} {move_val:+.2f} (conf: {confidence})"
        else:
            sharp_signal = "Sin señal sharp clara"

        results.append({
            "home": ev["home"],
            "away": ev["away"],
            "open_home": open_home,
            "open_away": open_away,
            "curr_home": curr_home,
            "curr_away": curr_away,
            "move_home": round(move_home, 4),
            "move_away": round(move_away, 4),
            "sharp_side": sharp_side,
            "sharp_signal": sharp_signal,
            "steam_move": steam_move,
        })

    return results


# ---------------------------------------------------------------------------
# 3. Wrapper conveniente
# ---------------------------------------------------------------------------

def get_consensus_sharp_side(home: str, away: str, sport: str, date_str: str) -> str | None:
    """
    Devuelve 'home'/'away'/None basado en line movement para un partido específico.
    """
    path = _cache_path(sport, date_str)
    if not os.path.exists(path):
        return None

    with open(path) as f:
        opening = json.load(f)

    key = f"{home}|{away}"
    if key not in opening:
        return None

    # Necesitamos current odds — sin ellas no podemos calcular movimiento
    # Este wrapper asume que las opening lines ya están cargadas y
    # el llamante provee los datos actuales via get_line_movement.
    # Aquí retornamos None si no hay datos actuales disponibles.
    return None


def get_consensus_sharp_side_from_events(
    home: str, away: str, sport: str, current_events: list, date_str: str
) -> str | None:
    """
    Versión completa: busca el partido en current_events y devuelve el sharp side.
    """
    movements = get_line_movement(sport, current_events, date_str)
    for mv in movements:
        if mv["home"] == home and mv["away"] == away:
            return mv["sharp_side"]
    return None


# ---------------------------------------------------------------------------
# 4. Formato resumen
# ---------------------------------------------------------------------------

def format_movement_summary(movement: dict) -> str:
    """
    Retorna string para mostrar el movimiento de línea de un evento.
    Ejemplo: "📈 Línea movió HOME @1.85→1.72 (sharp: HOME)"
    """
    home = movement["home"]
    away = movement["away"]
    open_h = movement["open_home"]
    curr_h = movement["curr_home"]
    open_a = movement["open_away"]
    curr_a = movement["curr_away"]
    sharp = movement.get("sharp_side")
    steam = movement.get("steam_move", False)

    icon = "🔥" if steam else "📈"
    sharp_str = f"sharp: {sharp.upper()}" if sharp else "sin señal"

    lines = [
        f"{icon} {home} vs {away}",
        f"   HOME @{open_h:.2f}→{curr_h:.2f} | AWAY @{open_a:.2f}→{curr_a:.2f}",
        f"   ({sharp_str})",
    ]
    if steam:
        lines.append(f"   ⚡ STEAM MOVE detectado")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5. Proxy de sharp money (sin API de pago)
# ---------------------------------------------------------------------------

def estimate_sharp_side(
    open_home: float,
    open_away: float,
    curr_home: float,
    curr_away: float,
) -> dict:
    """
    Estima el lado sharp basado en movimiento de línea.

    Lógica:
    - Si odds HOME bajaron (más caro apostar home = más demanda) → sharp en HOME
    - Si odds HOME subieron → sharp en AWAY
    - Regla: movimiento >5% en implied probability = señal significativa

    Retorna: {sharp_side, confidence, reason}
    """
    if not all([open_home, open_away, curr_home, curr_away]):
        return {"sharp_side": None, "confidence": "none", "reason": "Datos incompletos"}

    # Cambio en probabilidad implícita
    open_prob_home = _implied_prob(open_home)
    curr_prob_home = _implied_prob(curr_home)
    open_prob_away = _implied_prob(open_away)
    curr_prob_away = _implied_prob(curr_away)

    delta_home = curr_prob_home - open_prob_home  # positivo = más probable home ahora
    delta_away = curr_prob_away - open_prob_away

    move_home = curr_home - open_home  # negativo = bajó odds = más demanda
    move_away = curr_away - open_away

    THRESHOLD = 0.05  # 5% en implied prob

    # Determinar lado con mayor movimiento de sharp
    if abs(delta_home) >= THRESHOLD or abs(delta_away) >= THRESHOLD:
        # La línea se movió significativamente
        if delta_home > 0 and delta_home >= abs(delta_away):
            # Home más probable ahora = sharp apostó home = odds home bajaron
            sharp_side = "home"
            pct = delta_home * 100
            confidence = "high" if pct > 10 else "medium"
            reason = f"Implied prob HOME subió {pct:.1f}% (odds {open_home:.2f}→{curr_home:.2f})"
        elif delta_away > 0 and delta_away > abs(delta_home):
            sharp_side = "away"
            pct = delta_away * 100
            confidence = "high" if pct > 10 else "medium"
            reason = f"Implied prob AWAY subió {pct:.1f}% (odds {open_away:.2f}→{curr_away:.2f})"
        else:
            # Movimiento mixto o hacia afuera en ambos (raro)
            sharp_side = None
            confidence = "low"
            reason = f"Movimiento mixto: home Δ{delta_home*100:.1f}% away Δ{delta_away*100:.1f}%"
    elif abs(move_home) > 0.05 or abs(move_away) > 0.05:
        # Movimiento en odds pero <5% en implied prob → señal débil
        if move_home < 0:
            sharp_side = "home"
            confidence = "low"
            reason = f"Odds HOME bajaron {move_home:.2f} (señal débil)"
        elif move_away < 0:
            sharp_side = "away"
            confidence = "low"
            reason = f"Odds AWAY bajaron {move_away:.2f} (señal débil)"
        else:
            sharp_side = None
            confidence = "none"
            reason = "Sin movimiento significativo"
    else:
        sharp_side = None
        confidence = "none"
        reason = "Línea estable, sin actividad sharp detectable"

    return {
        "sharp_side": sharp_side,
        "confidence": confidence,
        "reason": reason,
    }
