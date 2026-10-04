"""Unit tests for Phase 5 statistical helpers."""
import numpy as np
import pandas as pd
import pytest

from src.analysis import stats


def test_cohens_h_zero_for_equal_proportions():
    assert stats.cohens_h(0.4, 0.4) == 0
    assert stats.cohens_h(0.5, 0.4) > 0


def test_cramers_v_bounds():
    independent = np.array([[50, 50], [50, 50]])
    perfect = np.array([[100, 0], [0, 100]])
    assert stats.cramers_v(independent) == pytest.approx(0.0)
    assert stats.cramers_v(perfect) == pytest.approx(1.0)


def test_registry_holm_only_on_primary():
    reg = stats.Registry()
    for i, p in enumerate([0.01, 0.04, 0.03]):
        reg.add(f"T{i}", "Q", "h", "m", "s", 10, "z", 1.0, p, 0.0, 0.0, 0.0, primary=i < 2)
    t = reg.frame()
    assert t.loc[0, "p_holm"] == pytest.approx(0.02)
    assert t.loc[1, "p_holm"] == pytest.approx(0.04)
    assert np.isnan(t.loc[2, "p_holm"])


def test_lincom_matches_single_coefficient():
    rng = np.random.default_rng(1)
    d = pd.DataFrame({"x": rng.normal(size=200)})
    d["y"] = 1.0 + 2.0 * d["x"] + rng.normal(size=200)
    res = stats.smf.ols("y ~ x", d).fit()
    est, lo, hi, p = stats._lincom(res, {"x": 1.0})
    assert est == pytest.approx(res.params["x"])
    assert lo < est < hi and p < 1e-10
