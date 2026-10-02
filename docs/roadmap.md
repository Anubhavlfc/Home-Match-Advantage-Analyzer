# Implementation roadmap

Each phase ends with validated outputs before the next starts.

## Phase 1: Foundation (done in this change)
- Repository structure, `.gitignore`, `requirements.txt`, `config/config.yaml`
- Source review and availability matrix (`docs/data_sources.md`)
- Match schema (`src/schema.py`, `docs/schema.md`)
- Known data-quality risks (`docs/data_quality.md`)
- Proposed index and period definitions (`docs/methodology.md`)
- Working, validated ETL for EPL 2016/17

## Phase 2: ETL for all competitions
1. EPL 2017/18 to 2025/26: extend `team_aliases.csv` and `final_tables.csv`, run the same checks per season.
2. La Liga 2016/17 to 2025/26: same pipeline, `SP1` files, openfootball `es.1` cross-check.
3. Champions League: parser for openfootball `cl.txt` (stages, legs, 90-minute vs extra-time scores, shoot-outs, `ucl_format`); checks for 125 or 189 matches per season (119 in 2019/20) and group/league-phase completeness.
4. Decide on the attendance source (section 4 of `docs/data_sources.md`).
5. Combine into one silver table; validate row counts and duplicates after every merge.

## Phase 3: Feature engineering
Reference tables (stadiums with coordinates and capacity, neutral/relocated venues, crowd restrictions), then `crowd_status`, `covid_period`, `neutral_venue`, travel distance, approximate rest days, shifted rolling form, pre-match Elo strength, UCL stage variables. Output: gold table in `data/processed/`.

## Phase 4: EDA
Questions A to F, one figure per question.

## Phase 5: Statistical analysis
Proportion tests, chi-square, confidence intervals, effect sizes, strength-controlled regressions, COVID interaction model.

## Phase 6: Machine learning
Model A (pre-match logistic regression, time-based split), Model B (explanatory, in-match stats), K-Means team segmentation with elbow and silhouette selection.

## Phase 7: Presentation
Streamlit + Plotly dashboard, final figures, README findings.
