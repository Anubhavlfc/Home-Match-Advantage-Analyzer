"""Venue resolution and travel distance.

Every match gets the coordinates of the stadium it was actually played at:

1. a row in ``venue_exceptions.csv`` (finals, relocations, displaced clubs), or
2. otherwise the home club's ground on that date from ``stadiums.csv``
   (date ranges cover temporary moves such as Tottenham at Wembley).

Travel distance is the great-circle (Haversine) distance from each club's
home ground on the match date to the actual venue. For a neutral venue both
teams travel, so ``home_travel_distance_km`` is recorded too.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import repo_path

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def load_stadiums() -> pd.DataFrame:
    st = pd.read_csv(repo_path("reference") / "stadiums.csv", dtype=str, keep_default_na=False)
    st["latitude"] = st["latitude"].astype(float)
    st["longitude"] = st["longitude"].astype(float)
    st["valid_from"] = pd.to_datetime(st["valid_from"].replace("", "1900-01-01"))
    st["valid_to"] = pd.to_datetime(st["valid_to"].replace("", "2100-01-01"))
    return st


def home_ground(team_ids: pd.Series, dates: pd.Series, competitions: pd.Series, stadiums: pd.DataFrame) -> pd.DataFrame:
    """The ground each club used as its home on each date.

    A competition-specific row (e.g. Tottenham's 2016/17 Champions League
    games at Wembley) beats a generic one. Missing or ambiguous matches raise.
    """
    q = pd.DataFrame({"team_id": team_ids.values, "date": pd.to_datetime(dates.values), "comp": competitions.values})
    q["_row"] = np.arange(len(q))
    m = q.merge(stadiums, on="team_id", how="left")
    m = m[(m["date"] >= m["valid_from"]) & (m["date"] <= m["valid_to"]) & ((m["competition"] == "") | (m["competition"] == m["comp"]))]
    m["_specific"] = (m["competition"] != "").astype(int)
    m = m.sort_values(["_row", "_specific"], ascending=[True, False])
    best = m.groupby("_row").head(1)
    ties = m.groupby(["_row", "_specific"]).size()
    if (ties > 1).any():
        bad = q.loc[ties[ties > 1].index.get_level_values(0), ["team_id", "date"]].drop_duplicates().head(5)
        raise ValueError(f"Ambiguous stadium rows for:\n{bad}")
    missing = sorted(set(q["_row"]) - set(best["_row"]))
    if missing:
        raise ValueError(f"No stadium for: {q.loc[missing, ['team_id', 'date']].drop_duplicates('team_id').head(10).to_dict('records')}")
    best = best.set_index("_row").sort_index()
    return best[["stadium", "city", "country", "latitude", "longitude"]].reset_index(drop=True)


def add_venue_and_travel(df: pd.DataFrame, stadiums: pd.DataFrame | None = None) -> pd.DataFrame:
    """Fill stadium/city/country and coordinates; compute travel distances."""
    stadiums = load_stadiums() if stadiums is None else stadiums
    exceptions = pd.read_csv(repo_path("reference") / "venue_exceptions.csv", dtype=str)
    df = df.reset_index(drop=True).copy()

    home = home_ground(df["home_team_id"], df["date"], df["competition"], stadiums)
    away = home_ground(df["away_team_id"], df["date"], df["competition"], stadiums)

    # Venue = home club's ground unless an exception already set the stadium.
    exc_coords = exceptions.set_index("stadium")[["latitude", "longitude"]].astype(float)
    exc_coords = exc_coords[~exc_coords.index.duplicated()]
    has_exc = df["venue_note"].notna()
    df["venue_latitude"] = np.where(has_exc, df["stadium"].map(exc_coords["latitude"]), home["latitude"])
    df["venue_longitude"] = np.where(has_exc, df["stadium"].map(exc_coords["longitude"]), home["longitude"])
    for col in ("stadium", "city", "country"):
        df[col] = df[col].where(has_exc, home[col]).astype("string")
    if df[["venue_latitude", "venue_longitude"]].isna().any().any():
        raise ValueError("Venue without coordinates")

    df["travel_distance_km"] = haversine_km(away["latitude"], away["longitude"], df["venue_latitude"], df["venue_longitude"]).round(1)
    df["home_travel_distance_km"] = haversine_km(
        home["latitude"], home["longitude"], df["venue_latitude"], df["venue_longitude"]
    ).round(1)
    return df
