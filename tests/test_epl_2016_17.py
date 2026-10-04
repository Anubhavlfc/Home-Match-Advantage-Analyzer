"""Integration test on the real EPL 2016/17 data.

Runs the full pipeline, which downloads raw files if they are not already in
``data/raw``. Skipped when no network source is reachable.
"""
import pandas as pd
import pytest

from src.data.extract import ExtractError
from src.pipeline import run_domestic_season


@pytest.fixture(scope="module")
def epl_1617() -> pd.DataFrame:
    try:
        return run_domestic_season("EPL", "2016/17")
    except ExtractError as err:  # pragma: no cover - depends on network
        pytest.skip(f"raw data unavailable: {err}")


def test_shape_and_identity(epl_1617):
    assert len(epl_1617) == 380
    assert epl_1617["match_id"].is_unique
    assert epl_1617["home_team"].nunique() == 20


def test_known_headline_numbers(epl_1617):
    # 1,064 goals in 2016/17 (published season total).
    assert int(epl_1617["home_goals"].sum() + epl_1617["away_goals"].sum()) == 1064
    champions = (
        pd.concat(
            [
                epl_1617.groupby("home_team")["home_points"].sum(),
                epl_1617.groupby("away_team")["away_points"].sum(),
            ]
        )
        .groupby(level=0)
        .sum()
        .idxmax()
    )
    assert champions == "Chelsea"


def test_known_match(epl_1617):
    # Opening weekend: Arsenal 3-4 Liverpool, 14 Aug 2016.
    m = epl_1617[(epl_1617["home_team"] == "Arsenal") & (epl_1617["away_team"] == "Liverpool")].iloc[0]
    assert (m["date"], m["home_goals"], m["away_goals"], m["result"]) == (pd.Timestamp("2016-08-14"), 3, 4, "A")


def test_no_fabricated_values(epl_1617):
    for col in ("attendance", "home_penalties", "home_possession", "stadium_capacity"):
        assert epl_1617[col].isna().all(), f"{col} should be missing, not filled"
