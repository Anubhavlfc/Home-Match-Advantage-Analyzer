# Data quality: known and expected problems

## Checks the pipeline runs on every league season

Hard checks abort the run before anything is written to `data/interim`.
Warnings are written to `reports/data_quality/` and the data are kept exactly
as published.

| Check | Severity | What it catches |
|---|---|---|
| `row_count` | error | Missing or extra matches (expects n x (n-1)) |
| `unique_match_id` | error | Duplicate rows |
| `no_duplicate_fixtures` | error | Same home/away pairing twice |
| `double_round_robin` | error | A team without exactly n-1 home and n-1 away games |
| `dates_in_season_window` | error | Dates outside 1 July to 31 August of the following year (also catches day/month swaps) |
| `result_matches_goals` | error | Result or points inconsistent with goals (the source `FTR` is also checked on load) |
| `logical_bounds` | error | Negative counts, half-time goals above full-time, shots on target above shots |
| `goals_exceed_shots_on_target` | warning | More goals than shots on target. Possible with own goals, so listed for review rather than corrected |
| `scores_match_openfootball` | error | Any score that differs from the independent openfootball record, or a match present in only one source |
| `table_matches_published` | error | Final table rebuilt from match rows differs from the published table in `data/reference/final_tables.csv` |

## EPL 2016/17 result

All hard checks pass: 380 matches, 20 teams with 19 home and 19 away games
each, 380/380 scores identical in openfootball, and the rebuilt table equals
the published final table for every team (P, W, D, L, GF, GA, Pts). 1,064
goals in total, matching the published season total.

One warning: three matches have more goals than shots on target for one side
(Everton v Middlesbrough 2016-09-17, Watford v Hull City 2016-10-29, Crystal
Palace v Watford 2017-03-18). They are kept as published and flagged.

Full results: `reports/data_quality/EPL_1617_checks.csv` and
`EPL_1617_missingness.csv`.

## Expected problems in later stages

- **Team names** differ between every source ("Man United", "Manchester United",
  "Manchester United FC", "Man Utd"; "Ath Madrid", "Atlético Madrid",
  "Atletico Madrid"). Handled by `data/reference/team_aliases.csv`; unknown
  names stop the pipeline and list every missing alias.
- **Promoted/relegated clubs** change the team set every season; the round-robin
  check is per season, so this is expected and handled.
- **Postponed and rescheduled matches** (for example, 2019/20 games played after
  the restart) keep their original fixture but a later date. Rest-day and form
  features must use the actual played date.
- **Extra time and penalty shoot-outs** in UCL knockouts: `home_goals` must be
  the 90-minute score so that it is comparable with league matches. Extra-time
  and shoot-out outcomes will be stored in separate columns.
- **Away-goals rule** applied to UCL ties until 2020/21 and was abolished from
  2021/22; relevant if tie-level outcomes are analysed.
- **Neutral and relocated UCL venues**: finals; the 2019/20 Lisbon final-eight
  (quarter-finals onward); 2020/21 ties moved to third countries because of
  travel restrictions. The listed "home" team did not play at home in these
  matches.
- **Domestic relocations**: clubs occasionally play home matches elsewhere
  (stadium works, sanctions). These need a cited exceptions table before
  travel distance is calculated.
- **COVID crowd restrictions** were not uniform: some 2020/21 EPL matches
  had up to 2,000 (December 2020) or 10,000 (May 2021) fans, and La Liga
  stadiums reopened with capacity caps in 2021/22. A season-level dummy would
  misclassify these.
- **Mirror vs primary source**: until the primary host is reachable, domestic
  match statistics come from a mirror. Scores and tables are independently
  verified; shots, cards and fouls are not.
