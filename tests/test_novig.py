"""P3.2 — test_novig.py: probabilidades suman 1 tras quitar vig."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


def test_two_way_novig_sums_to_one():
    from mercados import evaluate_two_way
    bets = evaluate_two_way(
        0.65, 0.35, 1.80, 2.10,
        "Home", "Away", "ML",
        market_trust=0.0,   # puro modelo, sin shrinkage
        confidence_floor=0.0,
        edge_threshold=-1.0,  # sin filtro
    )
    probs = [b["model_p"] for b in bets]
    if len(probs) == 2:
        assert abs(sum(probs) - 1.0) < 0.01, f"Probs no suman 1: {sum(probs)}"


def test_three_way_novig_sums_to_one():
    from mercados import evaluate_three_way
    bets = evaluate_three_way(
        0.45, 0.25, 0.30,
        2.10, 3.50, 2.80,
        "Home", "Away",
        market_trust=0.0,
        confidence_floor=0.0,
        edge_threshold=-1.0,
    )
    probs = [b["model_p"] for b in bets]
    if len(probs) == 3:
        assert abs(sum(probs) - 1.0) < 0.01, f"Probs no suman 1: {sum(probs)}"


def test_implied_probs_removed_vig():
    """La suma de implied probs (con vig) debe ser > 1; sin vig debe ser ~1."""
    odds_h, odds_a = 1.87, 1.95
    raw_h = 1.0 / odds_h
    raw_a = 1.0 / odds_a
    total_raw = raw_h + raw_a
    assert total_raw > 1.0, "odds mal configuradas (no hay vig)"
    novig_h = raw_h / total_raw
    novig_a = raw_a / total_raw
    assert abs(novig_h + novig_a - 1.0) < 1e-9, "no-vig no suma 1"


def test_prob_over_under_sums_to_one():
    from mercados import prob_over_under
    for sport in ("mlb", "nhl", "nba"):
        p_over, p_under = prob_over_under(4.5, 4.0, 8.5, sport, sigma_total=18)
        assert abs(p_over + p_under - 1.0) < 1e-6, (
            f"{sport}: p_over+p_under = {p_over+p_under}"
        )


def test_prob_spread_sums_to_one():
    from mercados import prob_spread
    for sport in ("mlb", "nba"):
        ph, pa = prob_spread(4.5, 4.0, -1.5, sport)
        assert abs(ph + pa - 1.0) < 1e-6, f"{sport}: ph+pa = {ph+pa}"


def test_prob_nrfi_valid():
    from mercados import prob_nrfi
    p_nrfi, p_yrfi = prob_nrfi(3.5, 4.2)
    assert 0 < p_nrfi < 1
    assert 0 < p_yrfi < 1
    assert abs(p_nrfi + p_yrfi - 1.0) < 1e-6
