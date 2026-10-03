# Home-field advantage in elite European football: final report

**Between two equally strong teams, playing at home is worth about +0.30
goals per match in the Premier League, and empty stadiums during COVID-19
took away about two-thirds of it.** Home advantage has not changed over the
decade, no club or competition stands apart, and before kick-off team
strength explains almost everything a model can predict.

This report tells the story in the order it is best presented. Each section
is one slide: the question, the figure that answers it, the takeaway, and
the caveat to say out loud. Full methods and every number are in
[`eda.md`](eda.md), [`statistics.md`](statistics.md) and [`ml.md`](ml.md);
the interactive version is `streamlit run dashboard/app.py`.

**Data.** 8,972 matches from the Premier League (3,800), La Liga (3,800)
and Champions League (1,372), 2016/17 to 2025/26. The 33 matches at neutral
venues (finals, the Lisbon 2020 tournament, relocated ties) are excluded
from home-advantage measures.

## 1. The question

How large is home advantage, what contributes to it, and has it changed?
The COVID-19 period is the key: for a year and a half, many matches were
played in empty stadiums, removing the crowd while keeping everything else.
The hypothesis, tested rather than assumed: home advantage shrinks without
crowds.

**Say:** raw home win rates mostly measure how good a club is. Every result
here compares equally rated teams, using pre-match Elo ratings built only
from earlier results.

## 2. Home advantage is real everywhere

![Results by competition](figures/eda_a_results.png)

Between equal teams with normal crowds, the home side is worth **+0.30
goals per match in the Premier League, +0.38 in La Liga and +0.44 in the
Champions League**. All three are significant after correcting for multiple
tests (Holm p < 0.001). Over 19 home matches, +0.30 goals adds up to about
6 goals of goal difference a season.

**Caveat:** per match the effect is small next to the noise of a single
result, which is why ten seasons are needed to measure it well.

## 3. It has not trended up or down

![Trend by season](figures/eda_b_trend.png)

With normal crowds, the strength-adjusted home advantage changes by −0.001
per season (95% CI −0.004 to +0.002, Holm p = 0.76). The only dip is in the
empty-stadium seasons.

## 4. The empty-stadium experiment

![Crowd conditions](figures/eda_c_crowd.png)

Home sides won **46.2%** of matches with normal crowds and **41.2%** behind
closed doors. With team strength and competition held equal, the home
goal-difference edge was **0.20 goals per match lower** behind closed doors
(95% CI −0.31 to −0.08, Holm p = 0.006), about two-thirds of the normal
advantage. The odds of a home win were 22% lower.

**Caveat, say it plainly:** with season fixed effects, which compare only
matches within the same season, the estimate keeps its direction (−0.14)
but its interval crosses zero. Empty stadiums came with congested fixtures,
five substitutes and no travelling fans, so "behind closed doors" means that
whole package, and a season-level explanation cannot be ruled out.

## 5. Home teams played differently, and the cards changed

![Performance by crowd](figures/eda_c_performance.png)

Without crowds the home edge in shots, shots on target and corners shrank
(shots on target −0.53 per match, p < 0.001). The away side's extra yellow
cards, 0.22 per match with crowds, **disappeared** (Holm p = 0.015). The
foul change does not survive correction.

**Caveat:** these are differences in referee-related outcomes, not proof of
referee bias. Away teams may also have defended less without a hostile
crowd, and the data cannot separate the two.

## 6. The drop was similar in every competition

![Crowd effect by competition](figures/stats_crowd_by_competition.png)

The closed-doors drop is significant in the Premier League (−0.24 goals)
and La Liga (−0.18), and the three competitions are not significantly
different (p = 0.66). The Champions League had only 83 closed-doors home
matches, too few to say.

## 7. No club is a proven fortress

![Clubs after shrinkage](figures/stats_clubs.png)

The raw club ranking (Mallorca and Atlético Madrid at the top) is mostly
sampling noise. Club differences are not significant (Cochran's Q p = 0.14),
and after shrinkage no club's interval excludes the average. K-Means agrees:
its clusters split clubs mainly by quality, and on home-away gaps alone the
two groups are halves of one continuum, not distinct types.

## 8. Travel and rest barely matter

![Travel and rest](figures/eda_g_travel_rest.png)

Longer domestic away trips go with slightly better home results (+0.03
goals per doubling of distance), but this does not survive the
multiple-testing correction, and there is no effect in the Champions League.
Rest shows nothing once strength is controlled, including when rest days are
rebuilt with every cup and Europa fixture for 2020/21 to 2024/25.

## 9. Before kick-off, strength is almost everything

![Model A effects](figures/ml_model_a_effects.png)

The pre-match model (logistic regression, trained on 2016/17 to 2022/23,
tuned on 2023/24 and scored once on 2024/25 and 2025/26) reaches **ROC-AUC
0.704 and 65% accuracy**, against 0.701 for Elo alone and 55% for always
guessing "no home win". Its probabilities are well calibrated. A stronger
home side (one standard deviation, 186 Elo points) has more than double the
odds of winning; empty stadiums cut the odds by about a quarter; form, rest
and travel add nothing beyond Elo.

A three-way version (home, draw, away) gives honest probabilities for all
three results, but a draw is almost never the single most likely outcome,
which is normal for football models.

## 10. What this does and does not show

**Shows:**
- Home advantage is a stable, measurable effect of about a third of a goal
  per match between equal teams.
- Removing crowds coincided with losing most of it, together with less
  home attacking dominance and the disappearance of the away side's extra
  yellow cards.

**Does not show:**
- That crowds alone cause home advantage. The empty-stadium period changed
  other things too, and the strictest design cannot rule out a season-level
  explanation.
- Referee bias. The card pattern fits crowd influence on referees, but it
  also fits a change in how teams played.
- Which clubs have a special home advantage. Ten seasons are not enough to
  separate clubs from the average.

**Limitations:** no per-match attendance (crowd status is a rule-based
proxy), no Champions League match statistics, no penalties or possession,
and approximate rest days outside 2020/21 to 2024/25.
