"""P3.2 — test_distribuciones.py: Poisson/Skellam/Normal devuelven probs válidas."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import numpy as np


def test_poisson_probs_in_range():
    from mercados import prob_over_under
    for mu_h, mu_a, line in [(4.5, 4.0, 8.5), (2.0, 1.5, 5.5), (6.0, 5.0, 10.5)]:
        p_o, p_u = prob_over_under(mu_h, mu_a, line, "mlb")
        assert 0 <= p_o <= 1, f"p_over={p_o} fuera de [0,1]"
        assert 0 <= p_u <= 1, f"p_under={p_u} fuera de [0,1]"


def test_normal_probs_in_range():
    from mercados import prob_over_under
    for mu_h, mu_a, line in [(113, 109, 224.5), (100, 100, 200.5), (120, 115, 230.5)]:
        p_o, p_u = prob_over_under(mu_h, mu_a, line, "nba", sigma_total=18)
        assert 0 <= p_o <= 1
        assert 0 <= p_u <= 1


def test_skellam_spread_in_range():
    from mercados import prob_spread
    for mu_h, mu_a, line in [(4.5, 4.0, -1.5), (2.5, 2.0, -0.5), (6.0, 3.0, -2.5)]:
        ph, pa = prob_spread(mu_h, mu_a, line, "mlb")
        assert 0 <= ph <= 1, f"p_home_cover={ph}"
        assert 0 <= pa <= 1, f"p_away_cover={pa}"


def test_team_total_in_range():
    from mercados import prob_team_total
    for mu, line in [(4.5, 4.0), (2.0, 1.5), (5.5, 5.0)]:
        p_o, p_u = prob_team_total(mu, line, "mlb")
        assert 0 <= p_o <= 1
        assert 0 <= p_u <= 1
        assert abs(p_o + p_u - 1.0) < 1e-6


def test_btts_in_range():
    from mercados import prob_btts
    for mu_h, mu_a in [(1.5, 1.2), (0.5, 0.3), (3.0, 2.5)]:
        p_yes, p_no = prob_btts(mu_h, mu_a)
        assert 0 <= p_yes <= 1
        assert 0 <= p_no <= 1
        assert abs(p_yes + p_no - 1.0) < 1e-6


def test_nrfi_extreme_eras():
    """ERAs extremas (0.0 o 15.0) no deben producir NaN o valores fuera de rango."""
    from mercados import prob_nrfi
    for era_h, era_a in [(0.01, 0.01), (15.0, 15.0), (0.0, 5.0)]:
        result = prob_nrfi(era_h, era_a)
        if result[0] is None:
            continue
        p_nrfi, p_yrfi = result
        assert not np.isnan(p_nrfi), f"NaN con era_h={era_h}, era_a={era_a}"
        assert 0 <= p_nrfi <= 1


def test_f5_expected_scores():
    """F5 debe ser ~55% del total esperado (no exactamente 5/9)."""
    from mercados_alternativos import prob_f5
    mu_h, mu_a = 4.5, 4.0
    f5_h, f5_a = prob_f5(mu_h, mu_a)
    # 5/9 ≈ 0.556
    assert 0.50 <= f5_h / mu_h <= 0.62, f"F5 ratio home: {f5_h/mu_h:.3f}"
    assert 0.50 <= f5_a / mu_a <= 0.62, f"F5 ratio away: {f5_a/mu_a:.3f}"
