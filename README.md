# The Ultimate Home-Field Advantage Analyzer

An end-to-end data engineering, statistics and machine-learning project on
home-field advantage in elite European football: the English Premier League,
Spanish La Liga and UEFA Champions League, for the ten completed seasons from
2016/17 to 2025/26 (8,972 matches).

**Headline:** between two equally strong teams, playing at home is worth
about **+0.30 goals per match** in the Premier League (more in La Liga and
the Champions League). When stadiums were empty during COVID-19 that edge
fell by about **two-thirds**. Before kick-off, though, team strength explains
almost everything a model can predict.

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py      # interactive dashboard, runs straight after a clone
```

The full story for a presentation is in
[`reports/final_report.md`](reports/final_report.md).

## Research question

**How large is home-field advantage in elite European football, what factors
contribute to it, and has it changed over the last decade?**

The COVID-19 period, when matches were played behind closed doors or with
limited crowds, is treated as a natural experiment. The working hypothesis,
to be tested rather than assumed:

> Home teams normally gain an advantage from playing at their own stadium,
> and that advantage decreases when crowd attendance is removed or
> significantly restricted.

### Questions the project answers
1. How much of an advantage does playing at home provide?
2. Has home advantage become weaker or stronger since 2016/17?
3. Did empty stadiums materially reduce home advantage?
4. Did home teams' underlying performance (shots, shots on target, corners) change without supporters?
5. Did referee-related outcomes (fouls, cards, penalties) change when crowds disappeared?
6. Was the COVID effect different in the Premier League, La Liga and Champions League?
7. Which clubs consistently get the largest measurable home advantage, after accounting for team strength?
8. Does longer away-team travel increase home advantage?
9. Does a rest advantage improve the home team's chance of winning?
10. Is attendance still associated with home success after accounting for team strength?
11. What distinguishes "fortress" teams from teams that perform similarly home and away?
12. Which factors explain home-win probability most strongly?

## Why home advantage matters

Home advantage is one of the most consistent effects in sport, but its causes
(crowd support, travel, familiarity, referee decisions) are hard to separate
because they normally occur together. Empty-stadium matches in 2020 and 2021
removed one of those factors at scale, which makes this decade unusually
informative.

## Data sources

| Data | Source | Competitions |
|---|---|---|
| Results and match statistics | [football-data.co.uk](https://www.football-data.co.uk/) (with a GitHub mirror as fallback) | EPL, La Liga |
| Results, stages, kick-off times, independent score check | [openfootball](https://github.com/openfootball) (public domain) | EPL, La Liga, UCL |
| Cup and Europa League fixture dates (for complete rest days) | openfootball | FA Cup, EFL Cup, Copa del Rey, Europa and Conference League, 2020/21 to 2024/25 |
| Stadium coordinates | hand-built reference table `data/reference/stadiums.csv` | all |
| Crowd conditions | cited table of COVID-era restrictions, `data/reference/crowd_restrictions.csv` | all |

Per-match attendance is not available from any free, stable source, so crowd
conditions come from documented league and government rules, with a
confidence rating and `unknown` where the rules are unclear. Full comparison,
access methods, licences and gaps: [`docs/data_sources.md`](docs/data_sources.md).

## ETL architecture

```
 sources ──► Bronze: data/raw/<source>/<comp>/      untouched files + _manifest.jsonl (URL, SHA-256, time)
                │  src/data/extract.py
                ▼
           Silver: data/interim/matches/            standardised schema, one row per match
                │  src/data/clean.py, src/data/validate.py
                ▼
           Gold:   data/processed/matches_gold.csv  engineered features, one row per match
                │  src/features/build.py
                ▼
           Analysis: reports/tables, reports/figures, dashboard/data

 data/reference/   curated, cited lookups (team aliases, published tables, stadiums...)
