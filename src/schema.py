"""Canonical match-level schema.

One row = one match. Columns are split by the layer that populates them:

* ``silver``  - facts about the match taken from a source and standardised
  (Phase 2). If no source provides a value, the column exists and is missing
  (``<NA>``). It is never estimated.
* ``gold``    - engineered features computed from silver data and reference
  tables (Phase 3): crowd, COVID period, travel, rest, form, strength.

``docs/schema.md`` is the human-readable version of this table; keep the two
in sync.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str  # pandas dtype used when the column is materialised
    layer: str  # "silver" or "gold"
    description: str


MATCH_SCHEMA: tuple[Column, ...] = (
    # --- identifiers -------------------------------------------------------
    Column("match_id", "string", "silver", "Deterministic id: <competition>_<season_code>_<yyyymmdd>_<home_id>_<away_id>"),
    Column("date", "datetime64[ns]", "silver", "Match date (local date as published by the source)"),
    Column("kickoff_time", "string", "silver", "Local kick-off time HH:MM if the source provides it"),
    Column("season", "string", "silver", "Canonical season label, e.g. 2016/17"),
    Column("season_start_year", "Int64", "silver", "Calendar year the season started, e.g. 2016"),
    Column("competition", "string", "silver", "Competition code: EPL, LALIGA, UCL"),
    Column("competition_type", "string", "silver", "domestic_league or continental_cup"),
    Column("stage", "string", "silver", "Source stage/round label normalised (e.g. league, group_a, round_of_16, final)"),
    Column("ucl_format", "string", "silver", "group_stage (to 2023/24) or league_phase (2024/25+); NA for domestic"),
    Column("stage_type", "string", "silver", "league, group, league_phase, knockout_playoff, knockout"),
    Column("knockout_match", "Int64", "silver", "1 if knockout match"),
    Column("two_legged_tie", "Int64", "silver", "1 if the match is one leg of a two-legged tie"),
    Column("leg", "Int64", "silver", "1 or 2 for two-legged ties, NA otherwise"),
    Column("home_team", "string", "silver", "Canonical home (first-listed) team name"),
    Column("away_team", "string", "silver", "Canonical away (second-listed) team name"),
    Column("home_team_id", "string", "silver", "Stable slug for the home team"),
    Column("away_team_id", "string", "silver", "Stable slug for the away team"),
    # --- outcome -----------------------------------------------------------
    Column("home_goals", "Int64", "silver", "Full-time home goals (90 min + stoppage; excludes extra time where separable)"),
    Column("away_goals", "Int64", "silver", "Full-time away goals"),
    Column("home_goals_ht", "Int64", "silver", "Half-time home goals"),
    Column("away_goals_ht", "Int64", "silver", "Half-time away goals"),
    Column("result", "string", "silver", "H / D / A derived from full-time goals"),
    Column("home_points", "Int64", "silver", "3/1/0 derived from result"),
    Column("away_points", "Int64", "silver", "3/1/0 derived from result"),
    # --- venue and crowd (facts) -------------------------------------------
    Column("stadium", "string", "silver", "Stadium where the match was actually played"),
    Column("city", "string", "silver", "City of the venue"),
    Column("country", "string", "silver", "Country of the venue"),
    Column("neutral_venue", "Int64", "silver", "1 if neither team played at its own home ground"),
    Column("attendance", "Int64", "silver", "Reported attendance; NA if not published by any integrated source"),
    Column("stadium_capacity", "Int64", "silver", "Venue capacity from reference table"),
    Column("attendance_pct", "Float64", "silver", "attendance / stadium_capacity"),
    # --- match statistics (in-match, NOT pre-match predictors) --------------
    Column("home_shots", "Int64", "silver", "Home shots"),
    Column("away_shots", "Int64", "silver", "Away shots"),
    Column("home_shots_on_target", "Int64", "silver", "Home shots on target"),
    Column("away_shots_on_target", "Int64", "silver", "Away shots on target"),
    Column("home_corners", "Int64", "silver", "Home corners"),
    Column("away_corners", "Int64", "silver", "Away corners"),
    Column("home_fouls", "Int64", "silver", "Fouls committed by home team"),
    Column("away_fouls", "Int64", "silver", "Fouls committed by away team"),
    Column("home_yellow_cards", "Int64", "silver", "Home yellow cards"),
    Column("away_yellow_cards", "Int64", "silver", "Away yellow cards"),
    Column("home_red_cards", "Int64", "silver", "Home red cards"),
    Column("away_red_cards", "Int64", "silver", "Away red cards"),
    Column("home_penalties", "Int64", "silver", "Penalties awarded to home team"),
    Column("away_penalties", "Int64", "silver", "Penalties awarded to away team"),
    Column("home_possession", "Float64", "silver", "Home possession share 0-100"),
    Column("away_possession", "Float64", "silver", "Away possession share 0-100"),
    Column("referee", "string", "silver", "Referee name as published by the source"),
    # --- lineage -----------------------------------------------------------
    Column("source", "string", "silver", "Source id(s) the row was built from"),
    # --- engineered features (Phase 3) -------------------------------------
    Column("crowd_status", "string", "gold", "normal / restricted / behind_closed_doors / unknown"),
    Column("covid_period", "Int64", "gold", "1 for matches in the COVID disruption window"),
    Column("covid_phase", "string", "gold", "pre_covid / covid / post_covid"),
    Column("travel_distance_km", "Float64", "gold", "Haversine km from away club's home ground to actual venue"),
    Column("home_rest_days", "Float64", "gold", "Days since home team's previous match in the dataset (approximate)"),
    Column("away_rest_days", "Float64", "gold", "Days since away team's previous match in the dataset (approximate)"),
    Column("rest_difference", "Float64", "gold", "home_rest_days - away_rest_days"),
    Column("home_form", "Float64", "gold", "Home team points from previous 5 matches (shifted, pre-kickoff)"),
    Column("away_form", "Float64", "gold", "Away team points from previous 5 matches (shifted, pre-kickoff)"),
    Column("home_strength", "Float64", "gold", "Pre-match home strength rating (e.g. Elo before kickoff)"),
    Column("away_strength", "Float64", "gold", "Pre-match away strength rating"),
    Column("strength_difference", "Float64", "gold", "home_strength - away_strength"),
)

SILVER_COLUMNS: list[str] = [c.name for c in MATCH_SCHEMA if c.layer == "silver"]
GOLD_COLUMNS: list[str] = [c.name for c in MATCH_SCHEMA]
DTYPES: dict[str, str] = {c.name: c.dtype for c in MATCH_SCHEMA}

# Columns that describe what happened during the match. They must never be
# used as features in the pre-match model (Model A).
IN_MATCH_COLUMNS: frozenset[str] = frozenset(
    c.name
    for c in MATCH_SCHEMA
    if c.name.startswith(("home_", "away_"))
    and any(k in c.name for k in ("shots", "corners", "fouls", "cards", "penalties", "possession", "goals"))
) | {"result", "home_points", "away_points"}
