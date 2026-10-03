"""Unit tests for the cup and Europa fixture-date parser."""
import numpy as np
import pandas as pd

from src.data import other_fixtures
from src.models.logistic_model import rps

SAMPLE_V = """= English FA Cup 2018/19

▪ Round 3
  Fri Jan 4 2019
    19:45  Tranmere Rovers         v Tottenham Hotspur        0-7 (0-3)
  Sat Jan 5
           Arsenal FC (ENG)        v Blackpool FC             3-0 (1-0)
           Harrogate Town          v Rochdale AFC             [cancelled]
"""

SAMPLE_ES = """= Copa del Rey 2023/24

▪ Round 1
Wed Nov 1
  19:00  Arosa SC                 3-0  Granada CF               [awarded]
         CD Cardassar             -  AD CF Épila
  20:00  Móstoles CF              4-5 pen. 0-0 a.e.t. (0-0)  CD Marchamalo
"""


def test_parse_v_layout_with_year_inference_and_cancellations():
    fx = other_fixtures.parse_dates(SAMPLE_V, "2018/19")
    assert fx["home"].tolist() == ["Tranmere Rovers", "Arsenal FC", "Harrogate Town"]
    assert fx["away"].tolist() == ["Tottenham Hotspur", "Blackpool FC", "Rochdale AFC"]
    assert fx["date"].tolist() == [pd.Timestamp("2019-01-04"), pd.Timestamp("2019-01-05"), pd.Timestamp("2019-01-05")]
    assert fx["played"].tolist() == [True, True, False]


def test_parse_copa_layout_keeps_awarded_and_drops_unplayed():
    fx = other_fixtures.parse_dates(SAMPLE_ES, "2023/24")
    assert fx["away"].tolist() == ["Granada CF", "AD CF Épila", "CD Marchamalo"]
    assert fx["date"].iloc[0] == pd.Timestamp("2023-11-01")
    assert fx["played"].tolist() == [True, False, True]


def test_expected_competitions_respect_start_season():
    assert "UECL" not in other_fixtures.expected("2020/21")
    assert "UECL" in other_fixtures.expected("2021/22")


def test_rps_perfect_and_ordered():
    y = np.array([0, 1, 2])
    assert rps(y, np.eye(3)) == 0
    # Forecasting a home win is punished more when the result is an away win than a draw.
    p = np.array([[0.0, 0.0, 1.0]])
    assert rps(np.array([0]), p) > rps(np.array([1]), p)
