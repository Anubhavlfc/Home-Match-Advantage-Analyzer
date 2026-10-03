# Match-level schema

One row = one match. Generated from `src/schema.py` by `python -m src.schema`; do not edit by hand.

* **silver** columns are source facts, standardised in Phase 2. When no source
  provides a value the column is present and missing (`<NA>`), never estimated.
* **gold** columns are engineered in Phase 3 from silver data and reference
  tables. Every rolling or cumulative feature is shifted so it only uses
  matches that finished before kick-off.
* Match statistics (shots, cards, fouls, corners, penalties, possession,
  goals) describe what happened *during* the match. They are listed in
  `IN_MATCH_COLUMNS` and are excluded from the pre-match model (Model A).

| Column | Type | Layer | Description |
|---|---|---|---|
| `match_id` | string | silver | Deterministic id: <competition>_<season_code>_<yyyymmdd>_<home_id>_<away_id> |
| `date` | datetime64[ns] | silver | Match date (local date as published by the source) |
| `kickoff_time` | string | silver | Local kick-off time HH:MM if the source provides it |
| `season` | string | silver | Canonical season label, e.g. 2016/17 |
| `season_start_year` | Int64 | silver | Calendar year the season started, e.g. 2016 |
| `competition` | string | silver | Competition code: EPL, LALIGA, UCL |
| `competition_type` | string | silver | domestic_league or continental_cup |
| `stage` | string | silver | Source stage/round label normalised (e.g. league, group_a, round_of_16, final) |
| `ucl_format` | string | silver | group_stage (to 2023/24) or league_phase (2024/25+); NA for domestic |
| `stage_type` | string | silver | league, group, league_phase, knockout_playoff, knockout |
| `knockout_match` | Int64 | silver | 1 if knockout match |
| `two_legged_tie` | Int64 | silver | 1 if the match is one leg of a two-legged tie |
| `leg` | Int64 | silver | 1 or 2 for two-legged ties, NA otherwise |
| `tie_id` | string | silver | <stage>:<team_id>|<team_id> linking both legs of a two-legged tie |
| `home_team` | string | silver | Canonical home (first-listed) team name |
| `away_team` | string | silver | Canonical away (second-listed) team name |
| `home_team_id` | string | silver | Stable slug for the home team |
| `away_team_id` | string | silver | Stable slug for the away team |
| `home_goals` | Int64 | silver | Full-time home goals (90 min + stoppage; excludes extra time where separable) |
| `away_goals` | Int64 | silver | Full-time away goals |
| `home_goals_ht` | Int64 | silver | Half-time home goals |
| `away_goals_ht` | Int64 | silver | Half-time away goals |
| `result` | string | silver | H / D / A derived from full-time goals |
| `home_points` | Int64 | silver | 3/1/0 derived from result |
| `away_points` | Int64 | silver | 3/1/0 derived from result |
| `extra_time` | Int64 | silver | 1 if the match went to extra time (UCL knockouts only) |
| `home_goals_aet` | Int64 | silver | Home score after extra time, if played |
| `away_goals_aet` | Int64 | silver | Away score after extra time, if played |
| `home_shootout` | Int64 | silver | Home penalty shoot-out score, if played |
| `away_shootout` | Int64 | silver | Away penalty shoot-out score, if played |
| `stadium` | string | silver | Stadium where the match was actually played |
| `city` | string | silver | City of the venue |
| `country` | string | silver | Country of the venue |
| `neutral_venue` | Int64 | silver | 1 if neither team played at its own home ground |
| `venue_note` | string | silver | Why the venue differs from the home club's usual ground (finals, relocations) |
| `attendance` | Int64 | silver | Reported attendance; NA if not published by any integrated source |
| `stadium_capacity` | Int64 | silver | Venue capacity from reference table |
| `attendance_pct` | Float64 | silver | attendance / stadium_capacity |
| `home_shots` | Int64 | silver | Home shots |
| `away_shots` | Int64 | silver | Away shots |
| `home_shots_on_target` | Int64 | silver | Home shots on target |
| `away_shots_on_target` | Int64 | silver | Away shots on target |
| `home_corners` | Int64 | silver | Home corners |
| `away_corners` | Int64 | silver | Away corners |
| `home_fouls` | Int64 | silver | Fouls committed by home team |
| `away_fouls` | Int64 | silver | Fouls committed by away team |
| `home_yellow_cards` | Int64 | silver | Home yellow cards |
| `away_yellow_cards` | Int64 | silver | Away yellow cards |
| `home_red_cards` | Int64 | silver | Home red cards |
| `away_red_cards` | Int64 | silver | Away red cards |
| `home_penalties` | Int64 | silver | Penalties awarded to home team |
| `away_penalties` | Int64 | silver | Penalties awarded to away team |
| `home_possession` | Float64 | silver | Home possession share 0-100 |
| `away_possession` | Float64 | silver | Away possession share 0-100 |
| `referee` | string | silver | Referee name as published by the source |
| `source` | string | silver | Source id(s) the row was built from |
| `crowd_status` | string | gold | normal / restricted / behind_closed_doors / unknown, from crowd_restrictions.csv |
| `crowd_status_confidence` | string | gold | high / medium / low confidence in crowd_status |
| `crowd_rule` | string | gold | Note of the crowd rule that set crowd_status |
| `covid_period` | Int64 | gold | 1 for matches from 2020-03-12 to 2021-07-31 |
| `covid_phase` | string | gold | pre_covid / covid / post_covid |
| `venue_latitude` | Float64 | gold | Latitude of the stadium the match was played at |
| `venue_longitude` | Float64 | gold | Longitude of the stadium the match was played at |
| `travel_distance_km` | Float64 | gold | Haversine km from away club's home ground to actual venue |
| `home_travel_distance_km` | Float64 | gold | Haversine km from home club's ground to actual venue (non-zero for neutral/relocated games) |
| `home_rest_days` | Float64 | gold | Days since home team's previous match in the dataset; NA for its first match of a season |
| `away_rest_days` | Float64 | gold | Days since away team's previous match in the dataset; NA for its first match of a season |
| `rest_difference` | Float64 | gold | home_rest_days - away_rest_days |
| `rest_difference_capped` | Float64 | gold | Rest difference with each side capped at 14 days |
| `home_rest_days_all` | Float64 | gold | Days since the home team's previous match in any covered competition (adds FA Cup, EFL Cup, Copa del Rey, Europa and Conference League). EPL and La Liga clubs in 2020/21 to 2024/25 only; NA elsewhere and for a first match of the season |
| `away_rest_days_all` | Float64 | gold | As `home_rest_days_all`, for the away team |
| `rest_difference_all_capped` | Float64 | gold | `home_rest_days_all` minus `away_rest_days_all`, each capped at 14 days |
| `home_form` | Float64 | gold | Home team points from its previous 5 matches, any competition (NA with < 5 prior) |
| `away_form` | Float64 | gold | Away team points from its previous 5 matches, any competition |
| `form_difference` | Float64 | gold | home_form - away_form |
| `home_last5_win_pct` | Float64 | gold | Home team win share over previous 5 matches |
| `away_last5_win_pct` | Float64 | gold | Away team win share over previous 5 matches |
| `home_last5_goal_difference` | Float64 | gold | Home team goal difference over previous 5 matches |
| `away_last5_goal_difference` | Float64 | gold | Away team goal difference over previous 5 matches |
| `home_last5_goals_scored` | Float64 | gold | Home team goals scored over previous 5 matches |
| `away_last5_goals_scored` | Float64 | gold | Away team goals scored over previous 5 matches |
| `home_last5_goals_conceded` | Float64 | gold | Home team goals conceded over previous 5 matches |
| `away_last5_goals_conceded` | Float64 | gold | Away team goals conceded over previous 5 matches |
| `home_last5_home_points` | Float64 | gold | Home team points from its previous 5 non-neutral home matches |
| `away_last5_away_points` | Float64 | gold | Away team points from its previous 5 non-neutral away matches |
| `home_matches_before` | Int64 | gold | Home team's matches in the dataset before this one (warm-up included) |
| `away_matches_before` | Int64 | gold | Away team's matches in the dataset before this one |
| `home_strength` | Float64 | gold | Home team Elo rating before kick-off |
| `away_strength` | Float64 | gold | Away team Elo rating before kick-off |
| `strength_difference` | Float64 | gold | home_strength - away_strength |
| `strength_reliable` | Int64 | gold | 1 when both teams have at least 20 prior matches in the dataset |

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
