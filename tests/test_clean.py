import pandas as pd
import pytest

from src.data.clean import (
    TeamNameNormalizer,
    UnmappedTeamError,
    clean_football_data,
    derive_result,
    normalize_competition,
    normalize_season,
    parse_match_dates,
    result_points,
    season_code,
    validate_attendance,
)
from src.schema import SILVER_COLUMNS


@pytest.mark.parametrize("raw", ["2016/17", "2016-17", "2016/2017", "2016-2017", "1617", 1617])
def test_normalize_season_variants(raw):
    assert normalize_season(raw) == "2016/17"


def test_normalize_season_century_boundary():
    assert normalize_season("1999/00") == "1999/00"
    assert season_code("2025/26") == "2526"


@pytest.mark.parametrize("bad", ["2016/18", "16", "season 1", "2016"])
def test_normalize_season_rejects_bad_labels(bad):
    with pytest.raises(ValueError):
        normalize_season(bad)


def test_parse_dates_two_digit_year_is_day_first():
    s = pd.Series(["13/08/16", "01/02/17"])
    out = parse_match_dates(s)
    assert out.tolist() == [pd.Timestamp("2016-08-13"), pd.Timestamp("2017-02-01")]


def test_parse_dates_rejects_mixed_formats():
    with pytest.raises(ValueError):
        parse_match_dates(pd.Series(["13/08/2016", "2016-08-14"]))


def test_competition_aliases():
    assert normalize_competition("E0") == "EPL"
    assert normalize_competition("  Premier   League ") == "EPL"
    assert normalize_competition("UEFA Champions League") == "UCL"
    with pytest.raises(ValueError):
        normalize_competition("Serie A")


def test_result_and_points():
    hg = pd.Series([2, 1, 0, pd.NA], dtype="Int64")
    ag = pd.Series([0, 1, 3, 1], dtype="Int64")
    r = derive_result(hg, ag)
    assert r.tolist()[:3] == ["H", "D", "A"]
    assert pd.isna(r.iloc[3])
    hp, ap = result_points(r)
    assert hp.tolist()[:3] == [3, 1, 0]
    assert ap.tolist()[:3] == [0, 1, 3]


def test_team_normalizer_reports_every_unknown_name():
    aliases = pd.DataFrame(
        {"alias": ["Man City", "Manchester City"], "canonical_name": ["Manchester City"] * 2, "team_id": ["manchester-city"] * 2}
    )
    norm = TeamNameNormalizer(aliases)
    assert norm.canonical(pd.Series(["man  city"])).tolist() == ["Manchester City"]
    with pytest.raises(UnmappedTeamError, match="Atlantis FC.*Narnia"):
        norm.canonical(pd.Series(["Man City", "Atlantis FC", "Narnia"]))


def test_team_normalizer_rejects_conflicting_alias():
    aliases = pd.DataFrame({"alias": ["United", "United"], "canonical_name": ["A", "B"], "team_id": ["a", "b"]})
    with pytest.raises(ValueError):
        TeamNameNormalizer(aliases)


def test_validate_attendance_flags_only_implausible_values():
    att = pd.Series([50000, -1, 80000, None])
    cap = pd.Series([60000, 60000, 60000, 60000])
    assert validate_attendance(att, cap).tolist() == [False, True, True, False]


def _raw_rows():
    return pd.DataFrame(
        {
            "Date": ["13/08/16", "14/08/16"],
            "HomeTeam": ["Man City", "Arsenal"],
            "AwayTeam": ["Arsenal", "Man City"],
            "FTHG": ["2", "1"], "FTAG": ["1", "1"], "FTR": ["H", "D"],
            "HTHG": ["1", "0"], "HTAG": ["0", "0"],
            "HS": ["10", "8"], "AS": ["5", "9"], "HST": ["4", "3"], "AST": ["2", "4"],
            "Referee": ["M Dean", "A Taylor"],
        }
    )


def _norm():
    return TeamNameNormalizer(
        pd.DataFrame(
            {"alias": ["Man City", "Arsenal"], "canonical_name": ["Manchester City", "Arsenal"], "team_id": ["manchester-city", "arsenal"]}
        )
    )


def test_clean_football_data_produces_full_schema_with_honest_missing_values():
    out = clean_football_data(_raw_rows(), "EPL", "1617", _norm(), "test")
    assert list(out.columns) == SILVER_COLUMNS
    assert out["match_id"].tolist() == ["EPL_1617_20160813_manchester-city_arsenal", "EPL_1617_20160814_arsenal_manchester-city"]
    assert out["result"].tolist() == ["H", "D"]
    # Columns the source does not publish stay missing; they are not zero-filled.
    for col in ("home_corners", "attendance", "home_penalties", "home_possession"):
        assert out[col].isna().all(), col


def test_clean_football_data_rejects_ftr_that_contradicts_goals():
    raw = _raw_rows()
    raw.loc[0, "FTR"] = "A"
    with pytest.raises(ValueError, match="FTR disagrees"):
        clean_football_data(raw, "EPL", "2016/17", _norm(), "test")
