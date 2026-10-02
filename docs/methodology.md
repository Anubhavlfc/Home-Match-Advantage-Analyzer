# Methodology decisions (proposed)

These are definitions to be agreed before the analysis phases. They describe
how numbers will be computed, not what the results are.

## Home Advantage Index

No new composite formula is invented. The project reports two established
measures side by side, plus the raw metrics behind them.

**1. Points-share home advantage (descriptive).** Following Pollard (1986),
for a group of matches:

```
HA_points = home points / (home points + away points)
```

0.5 means no advantage. This is easy to interpret and comparable over time,
but it is only fair in a balanced schedule where every team plays every
other team home and away (a full league season). It is therefore used for
EPL and La Liga at competition-season level. For a single team, the
equivalent is the team's home points per match minus its away points per
match, which is also only meaningful over full seasons.

**2. Strength-adjusted home advantage (inferential).** The home effect
estimated by a regression that controls for both teams' pre-match strength,
for example:

```
goal_difference_i = beta_0 + beta_1 * strength_difference_i + ... + error_i
```

where `beta_0` is the expected home goal-difference advantage between two
equally strong teams. An ordered-logit or logistic version gives the same
idea in terms of results. This works for unbalanced schedules (the Champions
League, part-seasons, crowd subsets) and is the version used for the COVID
comparison: interacting the home term with `crowd_status` measures how much
the home effect changes when crowds are absent.

The raw metrics (home/draw/away rates, points, goals, goal difference, shots,
cards) are always shown next to either index so the result stays
interpretable.

## Period definitions

| Period | Default rule | Overridden by |
|---|---|---|
| Pre-COVID | Matches before the March 2020 suspension | n/a |
| COVID disruption | 2019/20 matches after the restart; 2020/21 season | Match attendance, where known: matches with fans become `restricted` |
| Post-COVID | 2021/22 onward | Matches still under capacity caps become `restricted` |

`crowd_status` (normal / restricted / behind_closed_doors / unknown) is the
primary variable. `covid_period` is kept as a coarse secondary indicator.

## Leakage rules

All form and strength features are computed from matches strictly before the
current match date (`groupby(team).shift(1)` before rolling). Elo ratings are
recorded before the match updates them. Model evaluation uses a time-based
split: train 2016/17 to 2022/23, validate 2023/24, test 2024/25 to 2025/26.

## Reference

Pollard, R. (1986). Home advantage in soccer: a retrospective analysis.
*Journal of Sports Sciences*, 4(3), 237-248.
