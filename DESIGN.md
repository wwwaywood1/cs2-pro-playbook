# Design

cs2-pro-playbook turns professional CS2 demos into three things regular players can use:

1. **Team playbooks**: how a team sets up and attacks on each map, with sample sizes.
2. **Player profiles**: role hints backed by the metric that produced them.
3. **A lineup library**: grenades pros actually throw, ranked by usage, each with a
   `setpos/setang` practice command.

Existing tools either replay a single demo (2D viewers), report individual stats
(Leetify, Scope.gg), or sell raw aggregation to pro teams (Skybox, Noesis). The gap this
project fills is the **translation layer**: conclusions computed from many pro demos,
presented so a regular player can act on them. It is open source and static, so it costs
nothing to host.

## Architecture

```
HLTV.org match pages ──(downloaded by hand)──> ~/Downloads/*.rar|zip
   │ scripts/refresh.sh: import_hltv.py (extract, dedupe, map pool) ──> data/raw/hltv/<archive>/*.dem
   │                     register_hltv_dates.py (archive -> HLTV match, exact date)
   │                     archive_downloads.py   (original archives -> external drive)
cs2povarchive (HF) ──fetch──> data/raw/cs2povarchive/<event>/<hltv id>-<slug>/*.dem   (legacy source)
                              │ parse.py      (awpy 3.1: one demo -> normalized tables, 1 Hz frames, eye yaw)
                              │ semantics.py  (team_rounds, player_rounds)
                              ▼
                       data/parsed/<table>/<demo_id>.parquet
                              │ export.py     dedupe.py (cross-source duplicates), dates.py (event ranges,
                              │               config/match_dates.csv), winprob.py, replay.py, radar6.py,
                              │               heatmap.py, zones.py, tactics.py, insights.py, ct_patterns.py, ai_lab.py
                              ▼
                       data/site/**.json  ──sync──> web/public/data  ──> static site
```

`data/raw` may be a symlink to an external drive (`config/storage.toml`, `scripts/relocate_raw.py`).

All analysis is precomputed offline; the website only reads JSON. Each stage is rerunnable
on stored output: `export` never touches demos, and `parse` skips demos already parsed.
After editing `config/maps/*.toml`, `python -m playbook relabel [maps]` re-applies the
callout mapping to the stored tables and rebuilds the semantic tables (no demo needed).

| Module | Role |
|---|---|
| `playbook/parse.py` | One demo to tables; teams, sides, rounds, positions (1 Hz, eye yaw), kills, plants, grenades |
| `playbook/multipart.py` | Recordings split into parts (`-p1`, `-p2`) parsed as one game |
| `playbook/utility.py` | Grenade thrower recovery; callout lookup for arbitrary points |
| `playbook/semantics.py` | Round semantics (labels per round x team, and per round x player) |
| `playbook/dedupe.py` | Cross-source duplicates (map + teams + per-round winner sequence); event slug of a demo |
| `playbook/dates.py` | Match dates: exact (`config/match_dates.csv`), else HLTV id interpolation within a finished event, else event start |
| `playbook/export.py` | Site JSON: team/player profiles, lineup library, tactics, heatmaps, replays, WP timelines (written fresh, swapped in) |
| `playbook/winprob.py` | Round win-probability model (out-of-fold), WPA per action (drift-adjusted), recipe WP swing |
| `playbook/replay.py` | 2D replay per round (positions, yaw, events, WP, territory) |
| `playbook/radar6.py` | Six-axis player radar with peer percentiles |
| `playbook/heatmap.py` | Team heatmaps per player: presence, holding, shots, kills, deaths, utility landing by type (cleaned frames) |
| `playbook/zones.py` | Per-player summaries on the cleaned frames: zones, holding spots, fights, utility spots; team setup |
| `playbook/tactics.py` | Landing spots, T plans (commit, tempo, split, lurk, fake), execute recipes, CT setups; site summaries |
| `playbook/insights.py` | Team insight facts (tested against the other teams, FDR-controlled) for the written summaries |
| `playbook/ct_patterns.py` | CT defence formations (clustering on positions), economy association, team fingerprints |
| `playbook/ai_lab.py` | AI Lab: grouped Shapley explanations of the WP model, attention-style CT examples |
| `playbook/hltv.py` | Parsers for HLTV results/match/team pages saved from a browser; tier-1 filter; download planning |
| `playbook/fetch.py` | Lists and downloads demos from Hugging Face matching `config/targets.toml` (legacy source) |
| `playbook/store.py` | Parquet storage, one file per demo per table |
| `config/maps/*.toml` | Callout to region to lane mapping, radar transform, per map |
| `config/spots/*.toml` | Optional human names for landing spots, matched by position (survive re-clustering) |
| `config/team_aliases.csv`, `player_aliases.csv` | In-game clan names / alternate accounts to canonical identities |
| `config/events.json`, `match_dates.csv`, `hltv_archives.json` | Event date ranges; exact dates; which HLTV match each archive is |
| `config/hltv.toml`, `storage.toml`, `site.toml` | Download scope (2026, tier-1); where bulky data lives; showcase teams |

