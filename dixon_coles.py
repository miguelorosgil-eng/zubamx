"""
Dixon-Coles Poisson Model — Capa base del motor predictivo de fútbol.
Modela goles esperados por equipo con corrección para resultados de bajo
marcador (0-0, 1-0, 0-1, 1-1) que un Poisson puro subestima.

Ref: Dixon & Coles (1997), "Modelling Association Football Scores and
Inefficiencies in the Football Betting Market".
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson


def _tau(x, y, lambda_x, mu_y, rho):
    """Corrección Dixon-Coles para marcadores bajos."""
    if x == 0 and y == 0:
        return 1 - lambda_x * mu_y * rho
    elif x == 0 and y == 1:
        return 1 + lambda_x * rho
    elif x == 1 and y == 0:
        return 1 + mu_y * rho
    elif x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _time_weights(dates, xi=0.0019):
    """Ponderación por recencia: partidos viejos pesan menos.
    xi=0.0019 ~ vida media de ~1 año (recomendado por la literatura)."""
    last = dates.max()
    diff_days = (last - dates).dt.days
    return np.exp(-xi * diff_days)


class DixonColes:
    def __init__(self, xi=0.0019):
        self.xi = xi
        self.params = None
        self.teams = None

    def _neg_log_likelihood(self, params, hg, ag, hi, ai, weights):
        """Verosimilitud negativa VECTORIZADA (sin loops Python)."""
        n = len(self.teams)
        attack = params[:n]
        defence = params[n:2 * n]
        home_adv = params[2 * n]
        rho = params[2 * n + 1]

        lx = np.exp(attack[hi] + defence[ai] + home_adv)
        my = np.exp(attack[ai] + defence[hi])

        # Corrección tau de Dixon-Coles, vectorizada sobre las 4 celdas bajas
        tau = np.ones_like(lx)
        m00 = (hg == 0) & (ag == 0)
        m01 = (hg == 0) & (ag == 1)
        m10 = (hg == 1) & (ag == 0)
        m11 = (hg == 1) & (ag == 1)
        tau[m00] = 1 - lx[m00] * my[m00] * rho
        tau[m01] = 1 + lx[m01] * rho
        tau[m10] = 1 + my[m10] * rho
        tau[m11] = 1 - rho

        p = tau * poisson.pmf(hg, lx) * poisson.pmf(ag, my)
        ll = np.sum(weights * np.log(np.maximum(p, 1e-10)))
        return -ll

    def fit(self, df):
        """df columns: home, away, hg (home goals), ag (away goals), date"""
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        self.teams = sorted(set(df['home']) | set(df['away']))
        n = len(self.teams)
        weights = _time_weights(df['date'], self.xi).values

        # Precomputar índices de equipo y arrays de goles (vectorización)
        idx = {t: k for k, t in enumerate(self.teams)}
        hi = df['home'].map(idx).to_numpy()
        ai = df['away'].map(idx).to_numpy()
        hg = df['hg'].to_numpy()
        ag = df['ag'].to_numpy()

        x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25], [-0.1]])
        cons = [{'type': 'eq', 'fun': lambda p: np.sum(p[:n])}]

        res = minimize(
            self._neg_log_likelihood, x0,
            args=(hg, ag, hi, ai, weights),
            constraints=cons,
            method='SLSQP',
            options={'maxiter': 200, 'ftol': 1e-6}
        )
        self.params = res.x
        return self

    def _rates(self, home, away):
        n = len(self.teams)
        attack = dict(zip(self.teams, self.params[:n]))
        defence = dict(zip(self.teams, self.params[n:2 * n]))
        home_adv = self.params[2 * n]
        # Fallback para equipos fuera del training: usar media de todos los conocidos
        avg_att = float(np.mean(list(attack.values()))) if attack else 0.0
        avg_def = float(np.mean(list(defence.values()))) if defence else 0.0
        att_h = attack.get(home, avg_att + self._fifa_offset(home))
        def_h = defence.get(home, avg_def - self._fifa_offset(home))
        att_a = attack.get(away, avg_att + self._fifa_offset(away))
        def_a = defence.get(away, avg_def - self._fifa_offset(away))
        lx = np.exp(np.clip(att_h + def_a + home_adv, -3, 3))
        my = np.exp(np.clip(att_a + def_h, -3, 3))
        return lx, my

    def set_fifa_seeds(self, fifa_elo_seeds):
        """Almacena seeds FIFA para ajustar parámetros de equipos desconocidos."""
        # Convierte ELO FIFA (1300-1900) a offset de ataque DC (~-0.5 a 0.5)
        self._fifa_elo = fifa_elo_seeds

    def _fifa_offset(self, team):
        """Offset de ataque/defensa basado en ELO FIFA vs promedio (1500)."""
        if not hasattr(self, '_fifa_elo') or self._fifa_elo is None:
            return 0.0
        elo = self._fifa_elo.get(team, 1500)
        return (elo - 1500) / 2000.0  # escala: 1900 → +0.2, 1200 → -0.15

    def predict_matrix(self, home, away, max_goals=10):
        """Matriz de probabilidad conjunta de marcadores."""
        lx, my = self._rates(home, away)
        rho = self.params[-1]
        m = np.outer(poisson.pmf(range(max_goals + 1), lx),
                     poisson.pmf(range(max_goals + 1), my))
        # aplicar corrección tau a las 4 celdas bajas
        for x in range(2):
            for y in range(2):
                m[x, y] *= _tau(x, y, lx, my, rho)
        return m / m.sum()

    def predict_proba(self, home, away):
        """Devuelve P(home win), P(draw), P(away win) + features útiles."""
        m = self.predict_matrix(home, away)
        p_home = np.tril(m, -1).sum()
        p_draw = np.trace(m)
        p_away = np.triu(m, 1).sum()
        # over/under 2.5 y BTTS
        idx = np.indices(m.shape)
        total = idx[0] + idx[1]
        p_over25 = m[total >= 3].sum()
        btts = m[1:, 1:].sum()
        lx, my = self._rates(home, away)
        return {
            'p_home': p_home, 'p_draw': p_draw, 'p_away': p_away,
            'p_over25': p_over25, 'p_btts': btts,
            'xg_home': lx, 'xg_away': my
        }
