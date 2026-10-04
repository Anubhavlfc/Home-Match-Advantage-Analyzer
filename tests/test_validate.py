import itertools

import pandas as pd
import pytest

from src.data.clean import build_match_id, derive_result, result_points
from src.data.validate import (
    ValidationError,
    assert_all_passed,
    check_double_round_robin,
    check_goals_vs_shots_on_target,
    check_scores_match_reference,
    check_table_matches_reference,
    compute_table,
    run_league_checks,
)


def _league(n=4) -> pd.DataFrame:
    teams = [f"Team {i}" for i in range(n)]
    rows = []
    for k, (h, a) in enumerate(itertools.permutations(teams, 2)):
        rows.append({"home_team": h, "away_team": a, "home_goals": k % 3, "away_goals": 1, "date": pd.Timestamp("2016-09-01") + pd.Timedelta(days=k)})
    df = pd.DataFrame(rows)
    df["home_goals"] = df["home_goals"].astype("Int64")
    df["away_goals"] = df["away_goals"].astype("Int64")
    df["competition"], df["season"] = "EPL", "2016/17"
    df["home_team_id"] = df["home_team"].str.replace(" ", "-").str.lower()
    df["away_team_id"] = df["away_team"].str.replace(" ", "-").str.lower()
    df["result"] = derive_result(df["home_goals"], df["away_goals"])
    df["home_points"], df["away_points"] = result_points(df["result"])
    df["match_id"] = build_match_id(df)
    for side in ("home", "away"):
        df[f"{side}_goals_ht"] = pd.Series(0, index=df.index, dtype="Int64")
        df[f"{side}_shots"] = pd.Series(10, index=df.index, dtype="Int64")
        df[f"{side}_shots_on_target"] = pd.Series(5, index=df.index, dtype="Int64")
        df[f"{side}_red_cards"] = pd.Series(0, index=df.index, dtype="Int64")
    return df


def test_clean_league_passes_all_checks():
    df = _league()
    assert_all_passed(run_league_checks(df, n_teams=4, reference_scores={"copy": df.copy()}))


def test_duplicate_fixture_and_missing_match_are_caught():
    df = _league()
    broken = pd.concat([df.iloc[1:], df.iloc[[1]]], ignore_index=True)  # drop one, duplicate another
    with pytest.raises(ValidationError) as err:
        assert_all_passed(run_league_checks(broken, n_teams=4))
    msg = str(err.value)
    assert "unique_match_id" in msg and "no_duplicate_fixtures" in msg and "double_round_robin" in msg


def test_round_robin_reports_off_count_team():
    df = _league().iloc[1:]
    assert not check_double_round_robin(df, 4).passed


def test_score_mismatch_against_reference_is_caught():
    df = _league()
    ref = df.copy()
    ref.loc[0, "home_goals"] = 9
    res = check_scores_match_reference(df, ref, "ref")
    assert not res.passed and "1 score mismatches" in res.detail


def test_goals_above_shots_on_target_is_warning_not_error():
    df = _league()
    df.loc[0, "home_goals"] = 7  # e.g. own goals
    df["result"] = derive_result(df["home_goals"], df["away_goals"])
    df["home_points"], df["away_points"] = result_points(df["result"])
    res = check_goals_vs_shots_on_target(df)
    assert not res.passed and res.severity == "warning"
    assert_all_passed([res])  # warnings never abort


def test_table_check_detects_points_difference():
    df = _league()
    published = compute_table(df)
    assert check_table_matches_reference(df, published).passed
    published.loc[0, "points"] += 1
    assert not check_table_matches_reference(df, published).passed