## Data sources

- **HLTV.org** GOTV archives (`<event>-<team1>-vs-<team2>-<bo3|map>-<id>.rar`), downloaded by hand from
  match pages: the main source (about 580 of 745 maps). HLTV's robots.txt disallows automated access to
  `/download/demo`, so the tools never request HLTV; they plan, list the links and ingest what was downloaded.
  Scope in `config/hltv.toml`: matches since 2026-01-01, tier-1 events, most popular first.
- **cs2povarchive/cs2-demos** (Hugging Face, Apache-2.0): IEM Cologne Major 2026 and CAC 2026 GOTV demos
  (about 165 maps), layout `<event>/<hltv_match_id>-<slug>/<team1>-vs-<team2>[-mN]-<map>[-pK].dem`.
- **Match start times**: HLTV match pages and bo3.gg (cross-checked: median difference 0 min, no day
  mismatches over 159 matches); stored per HLTV match in `config/hltv_archives.json`.
- **awpy test fixtures** (github.com/pnxenopoulos/awpy-fixtures): used for tests.
- **awpy-data** releases: radar images and world-to-radar transforms (release 2000933).
- Credits and licences: `docs/CREDITS.md`.

## Tables (data/parsed)

Every table has `demo_id` and, where relevant, `round_num`. Knife rounds are dropped.
Sides are `T` / `CT`. `t_s` is seconds since freeze end of that round.

| Table | Grain | Key columns |
|---|---|---|
| matches | demo | map, team_a/b, score_a/b, winner, n_rounds, tick_rate, build_num |
| players | demo x player | steamid, name, team |
| rounds | round | half, ct_team, t_team, winner_team, reason, dur_s, score_ct_before, score_t_before |
| economy | round x team | side, buy_type (pistol/eco/force/full), equipment_value |
| loadouts | round x player | primary/secondary weapon, armor, kit, bomb, grenades held, money |
| positions | round x second x player | x, y, z, place (callout), region, lane, health, alive |
| kills | kill | t_s, is_opening, is_post_round, attacker/victim team, side, place, region, xyz, weapon, headshot, is_trade |
| plants | plant | t_s, site (A/B), place, planter |
| utility | grenade | type, throw/pop tick and t_s, thrower, throw xyz + place + pitch/yaw, movement at release, land xyz + place/region/lane, matched |
| shots | gun fire event | t_s, is_post_round, shooter steamid/team/side, xyz, pitch/yaw, weapon, scoped (knives, grenades, C4, zeus excluded) |
| team_rounds | round x team | see Round semantics |
| player_rounds | round x player | see Round semantics |

## Round semantics (definitions)

- **Team / side**: a player's team is the canonical clan name (`team_aliases.csv`). Side is
  read per round from the team number at freeze end, never from the parser's "last side".
- **Opening duel**: the first kill of a round between the two teams, before round end.
- **Early utility**: smokes, flashes and molotovs that pop in the first 15s (default
  map-control utility).
- **Execute window**: after 15s, the 10s window in which a team's smokes, flashes and
  molotovs *pop* most densely. Start of the window is the execute time; the dominant
  landing lane is the execute lane. "No clear execute" if fewer than 3 grenades fall in it.
- **Shape@N s**: lanes of the team's living players N seconds after freeze end, for
  example `A2 M2 B1` (S = T spawn, C = CT spawn). A coarse setup fingerprint.
- **dist_to_team_30s**: mean 2D distance to living teammates 30s in; high on T side means lurking.
- **site_entry_rank**: T-side order of first arrival on a bombsite region (1 = first in).
- **Lanes vs regions**: each map config maps callout to region (for example `A_APPROACH`,
  `A_SITE`) and region to lane (`T_SPAWN`, `A`, `MID`, `B`, `CT_SPAWN`).

### Grenade thrower recovery

