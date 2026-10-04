"""Unit tests for Phase 6 models."""
import pandas as pd
import pytest

from src.models import clustering, logistic_model as lm


def test_time_split_is_disjoint_and_ordered():
    assert not set(lm.TRAIN) & set(lm.VALID)
    assert not set(lm.VALID) & set(lm.TEST)
    assert max(lm.TRAIN) < min(lm.VALID) < min(lm.TEST)


def test_model_a_uses_no_in_match_information():
    from src.schema import IN_MATCH_COLUMNS

    used = set(lm.NUMERIC + lm.CATEGORICAL + lm.BINARY)
    in_match = set(IN_MATCH_COLUMNS) | {"home_goals", "away_goals", "result", "home_points", "away_points"}
    assert not used & in_match


def test_metrics_on_perfect_predictions():
    import numpy as np

    y = np.array([0, 1, 1, 0])
    m = lm.metrics(y, np.array([0.1, 0.9, 0.8, 0.2]))
    assert m["accuracy"] == 1.0 and m["roc_auc"] == 1.0 and m["tp"] == 2


def test_pick_k_prefers_stable_high_silhouette():
    scores = pd.DataFrame({"k": [2, 3, 4], "silhouette": [0.30, 0.40, 0.45],
                           "stability_ari": [0.9, 0.85, 0.5], "smallest_cluster": [10, 6, 6]})
    assert clustering.pick_k(scores) == 3
    # No stable solution: fall back to the best silhouette overall.
    scores["stability_ari"] = 0.5
    assert clustering.pick_k(scores) == 4
