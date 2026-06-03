"""
Semillas ELO basadas en el Ranking FIFA (mayo 2026).
Se usan para inicializar el motor cuando no hay historial de partidos
de una selección (ej: equipos no europeos en WC 2026).

Puntos FIFA → escala ELO interna (base 1500):
    elo = 1500 + (fifa_pts - 1500) * 0.6
Ajuste empírico para que el spread sea comparable al ELO de ligas.
"""

# Puntos FIFA aproximados (ranking mayo 2026) para los 48 clasificados al WC 2026
# Fuente: evolución del ranking FIFA + clasificatorios 2025-2026
FIFA_POINTS = {
    # Sudamérica (CONMEBOL)
    "Argentina":          1855,
    "Brazil":             1790,
    "Colombia":           1720,
    "Uruguay":            1730,
    "Ecuador":            1600,
    "Venezuela":          1490,
    "Paraguay":           1500,
    "Bolivia":            1430,
    # Europa (UEFA) — 16 equipos
    "France":             1820,
    "Spain":              1815,
    "England":            1800,
    "Portugal":           1785,
    "Netherlands":        1770,
    "Germany":            1765,
    "Italy":              1750,
    "Croatia":            1745,
    "Switzerland":        1590,
    "Denmark":            1585,
    "Austria":            1580,
    "Turkey":             1575,
    "Poland":             1570,
    "Czechia":            1565,
    "Serbia":             1595,
    "Hungary":            1555,
    "Scotland":           1545,
    "Ukraine":            1540,
    "Slovakia":           1530,
    # CONCACAF
    "United States":      1690,
    "Mexico":             1700,
    "Canada":             1610,
    "Costa Rica":         1460,
    "Honduras":           1440,
    "Panama":             1420,
    "Jamaica":            1400,
    "Haiti":              1380,
    "El Salvador":        1360,
    "Trinidad and Tobago":1370,
    "Curaçao":            1350,
    # África (CAF)
    "Morocco":            1680,
    "Senegal":            1665,
    "Nigeria":            1535,
    "Cameroon":           1520,
    "Côte d'Ivoire":      1515,
    "Egypt":              1510,
    "Algeria":            1505,
    "South Africa":       1450,
    "DR Congo":           1460,
    "Mali":               1455,
    "Tunisia":            1470,
    "Guinea":             1440,
    # Asia (AFC)
    "Japan":              1660,
    "South Korea":        1640,
    "Australia":          1620,
    "Iran":               1475,
    "Saudi Arabia":       1480,
    "Qatar":              1450,
    "Iraq":               1465,
    "Uzbekistan":         1440,
    "Indonesia":          1370,
    "Thailand":           1380,
    # Oceanía
    "New Zealand":        1450,
    # Otros / comodines
    "Bosnia-Herzegovina": 1510,
    "Luxembourg":         1480,
    "Greece":             1520,
    "Albania":            1500,
    "Slovenia":           1490,
    "Romania":            1510,
    "Finland":            1470,
    "Norway":             1560,
    "Sweden":             1550,
    "Israel":             1490,
    "Kazakhstan":         1430,
    "Wales":              1520,
    "Northern Ireland":   1440,
    "Ireland":            1460,
    "Georgia":            1470,
    "Kosovo":             1440,
    "North Macedonia":    1430,
    "Iceland":            1490,
    "Montenegro":         1450,
    "Lithuania":          1400,
    "Latvia":             1410,
    "Estonia":            1380,
    "Belarus":            1400,
    "Bulgaria":           1420,
    "Cyprus":             1380,
    "Armenia":            1440,
    "Azerbaijan":         1390,
    "Moldova":            1350,
    "Malta":              1320,
    "Andorra":            1280,
    "San Marino":         1200,
    "Faroe Islands":      1340,
    "Liechtenstein":      1230,
    "Gibraltar":          1220,
    "Cuba":               1360,
    "Guadalupe":          1370,
    "Guatemala":          1390,
    "Nicaragua":          1330,
}


def get_elo_seeds(base=1500, scale=0.6):
    """Convierte puntos FIFA a escala ELO interna."""
    seeds = {}
    for team, pts in FIFA_POINTS.items():
        seeds[team] = base + (pts - base) * scale
    return seeds


def seed_elo_ratings(elo_rating_obj):
    """Inicializa un objeto EloRating con los seeds FIFA."""
    seeds = get_elo_seeds()
    for team, elo in seeds.items():
        elo_rating_obj.ratings[team] = elo
    return elo_rating_obj
