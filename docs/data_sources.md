# Data sources

Status of every candidate source for EPL, La Liga and the Champions League,
2016/17 to 2025/26. "Verified" means the file or endpoint was actually
downloaded and inspected on the date shown; anything else is marked as
unverified and must be checked before the pipeline depends on it.

Date of this review: **2026-10-02**.

## 1. Summary

| Need | Chosen source | Status |
|---|---|---|
| EPL and La Liga results + match stats | football-data.co.uk (primary), Datahub `football-datasets` mirror (fallback) | Mirror verified for all 10 seasons, both leagues (380 rows each). Primary host blocked from the build sandbox; works from a normal network. |
| Independent score cross-check (domestic) | openfootball `football.json` | Verified EPL 2016/17: 380/380 scores identical to football-data. |
| Champions League results, stages | openfootball `champions-league` | Verified all 10 seasons. 125 matches per season to 2023/24 (119 in 2019/20), 189 from 2024/25 (league phase). No venues, no match stats. |
| Attendance (all competitions) | Not yet secured | See section 4. This is the main data gap. |
| Stadium coordinates and capacity | Wikidata (SPARQL, CC0) + manual reference table | Not yet built (Phase 3). |
| Neutral / relocated UCL venues | Curated reference table with citations (`venue_exceptions.csv`) | Built: 33 matches (finals, Lisbon 2020, 2020/21 relocations, displaced Shakhtar home games). |
| COVID crowd restrictions | Match-level attendance where available; otherwise documented league/government rules | Not yet built (Phase 3). |

## 2. Source details

### football-data.co.uk
- **What**: one CSV per league per season. EPL file `E0`, La Liga file `SP1`.
- **Access**: `https://www.football-data.co.uk/mmz4281/{season_code}/{division}.csv`, no key, no documented rate limit. Download politely (one request per file).
- **Variables used**: `Date`, `Time` (from 2019/20), `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, `FTR`, `HTHG`, `HTAG`, `Referee` (EPL only), `HS`, `AS`, `HST`, `AST`, `HF`, `AF`, `HC`, `AC`, `HY`, `AY`, `HR`, `AR`.
- **Not provided**: attendance (for these seasons), penalties, possession, venue, Champions League.
- **Licence**: free for personal and research use; attribute the site. Betting-odds columns exist but are not used.
- **Known quirks**: dates are `dd/mm/yy` in older files and `dd/mm/yyyy` in newer ones; some files are Latin-1 with trailing empty columns. Both handled in `src/data/clean.py`.

### Datahub `football-datasets` (mirror)
- **What**: GitHub mirror of football-data.co.uk league files (`datasets/football-datasets`), same column names, betting columns removed.
- **Access**: `https://raw.githubusercontent.com/datasets/football-datasets/main/datasets/{premier-league|la-liga}/season-{code}.csv`.
- **Why it is here**: the primary host refused connections from the cloud sandbox used to build this project. The extractor tries the primary first and records in `data/raw/_manifest.jsonl` which source was actually used, and files are stored under the source's own folder so a mirror is never mistaken for the primary.
- **Limitation**: a third-party copy. The EPL 2016/17 file reproduced the published final table exactly and agreed with openfootball on every score; match statistics cannot be cross-checked the same way. Re-run with `--refresh` on a network that reaches football-data.co.uk to switch to the primary.
- **Columns**: identical in all 10 seasons for both leagues, except `Referee`, which is empty for La Liga (checked 2016/17, 2020/21, 2025/26).

### openfootball (`football.json`, `champions-league`)
- **What**: community-maintained results in plain text / JSON. Public domain (CC0).
- **Access**: `raw.githubusercontent.com/openfootball/...`, no key.
- **Variables**: date, kick-off time, teams, full-time and half-time score, round/stage. UCL text marks extra time (`a.e.t.`) and penalty shoot-outs, which must be parsed so `home_goals` stays the 90-minute score.
- **Coverage (verified)**: UCL main tournament only (group or league phase onward; qualifying rounds are not included). The 2019/20 knockout rounds after March 2020 are single matches (Lisbon "final eight"), so 119 matches instead of 125.
- **Not provided**: venues (no `@ stadium` annotations in any of the 10 UCL files), attendance, match statistics.

