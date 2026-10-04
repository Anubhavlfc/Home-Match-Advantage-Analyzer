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

## Phase 3: Feature engineering
Reference tables (stadiums with coordinates and capacity, crowd restrictions), then `crowd_status`, `covid_period`, `neutral_venue`, travel distance, approximate rest days, shifted rolling form, pre-match Elo strength, UCL stage variables. Output: gold table in `data/processed/`.

## Phase 4: EDA
Questions A to F, one figure per question.

## Phase 5: Statistical analysis
Proportion tests, chi-square, confidence intervals, effect sizes, strength-controlled regressions, COVID interaction model.

## Phase 6: Machine learning
Model A (pre-match logistic regression, time-based split), Model B (explanatory, in-match stats), K-Means team segmentation with elbow and silhouette selection.

## Phase 7: Presentation
Streamlit + Plotly dashboard, final figures, README findings.
