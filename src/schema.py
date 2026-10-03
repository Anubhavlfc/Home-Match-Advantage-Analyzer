"""Canonical match-level schema.

One row = one match. Columns are split by the layer that populates them:

* ``silver``  - facts about the match taken from a source and standardised
  (Phase 2). If no source provides a value, the column exists and is missing
  (``<NA>``). It is never estimated.
* ``gold``    - engineered features computed from silver data and reference
  tables (Phase 3): crowd, COVID period, travel, rest, form, strength.

``docs/schema.md`` is generated from this table: ``python -m src.schema``.
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
    Column("tie_id", "string", "silver", "<stage>:<team_id>|<team_id> linking both legs of a two-legged tie"),
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
    Column("extra_time", "Int64", "silver", "1 if the match went to extra time (UCL knockouts only)"),
    Column("home_goals_aet", "Int64", "silver", "Home score after extra time, if played"),
    Column("away_goals_aet", "Int64", "silver", "Away score after extra time, if played"),
    Column("home_shootout", "Int64", "silver", "Home penalty shoot-out score, if played"),
    Column("away_shootout", "Int64", "silver", "Away penalty shoot-out score, if played"),
    # --- venue and crowd (facts) -------------------------------------------
    Column("stadium", "string", "silver", "Stadium where the match was actually played"),
    Column("city", "string", "silver", "City of the venue"),
    Column("country", "string", "silver", "Country of the venue"),
    Column("neutral_venue", "Int64", "silver", "1 if neither team played at its own home ground"),
    Column("venue_note", "string", "silver", "Why the venue differs from the home club's usual ground (finals, relocations)"),
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
    Column("crowd_status", "string", "gold", "normal / restricted / behind_closed_doors / unknown, from crowd_restrictions.csv"),
    Column("crowd_status_confidence", "string", "gold", "high / medium / low confidence in crowd_status"),
    Column("crowd_rule", "string", "gold", "Note of the crowd rule that set crowd_status"),
    Column("covid_period", "Int64", "gold", "1 for matches from 2020-03-12 to 2021-07-31"),
    Column("covid_phase", "string", "gold", "pre_covid / covid / post_covid"),
    Column("venue_latitude", "Float64", "gold", "Latitude of the stadium the match was played at"),
    Column("venue_longitude", "Float64", "gold", "Longitude of the stadium the match was played at"),
    Column("travel_distance_km", "Float64", "gold", "Haversine km from away club's home ground to actual venue"),
    Column("home_travel_distance_km", "Float64", "gold", "Haversine km from home club's ground to actual venue (non-zero for neutral/relocated games)"),
    Column("home_rest_days", "Float64", "gold", "Days since home team's previous match in the dataset; NA for its first match of a season"),
    Column("away_rest_days", "Float64", "gold", "Days since away team's previous match in the dataset; NA for its first match of a season"),
    Column("rest_difference", "Float64", "gold", "home_rest_days - away_rest_days"),
    Column("rest_difference_capped", "Float64", "gold", "Rest difference with each side capped at 14 days"),
    Column("home_form", "Float64", "gold", "Home team points from its previous 5 matches, any competition (NA with < 5 prior)"),
    Column("away_form", "Float64", "gold", "Away team points from its previous 5 matches, any competition"),
    Column("form_difference", "Float64", "gold", "home_form - away_form"),
    Column("home_last5_win_pct", "Float64", "gold", "Home team win share over previous 5 matches"),
    Column("away_last5_win_pct", "Float64", "gold", "Away team win share over previous 5 matches"),
    Column("home_last5_goal_difference", "Float64", "gold", "Home team goal difference over previous 5 matches"),
    Column("away_last5_goal_difference", "Float64", "gold", "Away team goal difference over previous 5 matches"),
    Column("home_last5_goals_scored", "Float64", "gold", "Home team goals scored over previous 5 matches"),
    Column("away_last5_goals_scored", "Float64", "gold", "Away team goals scored over previous 5 matches"),
    Column("home_last5_goals_conceded", "Float64", "gold", "Home team goals conceded over previous 5 matches"),
    Column("away_last5_goals_conceded", "Float64", "gold", "Away team goals conceded over previous 5 matches"),
    Column("home_last5_home_points", "Float64", "gold", "Home team points from its previous 5 non-neutral home matches"),
    Column("away_last5_away_points", "Float64", "gold", "Away team points from its previous 5 non-neutral away matches"),
    Column("home_matches_before", "Int64", "gold", "Home team's matches in the dataset before this one (warm-up included)"),
    Column("away_matches_before", "Int64", "gold", "Away team's matches in the dataset before this one"),
    Column("home_strength", "Float64", "gold", "Home team Elo rating before kick-off"),
    Column("away_strength", "Float64", "gold", "Away team Elo rating before kick-off"),
    Column("strength_difference", "Float64", "gold", "home_strength - away_strength"),
    Column("strength_reliable", "Int64", "gold", "1 when both teams have at least 20 prior matches in the dataset"),
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
    and any(k in c.name for k in ("shots", "corners", "fouls", "cards", "penalties", "possession", "goals", "shootout"))
) | {"result", "home_points", "away_points", "extra_time"}


_DOC_HEAD = """# Match-level schema

One row = one match. Generated from `src/schema.py` by `python -m src.schema`; do not edit by hand.

* **silver** columns are source facts, standardised in Phase 2. When no source
  provides a value the column is present and missing (`<NA>`), never estimated.
* **gold** columns are engineered in Phase 3 from silver data and reference
  tables. Every rolling or cumulative feature is shifted so it only uses
  matches that finished before kick-off.
* Match statistics (shots, cards, fouls, corners, penalties, possession,
  goals) describe what happened *during* the match. They are listed in
  `IN_MATCH_COLUMNS` and are excluded from the pre-match model (Model A).

"""

_DOC_TAIL = """

## Data layers

| Layer | Folder | Contents |
|---|---|---|
| Bronze | `data/raw/<source>/<competition>/` | Files exactly as downloaded, plus `_manifest.jsonl` (URL, SHA-256, size, UTC access time). Never edited. |
| Silver | `data/interim/matches/`, `data/interim/matches_all.csv` | One standardised CSV per competition-season, written only after all hard validation checks pass, plus all seasons stacked (8,972 matches). |
| Gold | `data/processed/` | Single analytical table across all competitions and seasons with gold features (Phase 3). |
| Reference | `data/reference/` | Hand-curated, cited lookup tables: team aliases (143 clubs), published final tables, venue exceptions (finals, relocations), UCL final winners, stat overrides. Stadiums and crowd restrictions follow in Phase 3. |

## Identifiers

`match_id = <competition>_<season_code>_<yyyymmdd>_<home_team_id>_<away_team_id>`,
for example `EPL_1617_20160814_arsenal_liverpool`. It is deterministic, so
re-running the pipeline produces the same ids, and it stays unique for UCL
two-legged ties because the two legs have different dates and home teams.
"""


def render_markdown() -> str:
    rows = "\n".join(f"| `{c.name}` | {c.dtype} | {c.layer} | {c.description} |" for c in MATCH_SCHEMA)
    return _DOC_HEAD + "| Column | Type | Layer | Description |\n|---|---|---|---|\n" + rows + _DOC_TAIL


if __name__ == "__main__":
    from src.config import REPO_ROOT

    (REPO_ROOT / "docs" / "schema.md").write_text(render_markdown(), encoding="utf-8")
