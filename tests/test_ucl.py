import pandas as pd
import pytest

from src.data.clean import TeamNameNormalizer, apply_venue_exceptions
from src.data.extract import ExtractError
from src.data.ucl import clean_openfootball_cl, parse_cl_text, parse_score
from src.data.validate import check_extra_time_consistency, run_ucl_checks


@pytest.mark.parametrize(
    "text, ft90, ht, aet, pens",
    [
        ("2-1 (1-0)", (2, 1), (1, 0), None, None),
        ("0-0", (0, 0), None, None, None),
        ("3-2 a.e.t. (2-1, 0-1)", (2, 1), (0, 1), (3, 2), None),
        ("4-2 pen. 1-1 a.e.t. (1-1, 0-0)", (1, 1), (0, 0), (1, 1), (4, 2)),
    ],
)
def test_parse_score_keeps_90_minute_score_separate(text, ft90, ht, aet, pens):
    s = parse_score(text)
    assert (s["ft90"], s["ht"], s["aet"], s["pens"]) == (ft90, ht, aet, pens)


@pytest.mark.parametrize("bad", ["2:1", "4-2 pen. 1-1", "abc"])
def test_parse_score_rejects_unknown_formats(bad):
    with pytest.raises(ValueError):
        parse_score(bad)


SAMPLE = """= UEFA Champions League 2019/20

▪ Group A
  Tue Sep 17 2019
    21:00  Real Madrid CF (ESP)  v Paris Saint-Germain (FRA)  0-0
▪ Final
  Sun Aug 23
    21:00  Paris Saint-Germain (FRA) v Bayern München (GER)  0-1 (0-0)
"""


def test_parse_cl_text_infers_year_from_season():
    df = parse_cl_text(SAMPLE, "2019/20")
    assert df["date"].tolist() == [pd.Timestamp("2019-09-17"), pd.Timestamp("2020-08-23")]
    assert df["stage"].tolist() == ["group_a", "final"]


def test_parse_cl_text_rejects_unparsed_lines():
    with pytest.raises(ValueError, match="Unparsed"):
        parse_cl_text(SAMPLE + "    something odd here\n", "2019/20")


def _ties():
    return pd.DataFrame(
        {
            "match_id": ["a", "b"],
            "tie_id": ["r16:x|y", "r16:x|y"],
            "leg": [1, 2],
            "two_legged_tie": [1, 1],
            "knockout_match": [1, 1],
            "extra_time": [0, 1],
            "home_goals": [0, 0],  # leg 1: X 0-1 Y; leg 2: Y 0-1 X (a.e.t.)
            "away_goals": [1, 1],
            "home_goals_aet": [pd.NA, 0],
            "away_goals_aet": [pd.NA, 1],
            "home_shootout": [pd.NA, 4],
            "away_shootout": [pd.NA, 2],
        }
    ).astype({"home_goals_aet": "Int64", "away_goals_aet": "Int64", "home_shootout": "Int64", "away_shootout": "Int64"})


def test_shootout_is_valid_when_aggregate_is_level():
    # X 0-1 Y, then Y 0-1 X a.e.t. -> 1-1 on aggregate -> shoot-out is legitimate
    assert check_extra_time_consistency(_ties()).passed


def test_shootout_after_decisive_aggregate_is_flagged():
    df = _ties()
    df.loc[1, "home_goals_aet"] = 2
    assert not check_extra_time_consistency(df).passed


def test_venue_exception_that_matches_nothing_raises():
    df = pd.DataFrame(
        {"competition": ["UCL"], "season": ["2020/21"], "stage": ["final"], "home_team": ["A"], "away_team": ["B"],
         "stadium": [pd.NA], "city": [pd.NA], "country": [pd.NA], "neutral_venue": [0], "venue_note": [pd.NA]}
    )
    ex = pd.DataFrame(
        {"competition": ["UCL"], "season": ["2020/21"], "stage": ["quarter_final"], "home_team": ["A"], "away_team": ["*"],
         "stadium": ["X"], "city": ["Y"], "country": ["Z"], "neutral_venue": ["1"], "reason": ["r"]}
    )
    with pytest.raises(ValueError, match="matched no match"):
        apply_venue_exceptions(df, ex)
    ex.loc[0, "stage"] = "final"
    out = apply_venue_exceptions(df, ex)
    assert out.loc[0, "neutral_venue"] == 1 and out.loc[0, "city"] == "Y"


@pytest.fixture(scope="module")
def ucl_2021():
    from src.pipeline import run_ucl_season

    try:
        return run_ucl_season("2020/21")
    except ExtractError as err:  # pragma: no cover - depends on network
        pytest.skip(f"raw data unavailable: {err}")


def test_ucl_2020_21_relocated_ties_are_neutral(ucl_2021):
    budapest = ucl_2021[ucl_2021["city"] == "Budapest"]
    assert len(budapest) == 4 and (budapest["neutral_venue"] == 1).all()
    final = ucl_2021[ucl_2021["stage"] == "final"].iloc[0]
    assert (final["city"], final["neutral_venue"], final["away_team"], final["result"]) == ("Porto", 1, "Chelsea", "A")
    # Normal group games default to the home club's country and are not neutral.
    group = ucl_2021[ucl_2021["stage"].str.startswith("group")]
    assert (group["neutral_venue"] == 0).all()