```

Every season passes structural, logical and cross-source checks before it
is written to the silver layer; see [`docs/data_quality.md`](docs/data_quality.md).
The schema is documented in [`docs/schema.md`](docs/schema.md), and the
Home Advantage Index and COVID period definitions are in
[`docs/methodology.md`](docs/methodology.md).

## Feature engineering

Every pre-match feature uses only matches dated before kick-off (rolling
windows are shifted; Elo is read before it is updated), and two warm-up
seasons (2014/15, 2015/16) give 2016/17 a history.

| Feature | How |
|---|---|
| Team strength | Elo rating (K = 20, scaled by goal difference; home term of 60 points fitted on the warm-up seasons) |
| Recent form | Points, wins, goals and goal difference over the previous five matches, plus venue-specific form |
| Rest days | Days since the previous match. Approximate (league and UCL only) for all seasons; complete (adds cups and Europa) for 2020/21 to 2024/25 |
| Travel distance | Haversine distance from the away club's ground to the actual venue |
| Crowd status | normal / restricted / behind closed doors / unknown, per match, from the restrictions table |
| Neutral venues | Finals, the Lisbon 2020 tournament and relocated ties (33 matches), excluded from home-advantage measures |

**Home Advantage Index.** The main measure is the *strength-adjusted home
excess*: the home side's result (win 1, draw 0.5, loss 0) minus the result
its pre-match Elo ratings predict with no home bonus. Zero means no home
advantage. Raw home win %, points and goals are always reported next to it.

## COVID natural experiment

Matches played behind closed doors in 2019/20 and 2020/21 remove the crowd
while leaving the stadium, the travel and the referee in place. The project
compares normal, restricted and empty-stadium matches with team strength held
equal, then asks whether the result survives tougher designs (season fixed
effects). It treats "behind closed doors" as the whole package of that
period, which also brought congested fixtures and five substitutes.

## Exploratory analysis

[`reports/eda.md`](reports/eda.md) answers research questions A to F with
one figure per question, 95% intervals throughout, and every number in
`reports/tables/eda_*.csv`.

## Statistical analysis

[`reports/statistics.md`](reports/statistics.md): proportion and chi-square
tests, OLS, logistic and ordered-logistic regressions with club-clustered
standard errors, a competition × crowd interaction model, a random-effects
model with shrinkage for clubs, and a Holm correction across 14 pre-specified
primary tests. Results are stated as associations.

## Machine learning

[`reports/ml.md`](reports/ml.md):
- **Model A**, a pre-match logistic regression for a home win, trained on
  2016/17 to 2022/23, tuned on 2023/24 and scored once on 2024/25 and
  2025/26. A three-way version (home, draw, away) uses the same protocol.
- **Model B**, an explanatory model with in-match statistics, never used
  for prediction.

## Team clustering

K-Means on 45 clubs' standardised home and home-versus-away features, with
k chosen by the elbow, the silhouette score and stability across random
starts, and a second run on the home-away gap features only. Clusters were
named only after inspecting their averages.

## Key findings

| # | Question | Answer |
|---|---|---|
| 1 | How much is home worth? | +0.30 goals per match between equal teams in the Premier League, +0.38 in La Liga, +0.44 in the Champions League (normal crowds). Significant everywhere. |
| 2 | Has it changed? | No trend over the decade with normal crowds (−0.001 home excess per season, Holm p = 0.76). |
| 3 | Did empty stadiums reduce it? | Yes: −0.20 goals per match behind closed doors with strength held equal (95% CI −0.31 to −0.08, Holm p = 0.006), about two-thirds of the advantage. With season fixed effects the direction holds (−0.14) but the interval crosses zero. |
| 4 | Did home performance change? | Yes: the home edge in shots, shots on target and corners shrank (shots on target −0.53 per match, p < 0.001). |
| 5 | Referee-related outcomes? | The away side's extra 0.22 yellow cards per match disappeared (Holm p = 0.015). Fouls not significant after correction. Not proof of referee bias. |
| 6 | Did competitions differ? | No significant difference (p = 0.66). The drop is significant in the Premier League and La Liga; the Champions League sample is too small. |
| 7 | Which clubs have the most? | None stands apart: club differences are not significant (Q p = 0.14), and no club's shrunk interval excludes the mean. |
| 8 | Does travel matter? | Weakly, domestic only (+0.03 goals per doubling of distance); does not survive correction. |
| 9 | Does rest matter? | No, including with complete cup and Europa fixtures for 2020/21 to 2024/25. |
| 10 | Attendance? | Not testable: no per-match attendance source. Crowd status is the proxy. |
| 11 | What makes a "fortress"? | Clusters split mainly by club quality; on home-away gaps alone they are halves of one continuum, not distinct types. |
| 12 | Which factors matter most? | Team strength (OR 2.3 per SD), then crowd status. The pre-match model reaches ROC-AUC 0.704 against 0.701 for Elo alone. |

## Dashboard

`streamlit run dashboard/app.py` opens an interactive dashboard with eight
sections: Overview, Home advantage over time, The COVID experiment,
Competition comparison, Team explorer, Travel and rest, Team clusters and
Statistical models. It reads only committed tables (`reports/tables`,
`dashboard/data`), so it works without rebuilding the data.

## Repository structure

```
├── config/config.yaml           seasons, competitions, source URLs
├── data/{raw,interim,processed,reference}/
├── docs/                        sources, schema, data quality, methodology, roadmap
├── src/
│   ├── data/                    extract, clean, validate, UCL parser, cup and Europa fixture dates
│   ├── features/                venues and travel, crowd status, rest, form, Elo; build.py
│   ├── analysis/                eda.py, stats.py
│   ├── models/                  logistic_model.py, clustering.py
│   └── visualization/           plots.py (report figures), dashboard_data.py
├── dashboard/                   app.py (Streamlit + Plotly) and its data
├── notebooks/                   04_eda.ipynb
├── reports/                     eda.md, statistics.md, ml.md, final_report.md, figures/, tables/
└── tests/                       unit, integration and dashboard smoke tests
```

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Extract, clean and validate everything -> data/interim/matches_all.csv
python -m src.pipeline --all

# Build engineered features -> data/processed/matches_gold.csv
python -m src.features.build

# Exploratory analysis -> reports/tables, reports/figures (write-up: reports/eda.md)
python -m src.analysis.eda

# Statistical tests and models -> reports/tables/stats_*.csv (write-up: reports/statistics.md)
python -m src.analysis.stats

# Models -> reports/tables/ml_*.csv (write-up: reports/ml.md)
python -m src.models.logistic_model
python -m src.models.clustering

# Dashboard tables and app
python -m src.visualization.dashboard_data
streamlit run dashboard/app.py

# Or one competition-season (EPL, LALIGA, UCL)
python -m src.pipeline --competition UCL --season 2020/21

# Tests (the integration test downloads the season if needed)
pytest
```

