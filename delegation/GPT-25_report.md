# GPT-25 backend v3.1 report

Completed 2026-10-22 in `/Users/stephen/Downloads/cs2-pro-playbook`. Read the delegation brief, review_round6.txt and route_mirage_a_r01.png. Backend/config/tests and generated data only; **no files in `web/` were changed**.

## 1. Route names and entry timing

Cause: `playbook/tactics.py::recipe_routes` named a route from its temporal dwell grouping key. In the ramp medoid, the last three pre-site samples carry `PalaceInterior`; the final `BombsiteA` sample lasts only one second and drops out of `_via`. The resulting key `TRamp, PalaceInterior` therefore names the ramp path Palace. A grouping key is not reliable evidence of the displayed route's main approach, particularly after geometry merges/extensions. `Scaffolding` also lacked a Chinese translation.

Fix: retain the chosen medoid's player/demo/round identity through both merge branches. `_point_places` maps each distance-spaced drawn point back to that player's own position sequence along arc length. `_drawn_via` uses sustained stretches of these drawn samples, excluding incidental one-point boundary labels, plus the final callout. Both the name and `via` now use this evidence rather than the grouping key. Export `point_places` and `medoid_member` for auditing. No coordinate thresholds or polygons were hard-coded. `config/route_names.json` now translates every configured callout on all six maps; invalid/non-map keys were removed.

`de_mirage-a-r01` before → after:

| Route | Before name / via | After name / via | Players / share |
|---|---|---|---|
| a | A二楼同步线 / TRamp, PalaceInterior | A1 斜坡主攻线 / TSpawn, PalaceAlley, TRamp, BombsiteA | 126 → 126 / 54.8% → 54.8% |
| b | Scaffolding / Scaffolding, BombsiteA | A二楼线 / TSpawn, PalaceInterior, BombsiteA | 53 → 53 / 23.0% → 23.0% |

Drawn coordinates are unchanged for both routes. Ramp medoid: `{'demo_id': '2394994_betboom-vs-fut-m1-mirage', 'round_num': 6, 'steamid': '76561199313968259'}`. Palace medoid: `{'demo_id': '2394885_b8-vs-gamerlegion-m2-mirage', 'round_num': 9, 'steamid': '76561198304115519'}`.

`recipe_extras` already used the first living member to reach the target's `BombsiteA/B` core for each route, paired within the same round; it did not use utility pop time. It did, however, accept first arrivals after the plant. Those arrivals are now excluded, as are arrivals beyond a supplied round-duration bound. `sync_pinch` now requires a median gap **≤3.0 seconds**, replacing 3.5; missing paired arrivals yield null. `entry_sync_rounds` exposes the paired sample size.

For this recipe, `entry_sync_sec`: **5.5 → 3.5 seconds** (26 eligible paired rounds after filtering). `intent_badges`: `[]` → `[]`. The 3.5-second result receives no synchronization badge.

## 2. Early positions: evidence and before/after

The existing export did **not** reproduce the screenshot's SideAlley claim for NiKo/kyousuke: their existing top places were already BackAlley. The actual code also already skipped the first **5** seconds, rather than including all spawn seconds. `playbook/heatmap.py::SPAWN_SKIP_S` is now **6**, with `EARLY_S=20` unchanged. Presence/holding grids and zone summaries share the same cleaned frame stream: early living position seconds in **[6,20)**, gun rounds for the player's team. Phase events such as utility/shots keep their actual event times.

Falcons Mirage has 113 T gun rounds per player. Below, “before” is the actual old export/window [5,20), and “after” is [6,20). The [0,20) column is a diagnostic of the originally requested spawn-inclusive window.

| Player | [0,20) top place | Before [5,20) top place | After [6,20) top place |
|---|---|---|---|
| NiKo | BackAlley 24.3% | BackAlley 32.4% | BackAlley 34.7% |
| kyousuke | TSpawn 19.4% | BackAlley 19.0% | BackAlley 20.4% |
| m0NESY | SideAlley 28.6% | SideAlley 30.1% | SideAlley 28.1% |
| TeSeS | TSpawn 32.3% | PalaceInterior 36.4% | PalaceInterior 38.3% |
| karrigan | SideAlley 40.1% | SideAlley 43.6% | SideAlley 41.3% |

NiKo's living-second shares per parsed callout (same 113 T gun rounds):

| Place | [0,6), seconds / 678 | [6,20), seconds / 1,582 |
|---|---|---|
| BackAlley | 0 / 0.00% | 549 / 34.70% |
| House | 29 / 4.28% | 242 / 15.30% |
| PalaceInterior | 4 / 0.59% | 211 / 13.34% |
| Underpass | 0 / 0.00% | 127 / 8.03% |
| TopofMid | 0 / 0.00% | 122 / 7.71% |
| PalaceAlley | 4 / 0.59% | 97 / 6.13% |
| SideAlley | 164 / 24.19% | 93 / 5.88% |
| TSpawn | 477 / 70.35% | 68 / 4.30% |
| TRamp | 0 / 0.00% | 34 / 2.15% |
| Apartments | 0 / 0.00% | 25 / 1.58% |
| Middle | 0 / 0.00% | 14 / 0.89% |

SideAlley falls from **24.19%** in [0,6) to **5.88%** in [6,20). BackAlley still wins at **549/1,582 = 34.70%**, versus TopofMid **122/1,582 = 7.71%**; keep the data-derived BackAlley summary. The current 64×64 early presence grid's hottest NiKo cell is also BackAlley (cell 934, 88 living seconds). There is no evidence in this snapshot supporting a coordinate remap to Top Mid. The review may describe a different build/layer/selection.

