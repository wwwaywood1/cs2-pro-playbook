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
CounterQuant (HF) ──fetch──> data/raw/*.dem
                              │ parse.py      (awpy 3.1: one demo -> normalized tables)
                              │ semantics.py  (team_rounds, player_rounds)
                              ▼
                       data/parsed/<table>/<demo_id>.parquet
                              │ export.py     (aggregate across demos, per map)
                              ▼
                       data/site/**.json  ──copy──> web/public/data  ──> static site (GitHub Pages)
```

All analysis is precomputed offline; the website only reads JSON. Each stage is rerunnable
on stored output: `export` never touches demos, and `parse` skips demos already parsed.

| Module | Role |
|---|---|
| `playbook/fetch.py` | Lists and downloads demos from CounterQuant matching `config/targets.toml` |
| `playbook/parse.py` | One demo to tables; teams, sides, rounds, positions, kills, plants, grenades |
| `playbook/utility.py` | Grenade thrower recovery; callout lookup for arbitrary points |
| `playbook/semantics.py` | Round semantics (labels per round x team, and per round x player) |
| `playbook/export.py` | Site JSON: team profiles, player profiles, lineup library |
| `playbook/store.py` | Parquet storage, one file per demo per table |
| `config/maps/*.toml` | Callout to region to lane mapping, radar transform, per map |
| `config/team_aliases.csv` | In-game clan names to canonical team names |

## Data sources

- **CounterQuant CS2 Demos** (huggingface.co/datasets/KEDevO/CounterQuant-CS2-Demos),
  CC BY 4.0, raw `.dem` files collected from HLTV.org, Tier 1/2, 2024 onward, updated
  within 24 to 48h of matches. Layout `data/{year}/{tier}/{hltv_match_id}/{team1}-vs-{team2}-{map}.dem`.
  Caveat: it is maintained by one person, and the original demos come from HLTV, so the
  CC BY license on the collection may not settle the rights of the underlying files.
  Fine for research and a non-commercial site; revisit before any monetisation.
- **awpy test fixtures** (github.com/pnxenopoulos/awpy-fixtures): used for tests
  (B8 vs Vitality on Mirage, 9z vs PARIVISION on Inferno).
- **awpy-data** releases: radar images and world-to-radar transforms (release 2000933).
- Fallback: GRID Open Access (official CS2 data; free for students and pre-revenue projects).

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
| awper | AWP at freeze end in at least 40% of rounds |
| a_anchor / b_anchor / mid_ct | same CT lane at 15s in at least 60% of CT rounds |
| lurker | highest T-side dist_to_team_30s on the team and at least 1.25x the team median |
| entry | highest T-side first-into-site rate on the team, at least 0.25 |
| support | most utility thrown per round on the team |

These thresholds are placeholders until a labelled validation set exists (Roadmap M2).

### Lineup clustering

Grenades of the same side and type are one lineup if released within 48 units and landing
within 120 units of the running cluster centre. The representative throw is the member
closest to the centre; its position and angles produce
`setpos x y z;setang pitch yaw 0`. Technique is jump, run (speed at least 100), crouch,
walk or stand, taken at the release tick.

## Site data contract (data/site, schema_version 1)

```
index.json                      { schema_version, generated_at, min_matches_reliable, maps: [{ map, display_name, n_matches, teams[], n_players, n_lineups }] }
<map>/meta.json                 { map, display_name, radar{pos_x,pos_y,scale[,lower_level_max_z]}, regions{region:lane}, callouts{callout:region} }
<map>/teams.json                [{ team, slug, n_matches, low_sample, win_rate_T, win_rate_CT }]
<map>/teams/<slug>.json         { team, slug, map, n_matches, low_sample, matches[], sides{T,CT}, economy[] }
<map>/players.json              [{ steamid, name, team, rounds{total,T,CT}, kpr, dpr, hs_pct, opening_*, awp_share, util_pr, T{...}, CT{...}, role_hints[] }]
<map>/lineups.json              [{ id, side, type, throw_place, land_place, land_region, land_lane, n_throws, n_matches, teams[], throwers[], round_win_rate, median_pop_t_s, technique, jump_share, throw{x,y,z,pitch,yaw,radar_x,radar_y}, land{x,y,z,radar_x,radar_y}, practice_cmd, example{demo_id,round_num,throw_tick} }]
```

- `sides.T` includes `plant_sites`, `execute_timing` (`fast` before 35s,
  `default_then_execute` 35 to 65s, `late`, `no_clear_execute`), `execute_lane`,
  `setups_15s`, `setups_30s`.
- `sides.CT` includes `setups_15s/30s`, `plants_against`, `retake_win_rate`, `stack_rate_15s`.
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
- `fetch.py` is written against the documented dataset layout but has not been run
  against Hugging Face yet (blocked in the development sandbox). First real run:
  `python -m playbook fetch --dry-run`.

## Known limitations and open questions

- Lane shapes are coarse. Two different executes can share a shape; trajectory-level
  clustering is the M2 work.
- Role thresholds are untuned; they need a labelled set (pro roles are public knowledge
  for top teams, so labels are cheap to collect).
- Multipart demos (one map split over several files) are not handled; awpy supports them.
- Parsing is strict (GPT-01): demos with restored or non-consecutive rounds, a bot playing
  inside a live round, or players whose team cannot be resolved are rejected, not repaired.
  A real backup-restore demo and a late-joined GOTV demo still need to be collected to see
  how often this triggers on Tier 1/2 data.
- Two-level maps (Nuke, Train, Vertigo) need the lower radar when z < `lower_level_max_z`.

## Roadmap

| Milestone | Content | Status |
|---|---|---|
| M0 | Pipeline: fetch, parse, semantics, export, tests | done |
| M1 | Map configs (Mirage, Inferno done), team aliases (done), first 60 demos for Mirage + Inferno | next: fetch |
| M2 | Tactic identification: trajectory clustering of T executes and CT setups, labelled validation set, tuned role thresholds | after M1 |
| M3 | Website v1: lineup library, team and player pages, bilingual (zh/en) | done on sample data; GitHub Pages deploy pending |
| M4 | Natural-language summaries generated from the computed numbers (the LLM rewrites, never invents) | after M2 |
| M5 | Full map pool, weekly incremental update | later |

## Work split

- Claude: architecture, parsing and semantics, tactic identification (M2), review and
  integration of delegated work, tests.
- DeepSeek: map callout configs, team alias table, i18n labels, frontend implementation
  to a fixed spec (see `delegation/`).
- GPT: one robustness review of the parsing edge cases (GPT-01).
