"""Unit tests for Phase 3 feature engineering."""
import numpy as np
import pandas as pd
import pytest

from src.features import crowd_features, team_history, venues


def _matches(rows):
    df = pd.DataFrame(rows, columns=["date", "home_team_id", "away_team_id", "home_goals", "away_goals"])
    df["date"] = pd.to_datetime(df["date"])
    df["match_id"] = [f"M{i:03d}" for i in range(len(df))]
    df["season"] = "2016/17"
    df["competition"] = "EPL"
    df["neutral_venue"] = 0
    gd = df["home_goals"] - df["away_goals"]
    df["home_points"] = np.select([gd > 0, gd == 0], [3, 1], 0)
    df["away_points"] = np.select([gd < 0, gd == 0], [3, 1], 0)
    return df


def test_haversine_known_distance():
    # London (Emirates) to Madrid (Bernabeu) is roughly 1,260 km.
    d = venues.haversine_km(51.5549, -0.1084, 40.4531, -3.6883)
    assert 1240 < float(d) < 1280
    assert float(venues.haversine_km(10, 10, 10, 10)) == 0.0


def test_home_ground_competition_specific_row_wins():
    st = venues.load_stadiums()
    out = venues.home_ground(
        pd.Series(["tottenham-hotspur", "tottenham-hotspur", "tottenham-hotspur"]),
        pd.Series(["2016-09-14", "2016-09-18", "2018-09-15"]),
        pd.Series(["UCL", "EPL", "EPL"]),
        st,
    )
    assert out["stadium"].tolist() == ["Wembley Stadium", "White Hart Lane", "Wembley Stadium"]


def test_home_ground_missing_team_raises():
    with pytest.raises(ValueError, match="No stadium"):
        venues.home_ground(pd.Series(["no-such-club"]), pd.Series(["2020-01-01"]), pd.Series(["EPL"]), venues.load_stadiums())


def test_crowd_rule_precedence():
    rules = pd.DataFrame(
        {
            "priority": [0, 1, 2],
            "competition": ["*", "EPL", "EPL"],
            "host_country": ["*", "England", "England"],
            "home_team_id": ["*", "*", "liverpool"],
            "date_from": pd.to_datetime(["2020-01-01"] * 3),
            "date_to": pd.to_datetime(["2020-12-31"] * 3),
            "crowd_status": ["unknown", "behind_closed_doors", "restricted"],
            "confidence": ["low", "high", "medium"],
            "note": ["a", "b", "c"],
        }
    )
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-12-05", "2020-12-05", "2020-12-05"]),
            "competition": ["EPL", "EPL", "LALIGA"],
            "country": ["England", "England", "Spain"],
            "home_team_id": ["liverpool", "everton", "sevilla"],
        }
    )
    out = crowd_features.assign_crowd_status(df, rules)
    assert out["crowd_status"].tolist() == ["restricted", "behind_closed_doors", "unknown"]


def test_crowd_rules_cover_every_date():
    df = pd.DataFrame(
        {"date": pd.to_datetime(["2014-08-16", "2020-06-20", "2026-05-24"]), "competition": "EPL",
         "country": "England", "home_team_id": "arsenal"}
    )
    out = crowd_features.assign_crowd_status(df)
    assert out["crowd_status"].tolist() == ["normal", "behind_closed_doors", "normal"]


def test_covid_phase_boundaries():
    df = pd.DataFrame({"date": pd.to_datetime(["2020-03-11", "2020-03-12", "2021-07-31", "2021-08-01"])})
    out = crowd_features.assign_covid_period(df)
    assert out["covid_phase"].tolist() == ["pre_covid", "covid", "covid", "post_covid"]
    assert out["covid_period"].tolist() == [0, 1, 1, 0]


def test_form_and_rest_use_only_earlier_matches():
    rows = [("2016-08-0%d" % (i + 1), "a", "b", 1, 0) for i in range(7)]
    df = _matches(rows)
    long = team_history.add_form(team_history.add_rest_days(team_history.long_format(df)))
    out = team_history.attach_team_features(df, long)
    # Team a wins every game: form is NA for the first 5 games, then 15.
    assert out["home_form"].isna().tolist() == [True] * 5 + [False, False]
    assert out["home_form"].iloc[5] == 15 and out["away_form"].iloc[5] == 0
    # A big result in the current match must not change its own form.
    df2 = df.copy()
    df2.loc[6, ["home_goals", "away_goals", "home_points", "away_points"]] = [0, 5, 0, 3]
    out2 = team_history.attach_team_features(df2, team_history.add_form(team_history.add_rest_days(team_history.long_format(df2))))
    assert out2["home_form"].iloc[6] == out["home_form"].iloc[6]
    # Rest: NA for first match of the season, then 1 day.
    assert pd.isna(out["home_rest_days"].iloc[0]) and out["home_rest_days"].iloc[1] == 1


def test_elo_is_pre_match():
    df = _matches([("2016-08-01", "a", "b", 3, 0), ("2016-08-08", "a", "b", 0, 0)])
    elo = team_history.run_elo(df, home_adv=60)
    assert elo["home_elo"].iloc[0] == elo["away_elo"].iloc[0] == team_history.ELO_INIT
    assert elo["home_elo"].iloc[1] > team_history.ELO_INIT > elo["away_elo"].iloc[1]
    # Zero-sum update.
    assert elo["home_elo"].iloc[1] + elo["away_elo"].iloc[1] == pytest.approx(2 * team_history.ELO_INIT)
