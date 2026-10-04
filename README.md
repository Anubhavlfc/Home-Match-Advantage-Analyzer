# The Ultimate Home-Field Advantage Analyzer

An end-to-end data engineering, statistics and machine-learning project on
home-field advantage in elite European football: the English Premier League,
Spanish La Liga and UEFA Champions League, for the ten completed seasons from
2016/17 to 2025/26.

> **Status: Phase 2 (ETL) complete.** 8,972 matches across the three
> competitions and ten seasons are extracted, standardised and validated. No
> analysis has been run yet, so this README contains no findings.

## Research question

**How large is home-field advantage in elite European football, what factors
contribute to it, and has it changed over the last decade?**

The COVID-19 period, when matches were played behind closed doors or with
limited crowds, is treated as a natural experiment. The working hypothesis,
to be tested rather than assumed:

> Home teams normally gain an advantage from playing at their own stadium,
> and that advantage decreases when crowd attendance is removed or
> significantly restricted.

### Questions the project will answer
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
| Stadium coordinates and capacity | Wikidata (planned) | all |
| Attendance | under evaluation | all |

Full comparison, access methods, licences and gaps:
[`docs/data_sources.md`](docs/data_sources.md).

## ETL architecture

```
 sources ──► Bronze: data/raw/<source>/<comp>/      untouched files + _manifest.jsonl (URL, SHA-256, time)
                │  src/data/extract.py
                ▼
           Silver: data/interim/matches/            standardised schema, one row per match
                │  src/data/clean.py, src/data/validate.py
                ▼
           Gold:   data/processed/                  engineered features (Phase 3)

 data/reference/   curated, cited lookups (team aliases, published tables, stadiums...)
```

Every season passes structural, logical and cross-source checks before it
is written to the silver layer; see [`docs/data_quality.md`](docs/data_quality.md).
The schema is documented in [`docs/schema.md`](docs/schema.md), and the
proposed Home Advantage Index and COVID period definitions are in
[`docs/methodology.md`](docs/methodology.md).

## Repository structure

```
├── config/config.yaml        seasons, competitions, source URLs
├── data/{raw,interim,processed,reference}/
├── docs/                     sources, schema, data quality, methodology, roadmap
├── src/
│   ├── config.py, schema.py, pipeline.py
│   └── data/                 extract.py, clean.py, ucl.py, validate.py, load.py
├── reports/data_quality/     per-season check results and missingness
└── tests/                    unit tests + EPL and UCL integration tests
```

Folders for features, models, visualisation, notebooks and the dashboard are
created as each phase starts.

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

# Or one competition-season (EPL, LALIGA, UCL)
python -m src.pipeline --competition UCL --season 2020/21

# Tests (the integration test downloads the season if needed)
pytest
```

## Roadmap

Foundation, ETL, feature engineering, EDA, statistical modelling, machine
learning, then presentation. Details: [`docs/roadmap.md`](docs/roadmap.md).

## Limitations (known so far)

- Attendance is not available from an integrated source; `crowd_status` comes from a hand-compiled, confidence-rated table of COVID-era restrictions.
- Champions League match statistics (shots, cards, fouls) are not available from the free sources checked.
- Penalties and possession are not available for any competition and are out of scope.
- Domestic match statistics currently come from a mirror of football-data.co.uk; scores and tables are independently verified, shots and cards are not.
- Rest days are approximate because domestic cups and other European competitions are not in the dataset.

## Methodological rules

No fabricated or silently imputed values; no future information in features;
association is not described as causation; neutral venues are handled
separately; team strength is controlled for whenever home advantage is
evaluated.