### football-data.org API (considered, not used yet)
- Free tier lists Premier League, La Liga and Champions League. Unauthenticated clients get 100 requests/day and only the competition list; a free key is needed for matches.
- **Unverified**: how many past seasons the free tier returns and whether `venue`/`attendance` are populated for 2016/17 onward. The API documentation says null is used for unknown values such as attendance. Worth testing with a free key as a possible UCL venue/attendance source.

### FBref (considered, not used yet)
- Historically the easiest free source of per-match attendance, venue, referee and possession for all three competitions.
- Opta ended its data agreement with FBref in January 2026 and advanced stats were withdrawn ([Awful Announcing](https://awfulannouncing.com/soccer/sports-reference-pulls-advanced-data-agreement-violation-dispute.html)). **Unverified** whether basic match-report fields (attendance, venue) are still published for past seasons.
- Sports Reference's terms restrict automated scraping (rate-limited, no bulk redistribution). If used, it would be a low-rate, cached, attributable extraction, not a dependency of the core pipeline.

### Other candidates
- **Transfermarkt**: per-match attendance for all three competitions. Scraping is against its terms; community dumps on Kaggle exist but licensing varies by uploader and must be checked per dataset.
- **Wikidata**: stadium coordinates, capacity, city, country. CC0 licence, SPARQL endpoint. Planned for `data/reference/stadiums.csv`.
- **UEFA.com match pages**: official UCL attendance and venue. No public API; scraping would be fragile. Candidate for a small, manually cited reference table (finals and relocated matches only).

## 3. Variable availability matrix

`Y` = available from an integrated or verified source, `P` = partial, `N` = not available from any source checked so far, `?` = unverified.

| Variable | EPL | La Liga | UCL | Source |
|---|---|---|---|---|
| Date, teams, full-time score | Y | Y | Y | football-data / openfootball |
| Half-time score | Y | Y | Y | football-data / openfootball |
| Kick-off time | Y | Y | Y | openfootball (fills football-data gaps) |
| Stage / round / leg | n/a | n/a | Y (derived) | openfootball |
| Extra time, shoot-outs | n/a | n/a | Y | openfootball |
| Shots, shots on target | Y | Y | N | football-data |
| Corners, fouls, yellow, red cards | Y | Y | N | football-data |
| Referee | Y | N | N | football-data |
| Penalties awarded | N | N | N | out of scope (decided in Phase 2) |
| Possession | N | N | N | out of scope (decided in Phase 2) |
| Attendance | ? | ? | ? | see section 4 |
| Venue (actual stadium) | derived* | derived* | derived* | *home club's ground (Phase 3) + exceptions table |
| Stadium capacity, coordinates | planned | planned | planned | Wikidata + manual |
| Rest days | approx. | approx. | approx. | derived from integrated fixtures only |
| Form, strength (Elo) | derived | derived | derived | from results |

## 4. Variables at risk across the full ten seasons

1. **Attendance**. No integrated source yet; the planned fallback is described in `docs/methodology.md`. Without it, `crowd_status` can only be assigned from documented restriction rules (for example, EPL behind closed doors from the June 2020 restart, small crowds allowed in December 2020 and May 2021). That is a legitimate fallback but coarser than the match-level analysis the project wants. Securing attendance is the first decision for Phase 2.
2. **Champions League match statistics**. Shots, cards, fouls and corners are not available for UCL from any free, stable source checked. The referee and in-match mechanism analysis (Questions C and D) will therefore be EPL and La Liga only unless a source is added.
3. **Penalties and possession**. Not available in the integrated sources for any competition. Decision (Phase 2): dropped from scope rather than scraped, because neither is central to the research questions; the columns stay in the schema as missing.
4. **Referee for La Liga**. Column present but empty. Decision: referee-*outcome* analysis (fouls, cards by side) still covers both leagues; analysis by individual referee is EPL only.
5. **Rest days**. Domestic cups and other European competitions are not in the dataset, so rest days for clubs in the FA Cup, Copa del Rey, Europa League and so on are overestimated. Will be labelled as an approximation.
6. **UCL venues**. openfootball has no venues, so neutral venues (finals, 2019/20 Lisbon tournament, 2020/21 relocated ties) need a hand-curated, cited reference table.
