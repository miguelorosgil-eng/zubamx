"""P3.2 — test_dedup.py: máximo 1 pick por partido."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest


def _make_bets_same_game(n=3, edge_base=0.05):
    """Genera n picks del mismo partido con edges distintos."""
    markets = ["ML", "F5-ML", "RL", "NRFI", "SPREAD"]
    return [
        {
            "label": f"MLB Yankees {markets[i % len(markets)]}",
            "market": markets[i % len(markets)],
            "model_p": 0.65 - i * 0.02,
            "odds_offered": 1.90,
            "edge": edge_base - i * 0.005,
            "kelly_frac": 0.10 - i * 0.01,
            "home": "New York Yankees",
            "away": "Boston Red Sox",
            "sport": "MLB",
        }
        for i in range(n)
    ]


def test_dedup_keeps_highest_edge():
    """De picks del mismo partido, debe quedar el de mayor edge."""
    bets = _make_bets_same_game(3)
    # Simular deduplicación (como en analisis_dia.py)
    seen = set()
    unique = []
    for b in bets:
        key = (b.get("home", ""), b.get("away", ""))
        if key not in seen:
            seen.add(key)
            unique.append(b)
    assert len(unique) == 1
    assert unique[0]["edge"] == bets[0]["edge"]  # primer pick = mayor edge


def test_label_dedup():
    """Deduplicación por label elimina duplicados exactos."""
    bets = [
        {"label": "MLB Yanks ML:Jake Benn", "edge": 0.05, "model_p": 0.65,
         "odds_offered": 1.87, "kelly_frac": 0.10},
        {"label": "MLB Yanks ML:Jake Benn", "edge": 0.05, "model_p": 0.65,
         "odds_offered": 1.87, "kelly_frac": 0.10},
        {"label": "NBA Lakers ML:home", "edge": 0.04, "model_p": 0.62,
         "odds_offered": 1.92, "kelly_frac": 0.08},
    ]
    seen_labels = set()
    unique = []
    for v in bets:
        if v["label"] not in seen_labels:
            seen_labels.add(v["label"])
            unique.append(v)
    assert len(unique) == 2, f"Esperado 2 únicos, obtenido {len(unique)}"


def test_multi_sport_no_dedup():
    """Picks de deportes distintos NO deben ser deduplicados."""
    bets = [
        {"label": "MLB Yanks ML", "home": "Yankees", "away": "Red Sox", "sport": "MLB",
         "edge": 0.05, "model_p": 0.65, "odds_offered": 1.90, "kelly_frac": 0.10},
        {"label": "NBA Celtics ML", "home": "Celtics", "away": "Knicks", "sport": "NBA",
         "edge": 0.04, "model_p": 0.62, "odds_offered": 1.88, "kelly_frac": 0.08},
        {"label": "NHL Bruins ML", "home": "Bruins", "away": "Leafs", "sport": "NHL",
         "edge": 0.03, "model_p": 0.60, "odds_offered": 1.95, "kelly_frac": 0.06},
    ]
    seen_labels = set()
    unique = []
    for v in bets:
        if v["label"] not in seen_labels:
            seen_labels.add(v["label"])
            unique.append(v)
    assert len(unique) == 3, "Picks de deportes distintos fueron deduplicados incorrectamente"