## Limitations

- Attendance is not available from an integrated source; `crowd_status` comes from a hand-compiled, confidence-rated table of COVID-era restrictions.
- Champions League match statistics (shots, cards, fouls) are not available from the free sources checked.
- Penalties and possession are not available for any competition and are out of scope.
- Domestic match statistics currently come from a mirror of football-data.co.uk; scores and tables are independently verified, shots and cards are not.
- `home_rest_days`/`away_rest_days` count only league and UCL matches, so they are approximate. Complete rest days (`*_rest_days_all`, adding FA Cup, EFL Cup, Copa del Rey, Europa and Conference League dates) exist only for EPL and La Liga clubs in 2020/21 to 2024/25, the seasons openfootball fully covers.

- Crowd status is a rule-based proxy; 88 matches are `unknown`. The closed-doors period also changed schedules and substitutions, so its effect is not crowd noise alone.
- All results are associations from observational data.

## Future improvements

- Per-match attendance, to test attendance as a continuous variable (question 10).
- Expected goals (xG) or betting-market ratings as stronger measures of team strength.
- Complete rest days for every season, if cup and Europa fixture data for 2016/17 to 2019/20 and 2025/26 become available.
- Champions League match statistics, to extend the performance and referee-related analyses.

Phase-by-phase history: [`docs/roadmap.md`](docs/roadmap.md).

## Methodological rules

No fabricated or silently imputed values; no future information in features;
association is not described as causation; neutral venues are handled
separately; team strength is controlled for whenever home advantage is
evaluated.