GOTV demos can omit the thrower on grenade projectiles; in the Mirage test demo awpy
reports none at all. Each trajectory's first sample is matched to the `weapon_fire` event
that threw it: same grenade class, fired 0 to 32 ticks earlier, nearest in 2D (at most 250
units), one-to-one greedy. The matched event also gives the release position and view
angles. Result: 314 of 319 grenades matched on Mirage, 587 of 587 on Inferno.

### Callouts for arbitrary points

Kill, plant and landing points get a callout from the nearest recorded player position
(z weighted x2, 16-unit grid). Grenades that pop mid-air fall back to a 2D lookup.

### Role hints (heuristic)

Relative to teammates on the same map. Each hint carries the metric and value behind it.

| Role | Rule |
|---|---|
| awper | AWP at freeze end in at least 40% of rounds, or the team's top AWP user from 15% |
| a_anchor / b_anchor / mid_ct | same CT lane at 15s in at least 60% of CT rounds |
| lurker | highest T-side dist_to_team_30s on the team and at least 1.25x the team median |
| entry | highest T-side first-into-site rate on the team, at least 0.25 |
| support | most utility thrown per round on the team |

Checked against `validation/pro_roles.csv` (GPT-05: 155 players, roles at the Cologne Major
with sources), per player and map on Mirage and Inferno: **awper** 49/50 found, no false
positives (the old 40% rule found 29). **lurker** (distance rule) is precise but misses most:
21 found, 2 false, 54 missed, because the table counts secondary lurk roles and many lurkers
stay near the team at 30 s; the per-round `T.lurk_share` did not do better (best 22 found /
18 false). Entry, anchor and support hints are not yet checked (the table has 2 entries).

### Lineup clustering

Grenades of the same side and type are one lineup if released within 48 units and landing
within 120 units of the running cluster centre. The representative throw is the member
closest to the centre; its position and angles produce
`setpos x y z;setang pitch yaw 0`. Technique is jump, run (speed at least 100), crouch,
walk or stand, taken at the release tick.

### Heatmaps and player summaries (playbook/heatmap.py, playbook/zones.py)

Purpose: a site feature (team -> map -> T/CT -> players, each player in a fixed colour)
and the cleaned base that tactic analysis and teaching material are built on.

Cleaning: gun rounds of the player's team only (full/force buys), living time only,
live round time only (no freeze time, no post-round), and presence/holding skip the first
5 s (walking out of spawn). Values are per round played on that side.

Grid: 64 x 64 over the 1024 px radar (16 px per cell); Nuke-style maps put z below
`lower_level_max_z` on a second level. Phases: `post` (after the plant; retake for CT)
takes precedence, then `early` (first 20 s), then `mid`.

| Layer | Counts |
|---|---|
| presence | living seconds (positions are sampled once per second) |
| holding | living seconds moving less than 40 units in that second (holding an angle) |
| shots | gun fire events at the shooter |
| kills / deaths | at the attacker / victim |
| smoke / flash / molotov / he | grenades at their landing point (throw spots belong to the lineup library) |

Colours: per team, players are ordered by rounds played over all maps, then name; the
first five get red, blue, purple, green, orange, so a player keeps his colour on every
map and side. Each player is shaded light to deep relative to his own peak; the
"owner" mode colours each cell by the player with the highest relative value.
`web/src/heatmap.ts` reproduces `scripts/heatmap_preview.py` (checked: same visible
cells, alpha within 1/255).

Summaries per player and side (zones.py): callout shares per phase and main lane;
holding spots (clusters of held seconds within 150 units: seconds per round, rounds held,
typical time); fights by callout (kills, deaths, openings); utility per round by type and
the landing spots he uses most, linked to the lineups he throws them from. Utility spot
summaries include `level` (0 upper, 1 lower), matching the landing library and grids. Per team and
side, `setup` lists which players are mainly on which lane in each phase.

### Tactic identification (playbook/tactics.py)

Computed per map over all its demos; the exported numbers use gun rounds only.

- **Landing spots**: grenades of one side and type landing in the same place, whatever the
  throw position (density-seeded clustering, radius 160 units for smokes and molotovs,
  260 for flashes and HE; at least 4 throws from 2 matches). Each spot links to the
  lineups (throw positions) that hit it. Names come from `config/spots/<map>.toml` when
  present (matched by position), otherwise the callout plus `#n`.
- **T plans**, one per T round: `commit_s` (first second with two living T players on the
  bombsite core callout, or the plant), `target`, `tempo` (fast <= 40 s, late >= 75 s),
  `attempt` (the target, or for rounds without a commit the lane of the densest execute
  utility), `split`, `lurk`, `fake`, execute utility. Exact rules: `tactics.DEFINITIONS`,
  also written into `tactics.json`.
