"""Unit tests for the EDA summary helpers."""
import numpy as np
import pandas as pd
import pytest

from src.analysis import eda


def test_wilson_interval_contains_estimate():
    lo, hi = eda.wilson(45, 100)
    assert lo < 0.45 < hi
    assert lo == pytest.approx(0.3561, abs=1e-3) and hi == pytest.approx(0.5476, abs=1e-3)


def _matches(results, strength_difference=0.0):
    pts = {"H": (3, 0), "D": (1, 1), "A": (0, 3)}
    goals = {"H": (2, 0), "D": (1, 1), "A": (0, 2)}
    df = pd.DataFrame({"result": results})
    df["home_points"] = [pts[r][0] for r in results]
    df["away_points"] = [pts[r][1] for r in results]
    df["home_goals"] = [goals[r][0] for r in results]
    df["away_goals"] = [goals[r][1] for r in results]
    df["goal_difference"] = df["home_goals"] - df["away_goals"]
    df["strength_difference"] = strength_difference
    df["home_score"] = df["result"].map({"H": 1.0, "D": 0.5, "A": 0.0})
    df["elo_expected"] = 1.0 / (1.0 + 10 ** (-df["strength_difference"] / 400.0))
    df["home_excess"] = df["home_score"] - df["elo_expected"]
    return df


def test_summary_has_no_home_excess_for_balanced_results():
    s = eda.summarise(_matches(["H", "D", "A", "H", "D", "A"]))
    assert s["home_excess"] == pytest.approx(0.0)
    assert s["points_share"] == pytest.approx(0.5)
    assert s["home_win_pct"] == pytest.approx(100 / 3)


def test_home_excess_adjusts_for_strength():
    # A much stronger home side winning every game shows little excess.
    strong = eda.summarise(_matches(["H"] * 10, strength_difference=400.0))
    equal = eda.summarise(_matches(["H"] * 10, strength_difference=0.0))
    assert strong["home_excess"] == pytest.approx(1 - 1 / 1.1)
    assert equal["home_excess"] == pytest.approx(0.5)
    assert strong["home_excess"] < equal["home_excess"]