## 3. KPR contract and before/after

Cause: `playbook/export.py::player_profiles` used semantic kills / all player rounds on the selected map, originally grouped only by steamid and assigning the modal team. `heatmap.clean_frames` / `zones._fights` instead used gun-round, side-filtered kills with valid attacker radar coordinates / gun rounds on that side. NiKo's old **0.637≈0.64** detail value was the T gun-round rate, while **0.700≈0.70** was all sides/all buys. Transfers could additionally mix team histories.

Fix: `playbook/metrics.py::combat_totals` is the shared calculation, using semantic `player_rounds` counters. Semantic kills exclude teamkills and post-round kills. Every played round for this **map + team + player** counts, including pistol/eco, with no coordinate requirement. Profiles are now grouped by `(team, steamid)`. Heatmap spatial layers remain gun-round layers; combat stats are explicitly separate. Side fight totals use all rounds for that side and expose their own denominator; `fights.places` remains spatial/gun-round data and is tagged accordingly.

Frontend handoff for GPT-26:

- **All-side KPR:** `heatmap.players[steamid].stats.kpr`; identical to the matching `players.json` record's `kpr` (match both team and steamid).
- **Explicit T/CT labels:** `heatmap.players[steamid].stats.sides[side].kpr`; side `summary[steamid][side].fights.kills_pr` is a compatibility alias using the same calculation.
- Use `stats.kills` / `stats.rounds` for totals; do not average side KPRs or weight them with the gun-round `summary.rounds`.

| Player | Before hover, all-side KPR | Before detail, T gun KPR | After canonical kills/rounds = KPR | After T all-round KPR |
|---|---|---|---|---|
| NiKo | 0.700 | 0.637 | 222/317 = 0.700 | 0.655 |
| kyousuke | 0.754 | 0.637 | 239/317 = 0.754 | 0.641 |
| m0NESY | 0.792 | 0.690 | 251/317 = 0.792 | 0.676 |
| TeSeS | 0.609 | 0.566 | 193/317 = 0.609 | 0.542 |
| karrigan | 0.407 | 0.283 | 129/317 = 0.407 | 0.289 |

## 4. Replay events

`playbook/replay.py::build_round` now adds actor `side` to kills/util/plants; `place` means the victim's callout for kills and landing callout for utility. Parsed places take precedence; missing places use the map's observed `PlaceIndex`, including height and its existing airborne 2D fallback. Plant `site` and actor `by` are available; player names remain in `players[by].name`. Kill `wpa` is retained, in actor perspective and fractional units. Flashes remain exported with `nade="flash"` and `is_flash=true`; other utility has `is_flash=false`, allowing the UI to filter without losing evidence. Unknown actors/locations remain null rather than fabricated.

| Replay measure | Before | After |
|---|---|---|
| Replay files | 2,195 | 2,195 |
| Kills | 14,455 | 14,455 |
| Utility events | 50,791 | 50,791 |
| Flashes retained | 14,952 | 14,952 |
| Plants | 1,252 | 1,252 |
| Kills with actor side | 0 | 14,420 |
| Kills with victim place | 0 | 14,454 |
| Utility with actor side | 0 | 50,700 |
| Utility with landing place | 0 | 50,778 |

Remaining null provenance: 35 kill actor sides, 1 victim place, 91 utility actor sides and 13 utility landing places. UI code should tolerate these null fields.

## 5. Validation and export

- `.venv/bin/python -m pytest -q`: **234 passed, 2 skipped**, 17.56s. The two skips required Node on PATH.
- With the existing bundled Node runtime on PATH, the same full suite: **236 passed, no skips**, 29.64s. One existing joblib physical-core discovery warning; logical-core fallback succeeded. No frontend builds or writes were performed.
- Added eight regressions in `tests/test_backend_v31.py`: own-point naming, merged medoid provenance, full Chinese naming coverage, 3-second sync boundary/pre-plant pairing, shared early window, all-round/team/side KPR with missing coordinates and transfers, floor-aware replay fallback, and event side/place/WPA/flash preservation. Updated existing fixtures/assertions for the 6-second spawn cutoff while preserving vertical-motion coverage.
- `.venv/bin/python -u -m playbook export`: **completed, exit 0**, all six active maps. Win-probability fit: 289 matches; accuracy 0.743 versus baseline 0.697, log loss 0.471.
- Generated JSON audit: **181 routes** with `via ⊆ point_places`, aligned point labels, and Chinese names; sync badges ≤3 seconds; **838 team/player KPR pairs** agree with profiles and their counts; all replay events have side/place fields, flashes retain filter tags, kills retain WPA, actor sides agree with their roster records.
- Retired **62 stale alias team/profile and heatmap files** not referenced by the canonical team index; reversible copies are in `/tmp/gpt25-backend-before/stale-export-files/`. No raw/parsed data was removed.
- Copied `data/site/` to `site-preview/data/site/`; verified relative file sets and SHA-256 equality for **2,671 files**. Existing inactive Overpass artifacts remain outside the six-map export index.

Exported active-map inventory:

| Map | Matches | Players | Lineups |
|---|---|---|---|
| de_ancient | 43 | 131 | 2177 |
| de_anubis | 24 | 103 | 1417 |
| de_dust2 | 63 | 176 | 3014 |
| de_inferno | 47 | 139 | 2173 |
| de_mirage | 57 | 129 | 2443 |
| de_nuke | 49 | 160 | 1790 |

Immediate frontend follow-up: consume the canonical all-side KPR field when the label has no side; use replay side/place and is_flash in the new event list; render neutral route-gap text unless the backend emits `sync_pinch`. These UI changes belong to GPT-26 and were not made here.