- **Execute recipes**: gun rounds hitting one site with similar smoke+molotov spot sets
  (average linkage on Jaccard distance, cut 0.6), merged when they share the same smoke
  core. Core spots appear in at least half of a recipe's rounds, options in 20-50%.
- **CT setups**: lanes at 20 s, forward players at 15 s (standing on callouts the T side
  holds in >= 60% of samples), stacks (a site lane with >= max(3, map median + 2) players),
  rotations after the T commit.

Validation: `validation/m2_blind_labels.csv` holds 20 rounds labelled blind from storyboards
(`scripts/storyboard.py`), then reviewed where they disagreed. `scripts/validate_m2.py`:
target 20/20, tempo 19/20, split 12/14, lurk 12/14, fake 18/20. Every remaining disagreement
is a borderline case explained in the `review` column. This is a human reading of the same
position data, not video ground truth; it needs to grow (especially for recipes).

### Team facts (playbook/insights.py)

Per team and map, `insights[]` in the team profile: differences from all other teams on
that map (tempo, site, split, lurk, fake; CT forward, stack, rotation), plus signature facts
(go-to execute, main lurker, default CT setup) above a minimum share. Each carries its numbers
and a template sentence in zh/en. Written analysis (M4) may rephrase these, never add to them.

A comparison is tested with the match as the unit (rounds of one match are not independent):
the variance of "team share minus everyone else's share" is, for each side, the larger of the
match-clustered (sandwich) variance and the design-effect variance under the null (intra-match
correlation estimated on the map). Only teams with at least 5 matches are tested; Benjamini-
Hochberg controls the false discovery rate at q = 0.10 across all team x fact tests of a map,
and a fact also needs a difference of at least 10 points. Facts export `matches`, `z`, `p`, `q`.
Under shuffled team labels this yields 0.07 facts per map (the old round-level |z| >= 2 rule:
about 8, close to the 11 observed).

### CT defence patterns (playbook/ct_patterns.py)

