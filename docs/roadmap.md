# Implementation roadmap

Each phase ends with validated outputs before the next starts.

## Phase 1: Foundation (done)
- Repository structure, `.gitignore`, `requirements.txt`, `config/config.yaml`
- Source review and availability matrix (`docs/data_sources.md`)
- Match schema (`src/schema.py`, `docs/schema.md`)
- Known data-quality risks (`docs/data_quality.md`)
- Proposed index and period definitions (`docs/methodology.md`)
- Working, validated ETL for EPL 2016/17

## Phase 2: ETL for all competitions (done)
- EPL and La Liga, 2016/17 to 2025/26: 7,600 matches, every season reconciled with openfootball and the published final table.
- Champions League: parser for openfootball `cl.txt` (stages, legs, 90-minute vs extra-time scores, shoot-outs, `ucl_format`), 1,372 matches, structural checks per season.
- Venue exceptions for finals, the Lisbon 2020 tournament, 2020/21 relocations and displaced Shakhtar home games.
- Combined silver table `data/interim/matches_all.csv` (8,972 matches), validated after stacking.
- Decisions on gaps: penalties and possession dropped from scope; referee-level analysis EPL only; crowd status from documented restrictions instead of attendance (see `docs/methodology.md`).

## Phase 3: Feature engineering (done)
- 2014/15 and 2015/16 added as warm-up seasons (1,770 matches) so Elo, form and rest have history on the 2016/17 opening day. They never enter the gold table.
- `data/reference/stadiums.csv`: home ground and coordinates for every club, with dated rows for temporary moves (Tottenham at Wembley, Real Madrid at the Di Stéfano, Barcelona at Montjuïc, Levante at La Nucía, Everton's move, and UCL-only venues).
- `data/reference/crowd_restrictions.csv`: dated crowd rules giving `crowd_status` and its confidence; `covid_phase` and `covid_period`.
- Travel distance (Haversine, away club's ground to actual venue; also the home club's distance, non-zero for neutral and relocated games).
- Approximate rest days, last-5 form (points, win share, goals, goal difference, plus venue-specific form), pre-match Elo strength with a reliability flag.
- Gold table `data/processed/matches_gold.csv` (8,972 rows), validated for row count, uniqueness and leakage. UCL stage variables (`stage`, `stage_type`, `knockout_match`, `leg`, `ucl_format`) come from silver.
- Stadium capacity was skipped: without attendance it has no use.

## Phase 4: EDA (done)
- `src/analysis/eda.py` builds summary tables for questions A to F with 95% intervals (`reports/tables/eda_*.csv`); `src/visualization/plots.py` draws one figure per question (`reports/figures/eda_*.png`).
- Strength-adjusted home excess (actual score minus Elo expectation with no home term) reported next to raw rates.
- Findings written up in `reports/eda.md`; `notebooks/04_eda.ipynb` is a thin interactive companion.

## Phase 5: Statistical analysis (done)
- `src/analysis/stats.py`: one registry of tests (hypothesis, method, statistic, p, Holm-adjusted p for 14 pre-specified primary tests, CI, effect size) in `reports/tables/stats_tests.csv`, plus all model coefficients.
- Proportion and chi-square tests, strength-controlled OLS / logit / ordered logit with club-clustered errors, a season-fixed-effects robustness check, the crowd x competition interaction model, referee-outcome and match-statistic models, travel / rest / form, decade trend, and random-effects shrinkage of club home advantage.
- Write-up in `reports/statistics.md`.

## Phase 6: Machine learning (done)
- `src/models/logistic_model.py`: Model A (pre-match home win, train 2016/17-2022/23, tune on 2023/24, test once on 2024/25-2025/26; baselines; calibration; interpretable clustered-SE logit) and Model B (explanatory, in-match statistics, EPL and La Liga).
- `src/models/clustering.py`: K-Means on 45 clubs, k chosen by elbow, silhouette and stability, with a gap-only sensitivity specification.
- Follow-ups: Model A3 (home / draw / away, multinomial, scored with the ranked probability score) and complete rest days for 2020/21-2024/25 from openfootball cup and Europa files (`src/data/other_fixtures.py`), checked in the stats (M7c) and in a Model A rest check.
- Write-up in `reports/ml.md`.

## Phase 7: Presentation (done)
- `dashboard/app.py`: Streamlit + Plotly dashboard with eight sections (overview, trend, COVID experiment, competitions, team explorer, travel and rest, clusters, models). Reads only committed tables; `src/visualization/dashboard_data.py` builds `dashboard/data/team_seasons.csv`.
- README findings and `reports/final_report.md`, a slide-by-slide presentation story.
