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

## Phase 4: EDA
Questions A to F, one figure per question.

## Phase 5: Statistical analysis
Proportion tests, chi-square, confidence intervals, effect sizes, strength-controlled regressions, COVID interaction model.

## Phase 6: Machine learning
Model A (pre-match logistic regression, time-based split), Model B (explanatory, in-match stats), K-Means team segmentation with elbow and silhouette selection.

## Phase 7: Presentation
Streamlit + Plotly dashboard, final figures, README findings.