Pistol rounds excluded (economy `buy_type`); formations are clustered on position features
only (standardise, PCA, KMeans, K <= 6 per map). The economy x formation association is
reported afterwards (chi-square, Cramer's V) with a p-value from within-match block
permutations. Team fingerprints carry Wilson 95% intervals on a design-effect-adjusted n and
a `reliable` flag (>= 5 matches and >= 60 rounds).

## Site data contract (data/site, schema_version 1)

```
index.json                      { schema_version, generated_at, min_matches_reliable, maps: [{ map, display_name, n_matches, teams[], n_players, n_lineups }] }
<map>/meta.json                 { map, display_name, radar{pos_x,pos_y,scale[,lower_level_max_z]}, regions{region:lane}, callouts{callout:region} }
<map>/teams.json                [{ team, slug, n_matches, low_sample, win_rate_T, win_rate_CT }]
<map>/teams/<slug>.json         { team, slug, map, n_matches, low_sample, matches[], sides{T,CT}, economy[] }
<map>/players.json              [{ steamid, name, team, rounds{total,T,CT}, kpr, dpr, hs_pct, opening_*, awp_share, util_pr, T{...}, CT{...}, role_hints[] }]
player_quotes.json              { "<steamid>": { name, zh, en } } (owner text from config/player_quotes.json; empty by default)
asset_slots.json                { teams: [slug], players: [steamid] } (supplied web/public PNG files only)
heatmap_teams.json              [{ team, slug, n_matches, maps: [{ map, display_name, n_matches, rounds{T,CT}, players[], map_win_rate?, round_win_rate?, win_rate_T?, win_rate_CT?, all_rounds?, low_sample?, results?[] }] (most played first), roster: [{ steamid, name, color, rounds }] }]
<map>/heatmaps/baseline.json    { map, grid, cell_px, levels, layers[], phases[], sides[], n_colors, early_s, spawn_skip_s, hold_speed, min_reliable_rounds, rounds{T,CT}, per_round, data }
<map>/heatmaps/teams/<slug>.json { team, slug, map, n_matches, rounds{T,CT}, roster: [{ steamid, name, color, rounds, low_sample }], team_grid, players{steamid: { per_round, data }}, summary{steamid: {side: { zones, main_lane, holds, fights, utility }}}, setup{side: {phase: {lane: [names]}}} }
<map>/tactics.json              { map, definitions, t_overview: TTactics, ct_overview: CTTactics, recipes: [{ id, site, core[], options[], n_rounds, n_matches, teams[], won, win_rate, plant_rate, median_commit_s, tempo[], avg_flashes, split_rate, examples[] }], spots: [{ spot_id, side, type, place, label, name, radar_x, radar_y, level, n_throws, lineups[], in_recipes, ... }] }
<map>/lineups.json              [{ id, side, type, throw_place, land_place, land_region, land_lane, n_throws, n_matches, teams[], throwers[], round_win_rate, median_pop_t_s, technique, jump_share, throw{x,y,z,pitch,yaw,radar_x,radar_y}, land{x,y,z,radar_x,radar_y}, practice_cmd, example{demo_id,round_num,throw_tick} }]
```

- Hub metadata is additive within schema 1. `map_win_rate` counts maps won / maps played;
  `round_win_rate` counts rounds won / all rounds (not the mean of T/CT rates).
  Existing `rounds{T,CT}` in the heatmap index remains the gun-round sample; `all_rounds`
  is the separate all-buy sample. `results` holds every match record of the map, newest
  first; each carries `date`, `date_precision` (`exact` from `config/match_dates.csv`, `day`
  from HLTV-id interpolation within a finished event, `event` = event start) and `event`.
- `sides.T` includes `plant_sites`, `execute_timing` (`fast` before 35s,
  `default_then_execute` 35 to 65s, `late`, `no_clear_execute`), `execute_lane`,
  `setups_15s`, `setups_30s`.
- `sides.CT` includes `setups_15s/30s`, `plants_against`, `retake_win_rate`, `stack_rate_15s`.
- Team profiles carry `tactics.T` (tempo, target, attempt, avg_commit_s, split/lurk/fake rates,
  recipes used, lurkers) and `tactics.CT` (setups_20s, forward rate and players, stacks,
  rotation). Player profiles add `T.lurk_share` and `CT.forward_share`. Types: `web/src/types.ts`.
- Ranked lists use `{ value, rounds, share, won, win_rate }`.
- Setups and executes are computed on gun rounds only (`full` or `force` buys); pistol and
  eco rounds appear in `economy`.
- `radar_x/radar_y` are pixels on the 1024x1024 radar:
  `radar_x = (x - pos_x) / scale`, `radar_y = (pos_y - y) / scale`.
- Every profile has `n_matches`; below `min_matches_reliable` (5) the UI must show a
  low-sample warning.

`samples/site/` holds a real export (one match, Mirage) for frontend development.

## Validation status

- `tests/test_units.py`: pure functions, no demo needed.
- `tests/test_pipeline.py`: B8 vs Vitality, Mirage. Checks the final score (13-5),
  sides per half, cumulative score, 7 plants with sites, one opening kill per round,
  grenade attribution (at least 95% matched), 10 players at every round start, ZywOo as
  top AWP user and ropz as the most distant T-side player (both known roles).
- Manual: the frequent lineups plotted on the Mirage radar land in the expected places
  (T-spawn window and top-mid smokes, CT run-throw molotov to T ramp, B-site molotov to apartments).
- Inferno (9z vs PARIVISION 13-10) parses end to end with its region mapping (DS-01),
  and a FACEIT Mirage demo (16-14, with warmup) parses too.
- `tests/test_robustness.py` (GPT-01, see REVIEW.md): synthetic regressions for restored or
  incomplete round histories, substitutions, bots, missing clan names, same-tick opening
  kills, tick rate, and warmup-only players. Malformed demos are rejected with a
  `ValueError` rather than producing a wrong score.
- `web/e2e/smoke.py`: headless-browser check of every route on the sample data (filters,
  radar/card selection, copy button, low-sample banner, language switch, 375px layout,
  console errors).
- Batch 1 (Oct 2026): 65 Cologne Major demos (28 Mirage, 32 Inferno, 1 each of the other
  five maps) downloaded with `scripts/download_batch1.py` and parsed: 65/65 after one fix.
  1,400 rounds, 1.3M position samples, 31k grenades, 31 teams, exactly 10 players per demo.
  The fix: Legacy vs TYLOO had a non-playing slot (coach/admin, 0 HP at CT spawn all match)
  on team 3, which linked both rosters; entities never alive in a live round are now
  dropped (`_playing` in parse.py, regression test in test_robustness.py).

## Multipart recordings (GPT-03, playbook/multipart.py)

awpy 3.1.0 accepts `Demo([part1, part2, ...])` but its own validation rejects overlapping
rounds and live-round splits, so each file is opened separately, round ownership is chosen,
and the inputs are adapted to the existing parser before teams are resolved.

- Files must share a directory and stem after stripping `-pK`, with consecutive part numbers
  from 1; a supplied part discovers its siblings in the CLI; `(1)` duplicates are ignored.
  Map, build, tick rate, regulation and overtime length must agree across parts.
- Recorded round numbers are kept. A later complete overlap (backup restore) replaces the
  earlier suffix with all its events, economy and snapshots. A boundary fragment is usable
  only if a complete copy of that round survives elsewhere; fragments are never merged.
  Missing rounds, incomplete interior rounds and restores within one file reject the game.
- Retained events and ticks are restricted to their own part's round bounds, then offset
  onto one synthetic tick timeline (next offset = previous offset + last official-end tick
  + 1). Round-relative seconds are unchanged. Grenade attribution runs per part (entity
  handles repeat), then `nade_id` is made unique.
- `_validate_rounds` runs per part and on the stitched history; scores are rebuilt from
  retained winners and must sum to `round_num - 1`. Economy pistols are regulation rounds 1
  and `mp_maxrounds/2 + 1` (awpy would label the first round of every file a pistol).
- Teams are resolved once over all parts by Steam ID. `demo_id` drops `-pK`;
  `matches.demo_file` lists the parts joined with `+`. No table or JSON field changes.

Verified by GPT-03 on MOUZ vs Legacy Nuke (2394905: 13-6, 19 rounds); B8 vs TYLOO Mirage
(2394773) is rejected because awpy emits no rounds for part 1. Tests: `tests/test_multipart.py`
(synthetic) and the optional `tests/test_multipart_pipeline.py`.

## Known limitations and open questions

- Lane shapes are coarse. Two different executes can share a shape; trajectory-level
  clustering is the M2 work.
- Role thresholds are untuned; they need a labelled set (pro roles are public knowledge
  for top teams, so labels are cheap to collect).
- Parsing is strict (GPT-01): demos with restores within one recording or non-consecutive rounds, a bot playing
  inside a live round, or players whose team cannot be resolved are rejected, not repaired.
  A real backup-restore demo and a late-joined GOTV demo still need to be collected to see
  how often this triggers on Tier 1/2 data.
- Two-level maps (Nuke, Train, Vertigo) need the lower radar when z < `lower_level_max_z`
  (heatmaps and holding spots already split levels; the lineup radar does not yet).
- Tactic labels (playbook/tactics.py) only name a target once two T players reach the bomb
  site core or the bomb is planted. Failed executes that never reach the site are `no_hit`
  for now; attributing them from the execute utility is next.
- `shots` counts weapon_fire events; awpy reports roughly 11 per player-round, so treat
  the layer as "where they fight", not as an exact bullet count.

## Roadmap

| Milestone | Content | Status |
|---|---|---|
| M0 | Pipeline: fetch, parse, semantics, export, tests | done |
| M1 | Map configs (7-map pool incl. Cache), team/player aliases | done |
| M2 | Heatmaps, player summaries, tactics (recipes, routes, CT setups), spot names, role checks | done |
| M3 | Website: teams hub (orbit), tactics, lineup library, heatmaps, 2D replay with view cones and WP, AI Lab; zh/en | done (desktop, Chinese first) |
| M4 | Natural-language team summaries from checked facts (`scripts/insight_text.py`) | done for 6 maps; rewritten when facts change |
| M5 | HLTV ingest: planning, manual download list, scripted import, exact dates, archive to external drive | done (2026-10) |
| M6 | Win probability model, WPA, recipe swing, AI Lab explanations | done |
| M7 | More showcase teams (2026 tier-1 events, most popular teams first) | in progress (Aurora next) |
| M8 | Public site repository (built site only, no third-party images) | planned |

## Work split

Built with AI assistance: Claude (architecture, pipeline, review, integration) with helper models for
delegated implementation tasks; briefs and reports are kept under `delegation/`.


## Round win probability and action value (playbook/winprob.py)

Inspired by Szmida & Toka (MIT Sloan 2025, temporal heterogeneous GNN) and Xenopoulos et al. (arXiv 2011.01324), implemented as the simple reproducible version.

- **States**: one per second of live play from `positions` (1 Hz), T-side view: alive and HP per side, equipment value of alive players (round buy ÷ players × alive), time left (round timer 115 s, then the 40 s bomb timer after the plant), planted / site A, score difference, alive players per lane per side, map one-hot. Label: T wins the round.
- **Model**: `HistGradientBoostingClassifier`, 5-fold `GroupKFold` by match; isotonic calibration cross-fitted by match. Every exported probability is out-of-fold — no match is scored by a model that saw it. Baseline: logistic regression on alive counts, time left, planted.
- **Current result**: see `data/site/winprob_metrics.json` (2026-10-25: 745 maps, 1,484,022 states, accuracy 0.752 vs 0.694 baseline, log loss 0.457, Brier 0.155). Folds group by map (`demo_id`); maps of one series can fall in different folds (no team identity features, so leakage is small). Most informative: HP T/CT, equipment difference, alive difference, planted.
- **Action value (ΔWP)**: WP 2 s after the event minus WP in the last full second before it, from the actor's team view; when the round ends inside the window, the outcome is the state after. The game clock alone moves WP (towards CT before a plant, towards T after it), so the mean change of *quiet* 2 s windows (no kill, grenade pop or plant) of the same map, plant state and 10 s time bucket (5 s after a plant) is subtracted. Kills credit the attacker, deaths debit the victim, utility (smoke, flashbang, molotov, HE) credits the thrower at the pop; events before freeze end are ignored. Per player, team and side in `players.json` (`T.wpa`, `CT.wpa`: per round, duels, utility). Utility values are small and noisy: a grenade's effect is often delayed beyond 2 s.
- **Presentation**: `wpa.rounds_per_match` (= per round × 24, extra rounds won per match) and `wpa.percentile` among players of the same map and side with ≥ 50 rounds. The utility split stays in the data but is not headlined on the site.
- **Recipe swing**: mean WP 5 s before the commit vs 10 s after, or the round outcome when the round ends sooner (`tactics.json` › `recipes[].wp`). Biased upward (rounds that reach a commit are already going well): use it to compare recipes, not as an absolute effect.
- **Timelines**: `data/site/<map>/winprob/<demo_id>.json` and full 2D replays for every match of the showcase teams (`config/site.toml`, listed in `index.json` › `showcase`).


## Entry routes (playbook/tactics.py `recipe_routes`)

For every execute recipe, each T player alive at the commit contributes the path from round start to the commit (1 Hz positions). Paths are grouped by the callouts the player dwelt in for ≥ 2 s on the way (the last one before the final callout, plus the final callout). Each group is drawn as its **medoid** — a real player path, so it never crosses walls — resampled to 16 points.

- Groups are taken biggest first. A group whose path runs along an existing route (a player caught half-way at the commit) joins it; if the existing route is itself a stretch of the new path and the new path is at most 1.6× as long, the route takes the longer path (so "back alley → apartments" and "apartments → B site" become one route).
- Rotations and lurks are dropped: a further route may be at most 1.7× the length of the main route and must not zig-zag (length / straight distance ≤ 2.6). Groups under 12 % of the paths are dropped; at most 4 routes.
- Exported as `recipes[].routes` (`via`, `lane`, `n`, `share`, `points` in radar px). Mirage: 2.1 routes per recipe covering 86 % of player paths; Inferno 85 %; Nuke 94 %.

Recipe spots also carry `throw_place` (most common callout the grenade is thrown from, with `throw_place_share`) and `thrower` / `thrower_team` (most frequent thrower, an example only: recipes pool every team). `core` and `options` stay in frequency order because recipe names and insight texts are built from them; the site sorts them by `order` (throw order).

## GPT-23 metrics: routes, intent, six-axis profiles and replay

`recipe_routes` names each retained route from its **last non-site callout** in
`via`. Site means the BombsiteA/B core callouts; chokes such as Mirage Connector remain
eligible even when their coarse region is A_SITE.
`config/route_names.json` supplies a standard name; the original display callout
is the fallback. Only keys present in that map's configured callouts are accepted;
unknown keys are warned about once per map/configuration per export process.
Route membership follows the existing dwell grouping, geometric merging, share
floor and lurk filtering; membership IDs are internal and are never exported.

Recipe `entry_sync_sec` is the median absolute difference of the first living
player's first target **BombsiteA/B core** sample on the two highest-share retained
routes. Only rounds where both routes enter contribute; fewer than two routes or
no paired entries gives null. Route shares use all eligible pre-commit player
paths as their denominator. `sync_pinch` needs both leading routes at >=20% and a
paired median <=3.5 s. `fake` needs other-site plants / **all recipe rounds** >=25%,
including unplanted rounds in the denominator. Existing recipe clustering uses
the plant site as its target, so this badge is normally absent: it cannot discover
a fake that changed target before the recipe was assigned. It does not reuse the
older utility-based fake flag.

The **commit start window** for `rush` starts at `max(0, commit_s - 15)` (the
existing execute utility window's left edge). For each round take the earliest
living T core entry on the target, subtract this start, and clamp at zero for
players already inside. The median of observed rounds is exported as
`median_first_entry_delay_sec`; `rush` requires <=8 s. Missing core observations
are excluded, never interpreted as an instant entry. This is entry speed relative
to the execute window, not necessarily an early-round hit.

`players.json` has `T/CT.radar_6d`. All live rounds count (including pistols and
ecos), deduplicated by match/round/player, with post-round positions and events
excluded. Each axis has `raw`, `percentile`, and `reference_players`. Reference
players have >=50 rounds **on this map and this side**. Lower-sample players retain
raw values but have null percentiles. Per-axis missing observations are excluded
from the reference distribution. Empirical midrank is
`100 * (# below + 0.5 * # equal) / N`; ties, including a constant population, are
centred at 50. Higher values describe more of an attribute, not overall skill.

- **entry**: rounds containing the opening enemy kill or death / rounds played.
  Each round contributes at most one for a player; teamkills/world deaths are not
  opening enemy duels.
- **trade**: equal-weight mean of (own enemy deaths avenged by a teammate within
  `(0, 4]` seconds / own enemy deaths) and (teammate enemy deaths this player
  avenged within `(0, 4]` seconds / all teammate enemy deaths). A revenge kills
  the original attacker. The first qualifying revenge gets credit; one revenge
  may avenge several victims. A denominator of zero gives a null component; the
  available component is used, or null if neither exists. Both raw component
  shares are in `trade_components`. Times are recomputed, not inferred from old
  parser trade flags.
- **lurk_distance**: T only; mean world XY Manhattan distance to the centroid of
  *other alive teammates*, equally weighted by observed living seconds strictly
  after 15 s and strictly before the first plant (or round end if unplanted).
  Samples with no living teammate are excluded. CT is null, not zero.
- **space_gain**: mean per round of `distance(first living position, enemy spawn)
  - distance(last living position, enemy spawn)`, using world XY Euclidean
  distance. Enemy spawn is the map-wide mean of the opposing side's second-zero
  positions. Retreat is negative; death ends the track. This measures net advance,
  not accumulated path length or navigation-mesh reachability.
- **utility_impact**: `(flash-assisted enemy kills + molotov displacements) / rounds`.
  A displacement is one enemy alive at the nearest 1 Hz sample to pop (ties round
  up), within 120 world XY units of the landing point and 120 Z units, whose
  living samples show >150 XY units displacement from that initial point after
  pop and within 3.5 s. Each enemy counts once per grenade. Radius matches the
  replay overlay. `utility_counts` exposes both event counts. This is a sampled
  spatial proxy, not proof that fire caused movement or dealt damage.
- **clutch_wpa**: mean `round win (0/1) - side WP` at the first observed 1vN
  state per side per round, N>=1 (including 1v1). WP comes exclusively from
  `playbook.winprob` match-held-out states at that exact second. Null when no
  scored clutch exists. `clutch_situations` and `clutch_wpa_sum` retain the sample
  and total. It does not credit a player again as N decreases.

Replay `t_control` has one value per frame (three decimal places). Map-wide finite
observed XY positions at nonnegative seconds define a bounding rectangle, split
into **15×15 cells**; only cells containing any observed position are treated as
walkable. Control is the share of these occupied cell centres strictly closer in
Euclidean XY distance to the nearest alive T than the nearest alive CT. Ties are
uncontrolled. T-only gives 1, CT-only 0, no living positions null. Cells are reused
across every round of the map. This is an observed occupancy / proximity proxy;
it ignores walls, sight lines, floors and unseen walkable areas.

Kill `wpa` uses the same sampled window as `winprob.action_values`:
`WP[floor(event_s)+2] - WP[floor(event_s)]`, sign reversed for CT actors.
If the later second is beyond the round end, the actual terminal outcome is used;
missing pre-event states or unknown actors give null. Raw replay WPA is rounded
to four decimals; the UI displays signed percentage points. Multiple actions in
the window can share a swing: this is not causal attribution. WP arrays preserve
second indexes, including null holes. Positions remain integer radar pixels.

View cones use each player's eye yaw per sampled second (`m_angEyeAngles`, parsed into
`positions.yaw`; tests in `tests/test_view_cones.py`).
