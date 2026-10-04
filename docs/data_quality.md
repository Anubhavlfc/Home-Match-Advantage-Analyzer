# Data quality

## Result of the full ETL run (Phase 2)

`python -m src.pipeline --all` produces 8,972 matches in
`data/interim/matches_all.csv`, and every hard check passes for every
competition-season.

| Competition | Seasons | Matches | Cross-checks |
|---|---|---|---|
| Premier League | 10 | 3,800 | Every score identical in openfootball; rebuilt table equals the published final table for all 200 team-seasons |
| La Liga | 10 | 3,800 | Same: all scores identical, all 200 team-seasons equal the published table |
| Champions League | 10 | 1,372 | Stage counts, group/league-phase structure, two-legged ties, knockout progression and final winner all as published |

Per-season results are in `reports/data_quality/<COMP>_<season>_checks.csv`,
with missingness per column alongside. `ALL_checks.csv` covers the combined
table (row count, unique `match_id`, schema).

## Checks

Hard checks (severity `error`) abort the run before anything is written.
Warnings are recorded and the data are kept as published.

### League seasons (EPL, La Liga)

| Check | Severity | What it catches |
|---|---|---|
| `row_count` | error | Missing or extra matches (expects n x (n-1)) |
| `unique_match_id` | error | Duplicate rows |
| `no_duplicate_fixtures` | error | Same home/away pairing twice |
| `double_round_robin` | error | A team without exactly n-1 home and n-1 away games |
| `dates_in_season_window` | error | Dates outside 1 July to 31 August of the following year |
| `result_matches_goals` | error | Result or points inconsistent with goals (the source `FTR` is also checked on load) |
| `logical_bounds` | error | Negative counts, half-time goals above full-time, shots on target above shots |
| `goals_exceed_shots_on_target` | warning | More goals than shots on target, which own goals make possible |
| `scores_match_openfootball` | error | A score that differs from openfootball, or a match missing from one source |
| `table_matches_published` | error | Rebuilt final table differs from the published one (after documented points deductions) |

### Champions League seasons

| Check | Severity | What it catches |
|---|---|---|
| `ucl_stage_counts` | error | Stage sizes other than 96/16/8/4/1 (group era), 96/16/4/2/1 (2019/20) or 144/16/16/8/4/1 (league phase) |
| `ucl_group_structure` | error | Groups that are not 8 x 4 teams with every ordered pair once. Groups are rebuilt as connected components, because the 2023/24 file does not label them |
| `ucl_league_phase` | error | League phase without 36 teams and 4 home + 4 away each, or a repeated pairing |
| `two_legged_ties` | error | A tie without exactly two legs with home and away swapped |
| `knockout_progression` | error | A team in a round that was not in the previous one; rounds not 16 > 8 > 4 > 2 |
| `extra_time_consistency` | error | Extra time outside knockouts, extra-time score below the 90-minute score, or a shoot-out when the tie (aggregate for second legs) was not level |
| `final_winner_matches_published` | error | Final winner (after extra time and penalties) differs from `ucl_finals.csv` |
| `neutral_venues_flagged` | error | A final not marked as a neutral venue |

## Warnings and corrections

- **Goals above shots on target**: 50 matches across 16 league-seasons. Kept
  as published (own goals explain most of them).
- **One impossible value blanked**: Newcastle v West Ham, 2021-08-15, has 8
  away shots but 9 on target. The true values are unknown, so both are set to
  missing, as logged in `data/reference/stat_overrides.csv`. Nothing is ever
  replaced with an estimate.
- **Points deductions**: Everton (-8) and Nottingham Forest (-4) in 2023/24.
  Stored in `final_tables.csv` and applied before the table comparison.

## Gaps filled from other real data

These fill gaps only with values that are recorded elsewhere or are
logically certain. Nothing is estimated.

- **Kick-off times** for domestic matches come from openfootball, and only
  for a season whose fixtures and scores match the primary source exactly.
- **Half-time score of 0-0 draws** in the Champions League files is omitted by
  the source; it can only be 0-0 and is set so.
- **Venue country** is the home club's country (Swansea and Cardiff play in
  Wales, Monaco in Monaco), unless a venue exception applies.

## Source issues found

- **openfootball EPL 2019/20 dates**: the 66 matches played after the COVID
  restart in July 2020 are dated July **2019** in the JSON. The scores are
  correct. The pipeline uses football-data dates, and this shows up only as an
  informational "date differences" count in the cross-check.
- **openfootball 2025/26 JSON** uses a bare `[h, a]` score for some 0-0
  matches instead of `{"ft": [h, a]}`. Both forms are handled.
- **La Liga referee** column is empty in every season.

## Venue exceptions (`data/reference/venue_exceptions.csv`)

49 matches are not at the listed home team's usual ground, 33 of them at a neutral venue:

| Case | Matches | `neutral_venue` |
|---|---|---|
| Finals (Cardiff, Kyiv, Madrid, Lisbon, Porto, Saint-Denis, Istanbul, London, Munich, Budapest) | 10 | 1 |
| 2019/20 Lisbon final tournament, quarter- and semi-finals | 6 | 1 |
| 2020/21 ties moved because of COVID travel rules (Budapest x4, Bucharest, Seville x2) | 7 | 1 |
| Shakhtar Donetsk home games abroad (Warsaw 2022/23, Hamburg 2023/24, Gelsenkirchen 2024/25) | 10 | 1 |
| Shakhtar Donetsk home games elsewhere in Ukraine (Kharkiv, Kyiv), 2017/18 to 2021/22 | 16 | 0 (same country, but venue recorded for travel distance) |

Each row must match at least one match or the pipeline fails, so a typo cannot
silently leave a final marked as a home game.

## Gold table (Phase 3)

`python -m src.features.build` writes `data/processed/matches_gold.csv`
(8,972 rows, same as silver) and a summary JSON. The build fails on any of:

- a club without a home ground on a match date, or two equally specific rows;
- a match not covered by any crowd rule;
- a row-count change or duplicate `match_id`;
- a non-neutral match far from the home ground without a venue note;
- any form or rest value in a 300-match sample that differs from a direct
  recomputation from earlier-dated rows.

Feature missingness is by design: rest days 3.5% (first match of a season),
form 2% (clubs with fewer than 5 prior matches, mostly UCL newcomers),
venue-specific form 4%. Elo, travel and crowd status are complete. Two runs
produce byte-identical files.

Stadium coordinates (`stadiums.csv`) were compiled by hand to about 100 m
precision; they feed only distances, where that error is negligible. The
Shakhtar row is Kyiv, used only as a travel origin since its games are placed
by venue exceptions.

## Still open

- **Rest days** (`*_rest_days`) are approximate because domestic cups and
  other European competitions are not in the dataset. Complete rest days
  (`*_rest_days_all`) add those fixtures for EPL and La Liga clubs in
  2020/21 to 2024/25, the only seasons where every one is published. They
  are missing elsewhere, and still miss one-off matches (Community Shield,
  Supercopa, UEFA Super Cup, Club World Cup) and European qualifiers.
- **Crowd status** for 88 matches is `unknown`, and some rules are medium or
  low confidence.
- **Away-goals rule** decided UCL ties until 2020/21; it matters only if
  tie-level outcomes are analysed.
