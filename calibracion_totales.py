"""
Calibración empírica del modelo de totales (medida sobre 372 juegos MLB,
jun-jul 2026, líneas de cierre reales).

Hallazgo: el modelo proyectaba con sigma=3.0 (sobre-confiado) y sub-proyectaba
0.70 runs. Con el sigma REAL (4.69) los picks de O/U aciertan ~50% — no hay edge
en las líneas de MLB. Esta calibración hace que el modelo sea HONESTO: casi no
genera picks en totales de MLB, que es lo correcto (mercado eficiente).

Uso: aplicar corrige_total() a mu_total antes de calcular probabilidades O/U,
y usar MLB_TOTAL_SIGMA como sigma (no 3.0).
"""

# Desviación estándar REAL del residual (total real - proyección del modelo).
# sigma=3.0 daba probabilidades tipo 75% que en realidad eran 56%.
MLB_TOTAL_SIGMA = 4.6

# El modelo sub-proyecta ~0.70 runs en promedio; se corrige el sesgo.
MLB_TOTAL_BIAS = 0.70


def corrige_total(mu_total: float) -> float:
    """Corrige el sesgo de sub-proyección del modelo de totales."""
    return mu_total + MLB_TOTAL_BIAS


def prob_total_calibrada(mu_total: float, line: float):
    """
    P(over), P(under) CALIBRADAS: sesgo corregido + sigma real.
    Devuelve probabilidades realistas (no infladas).
    """
    from scipy.stats import norm
    mu = corrige_total(mu_total)
    p_over = 1 - norm.cdf(line + 0.5, loc=mu, scale=MLB_TOTAL_SIGMA)
    p_under = norm.cdf(line - 0.5, loc=mu, scale=MLB_TOTAL_SIGMA)
    t = p_over + p_under
    return p_over / t, p_under / t
