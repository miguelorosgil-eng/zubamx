"""
Ajuste de totales MLB por condiciones climáticas.
Solo aplica a estadios ABIERTOS — los con techo se omiten.
Fuente: Open-Meteo API (100% gratis, sin API key).

Factores aplicados al total esperado:
  Viento a favor (>20 km/h outward): +0.4 carreras
  Viento en contra (>20 km/h inward): -0.5 carreras
  Temperatura < 10°C: -0.4 carreras
  Temperatura > 32°C: -0.2 carreras (calor extremo = pitchers cansados)
  Lluvia prevista: partido puede posponerse → marcar partido como "rain risk"
"""
import requests
import math

# Estadios con coordenadas y si tienen techo
# True = estadio abierto (afecta el weather), False = techo/domo
MLB_STADIUMS = {
    "Arizona Diamondbacks":   (33.4453, -112.0668, False),   # Chase Field (techo retráctil)
    "Atlanta Braves":         (33.8908,  -84.4678, True),    # Truist Park
    "Baltimore Orioles":      (39.2839,  -76.6218, True),    # Camden Yards
    "Boston Red Sox":         (42.3467,  -71.0972, True),    # Fenway Park
    "Chicago Cubs":           (41.9484,  -87.6553, True),    # Wrigley Field
    "Chicago White Sox":      (41.8300,  -87.6338, True),    # Guaranteed Rate Field
    "Cincinnati Reds":        (39.0975,  -84.5064, True),    # Great American Ball Park
    "Cleveland Guardians":    (41.4954,  -81.6854, True),    # Progressive Field
    "Colorado Rockies":       (39.7559, -104.9942, True),    # Coors Field
    "Detroit Tigers":         (42.3390,  -83.0485, True),    # Comerica Park
    "Houston Astros":         (29.7573,  -95.3555, False),   # Minute Maid (techo)
    "Kansas City Royals":     (39.0517,  -94.4803, True),    # Kauffman Stadium
    "Los Angeles Angels":     (33.8003, -117.8827, True),    # Angel Stadium
    "Los Angeles Dodgers":    (34.0739, -118.2400, True),    # Dodger Stadium
    "Miami Marlins":          (25.7781,  -80.2198, False),   # loanDepot Park (techo)
    "Milwaukee Brewers":      (43.0280,  -87.9712, False),   # American Family Field (techo)
    "Minnesota Twins":        (44.9817,  -93.2777, False),   # Target Field (abierto, frío)
    "New York Mets":          (40.7571,  -73.8458, True),    # Citi Field
    "New York Yankees":       (40.8296,  -73.9262, True),    # Yankee Stadium
    "Athletics":              (37.7516, -122.2005, True),    # Sutter Health Park
    "Philadelphia Phillies":  (39.9061,  -75.1665, True),    # Citizens Bank Park
    "Pittsburgh Pirates":     (40.4469,  -80.0057, True),    # PNC Park
    "San Diego Padres":       (32.7073, -117.1566, True),    # Petco Park
    "San Francisco Giants":   (37.7786, -122.3893, True),    # Oracle Park
    "Seattle Mariners":       (47.5914, -122.3325, False),   # T-Mobile Park (techo)
    "St. Louis Cardinals":    (38.6226,  -90.1928, True),    # Busch Stadium
    "Tampa Bay Rays":         (27.7683,  -82.6534, False),   # Tropicana Field (techo)
    "Texas Rangers":          (32.7473,  -97.0822, False),   # Globe Life Field (techo)
    "Toronto Blue Jays":      (43.6414,  -79.3894, False),   # Rogers Centre (techo)
    "Washington Nationals":   (38.8730,  -77.0074, True),    # Nationals Park
    "Minnesota Twins":        (44.9817,  -93.2777, True),    # Target Field (abierto)
}


def _fetch_weather(lat: float, lon: float) -> dict:
    """Llama Open-Meteo para condiciones actuales + próximas 3h."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,windspeed_10m,winddirection_10m",
        "forecast_days": 1,
        "timezone": "auto",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        hourly = data["hourly"]
        # Tomar hora 19-20 local (hora típica de juego nocturno)
        idx = 19  # índice aproximado para las 7pm
        return {
            "temp_c": hourly["temperature_2m"][idx],
            "precip_pct": hourly["precipitation_probability"][idx],
            "wind_kmh": hourly["windspeed_10m"][idx],
            "wind_dir": hourly["winddirection_10m"][idx],
        }
    except Exception:
        return {}


def _wind_direction_label(degrees: float) -> str:
    dirs = ["N","NE","E","SE","S","SW","W","NW"]
    return dirs[int((degrees + 22.5) / 45) % 8]


def get_weather_adjustment(home_team: str) -> dict:
    """
    Devuelve dict con:
      total_adj: carreras a sumar/restar al total esperado
      rain_risk: True si hay >50% prob de lluvia
      summary: string descriptivo
    """
    info = MLB_STADIUMS.get(home_team)
    if not info:
        return {"total_adj": 0.0, "rain_risk": False, "summary": ""}
    lat, lon, is_open = info
    if not is_open:
        return {"total_adj": 0.0, "rain_risk": False, "summary": "🏟️ Estadio con techo"}

    w = _fetch_weather(lat, lon)
    if not w:
        return {"total_adj": 0.0, "rain_risk": False, "summary": ""}

    adj = 0.0
    notes = []

    # Temperatura
    temp = w.get("temp_c", 20)
    if temp < 10:
        adj -= 0.4
        notes.append(f"❄️ {temp:.0f}°C (-0.4)")
    elif temp > 32:
        adj -= 0.2
        notes.append(f"🌡️ {temp:.0f}°C (-0.2)")
    else:
        notes.append(f"{temp:.0f}°C")

    # Viento
    wind = w.get("wind_kmh", 0)
    wind_dir = w.get("wind_dir", 0)
    if wind > 20:
        # Viento del SW-SE → favorece bateo (outward en la mayoría de parques)
        # Viento del NE-NW → viento en contra (inward)
        label = _wind_direction_label(wind_dir)
        if label in ("SW", "S", "SE"):
            adj += 0.4
            notes.append(f"💨 {wind:.0f}km/h {label} (+0.4 bateadores)")
        elif label in ("NW", "N", "NE"):
            adj -= 0.5
            notes.append(f"💨 {wind:.0f}km/h {label} (-0.5 pitchers)")
        else:
            notes.append(f"💨 {wind:.0f}km/h {label}")

    # Lluvia
    rain = w.get("precip_pct", 0)
    rain_risk = rain > 50
    if rain_risk:
        notes.append(f"🌧️ Lluvia {rain:.0f}% (riesgo suspensión)")

    return {
        "total_adj": round(adj, 2),
        "rain_risk": rain_risk,
        "summary": " | ".join(notes),
    }


if __name__ == "__main__":
    for team in ["Chicago Cubs", "Seattle Mariners", "Houston Astros"]:
        w = get_weather_adjustment(team)
        print(f"{team}: adj={w['total_adj']:+.1f}  {w['summary']}")
