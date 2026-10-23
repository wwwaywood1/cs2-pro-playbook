# GPT-33 ingest fixes report

## Result

- Parsed maps: **423 → 455**; **28** newly recovered distinct maps; **30** newly parsed recordings survive export content dedupe (some may replace an older preferred recording).
- Original parquet preservation: **5076** SHA-256 checks, **0** changed/missing; **384** new files. No existing parsed demo ID was migrated.
- Original 21 failing game groups: **13 recovered, 8 still rejected** (two recovered groups have cross-source copies). Final full parse has **8** failures, detailed below.
- Full export completed and `cp -R data/site/. site-preview/data/` completed; **3152** files verified, **0** mismatches.
- Full pytest: `267 passed, 3 skipped, 1 warning in 17.37s`.

## Identity and import

`playbook.parse.demo_identity` now scopes nonnumeric HLTV archive members as `hltv-<16 hex SHA256 of archive directory>_<game stem>`. Multipart members share the game stem and one ID. Numeric HLTV identities and loose demo IDs keep their existing behavior. Scope is relative to the `hltv` directory, so moving the repository does not change IDs.

`config/hltv_legacy_ids.json` explicitly binds **188** existing parsed HLTV games to their old IDs using archive-relative game paths. These were generated before re-import from the unambiguous existing raw-to-parquet mapping. Keep this compatibility registry with the dataset; deleting it would assign scoped IDs to those historical recordings on a later parse. New series cannot claim another source's legacy binding. Existing unique parquets require no migration or reparse. Alias changes are reapplied to all team columns at export.

The supplied JSON lists **18 colliding identities across 26 distinct archives**, not 18 distinct archives. Revisited all 26 archives using the production extractor, header/map checks and `_process`; retained all original archives. Reproduction helper: `.venv/bin/python -m _sync.gpt33.reimport`.

Import totals: **19 imported game groups**, **45 existing-identity skips**, **5 off-pool skips**, **0 failures**. Identity skips here refer to the same scoped source; different archived rematches are allowed through. Content copies are still removed at export.

| Archive | Imported | Existing | Off pool | Failed |
| --- | ---: | ---: | ---: | ---: |
| `blast-bounty-2026-season-1-finals-vitality-vs-falcons-bo3-m75xkiVwc3YZkEbdtP1s9_.rar` | 1 | 2 | 0 | 0 |
| `blast-open-porto-2026-mouz-vs-vitality-bo3-V3i93ufoKzBC0MBPii8PGf.rar` | 0 | 2 | 0 | 0 |
| `blast-open-porto-2026-vitality-vs-9z-bo3-p-u8ZqQpw4ORQzAjpnwJBy.rar` | 0 | 2 | 0 | 0 |
| `blast-open-rotterdam-2026-vitality-vs-9z-bo3-kVsrbfS7P7ANQA8A6NP-eu.rar` | 1 | 0 | 1 | 0 |
| `blast-open-rotterdam-2026-vitality-vs-aurora-bo3-FlxFvdx4Pl-M44Zsyy4BH3.rar` | 0 | 2 | 0 | 0 |
| `blast-rivals-2026-season-1-natus-vincere-vs-vitality-bo5-Mv7s4IInKiHxzKeMZKCajF.rar` | 0 | 3 | 0 | 0 |
| `blast-rivals-2026-season-1-vitality-vs-fut-bo3-9RYfK_Nffwu4TXDghNJDks.rar` | 0 | 3 | 0 | 0 |
| `blast-rivals-2026-season-1-vitality-vs-g2-bo3-QFGfmJ4pQ03xQPiA9-8d-X.rar` | 0 | 2 | 1 | 0 |
| `esl-pro-league-season-24-aurora-vs-vitality-bo3-jz97l79s_ZddmLmtUQ37rg.rar` | 0 | 3 | 0 | 0 |
| `esl-pro-league-season-24-vitality-vs-falcons-bo3-tjOq40YPwMI3QHOotPr9e9.rar` | 0 | 3 | 0 | 0 |
| `esports-world-cup-2026-b8-vs-vitality-bo3-N4CDgIbMarl-Be8034f4a_.rar` | 0 | 3 | 0 | 0 |
| `iem-atlanta-2026-b8-vs-vitality-bo3-nGRbmcCg2mU5uSsmD_vHGX.rar` | 1 | 1 | 0 | 0 |
| `iem-atlanta-2026-natus-vincere-vs-vitality-bo3-Oy5NkCJPWmHl6H0cKtC9_L.rar` | 1 | 2 | 0 | 0 |
| `iem-cologne-major-2026-vitality-vs-fut-bo3-rNsUTmTOO26ftPbfiPVp79.rar` | 1 | 1 | 1 | 0 |
| `iem-cologne-major-2026-vitality-vs-mouz-bo3-E9khg_TX6BxGaIZNKJ3X1O.rar` | 0 | 3 | 0 | 0 |
| `iem-krakw-2026-vitality-vs-aurora-bo3--mY74mcLmUrEjY-ofCuhG0.rar` | 0 | 1 | 1 | 0 |
| `iem-krakw-2026-vitality-vs-mouz-bo3-UD0TEnJpRupm9E_EHc4hZG.rar` | 1 | 1 | 0 | 0 |
| `iem-rio-2026-vitality-vs-falcons-bo3-O2Ctrym3k5WQt8XytMQySq.rar` | 1 | 2 | 0 | 0 |
| `iem-rio-2026-vitality-vs-g2-bo3-yhOR34cA9Po02UrfKIOtO9.rar` | 2 | 1 | 0 | 0 |
| `pgl-cluj-napoca-2026-mouz-vs-vitality-bo3-k_w5VQbpH9bZlYTAZc8SyE.rar` | 1 | 1 | 0 | 0 |
| `pgl-cluj-napoca-2026-vitality-vs-aurora-bo3-Pn_Q-PJO50-mcoIjPX1Cjf.rar` | 1 | 0 | 1 | 0 |
| `pgl-cluj-napoca-2026-vitality-vs-g2-bo3-qYj9k9myd7QwvfmcK2ZjT5.rar` | 2 | 1 | 0 | 0 |
| `pgl-cluj-napoca-2026-vitality-vs-the-mongolz-bo3-HnIEEaHEW5z1jrP1O7fbaW.rar` | 0 | 3 | 0 | 0 |
| `pgl-cluj-napoca-2026-vitality-vs-the-mongolz-bo3-_V1-atgVjp_HiqnMb5rNMc.rar` | 2 | 0 | 0 | 0 |
| `starladder-starseries-fall-2026-aurora-vs-vitality-bo3-YKs8kEDNPDubjefvBPad28.rar` | 1 | 2 | 0 | 0 |
| `starladder-starseries-fall-2026-aurora-vs-vitality-bo5-a29hF-CpdWTocEVzwpQ_0F.rar` | 3 | 1 | 0 | 0 |

Export content dedupe drops **38** recordings (GPT-32 baseline: 34). Exact keep/drop pairs: `_sync/gpt33/dedupe-after.json`; new retained rows: `_sync/gpt33/new-kept-matches.json`. True duplicate archive downloads can receive different series hashes but still collapse by canonical map/teams/ordered-round-winner signature.

## Round investigation and safe repairs

Inspected **every round table in the 21 failed game groups**, including all recording parts. Raw tables and convars: `_sync/gpt33/round-audit.json` and `_sync/gpt33/*__*.json`.

All ten single-file m3 failures had consecutive round numbers and valid winners; the only invalid bound was a null `start_tick` on round 1. This is missing initial boundary evidence, not an overtime numbering/MR3-half problem or an overlapping restore. Examples:

| Recording | Round range | Round 1 start / freeze end / end / official end |
| --- | --- | --- |
| `data/raw/hltv/blast-rivals-2026-season-1-vitality-vs-g2-bo3-QFGfmJ4pQ03xQPiA9-8d-X/vitality-vs-g2-m3-dust2.dem` | 1–16 | None / 16295 / 22569 / 23017 |
| `data/raw/hltv/blast-open-porto-2026-furia-vs-vitality-bo3-KULcN3Jf23XthDsJCBq9hT/furia-vs-vitality-m3-dust2.dem` | 1–17 | None / 16941 / 22053 / 22501 |
| `data/raw/hltv/cs-asia-championships-2026-falcons-vs-mouz-bo3--bPrjLQ2TP-mMaeM2Zy1DS/falcons-vs-mouz-m3-nuke.dem` | 1–23 | None / 5425 / 8806 / 9254 |

`playbook.parse._leading_round_bounds` clips only a recording's missing leading start to its observed freeze-end tick. It retains the full observed live interval and invents no earlier ticks. Missing freeze/end/winner evidence, interior missing starts, numbering resets and overlapping bounds remain rejected by `_validate_rounds`.

Multipart handling uses the same clipping before round ownership is chosen. This recovers Vitality–MOUZ Dust2 round 13 in both archive sources: freeze end and the entire live round exist, only the leading start is absent. Export counts the two recordings once.

FaZe–Vitality Nuke has a synthetic tick-1 `unassigned` / winner 0 / reason 0 (`still_in_progress`) marker at the start of part 2. `_stitch_rounds` treats only that exact marker shape as a boundary fragment, and still requires a complete copy in final ownership. Part 1 supplies round 1; part 2 supplies rounds 2–30. Recovered score: **FaZe 14–16 Vitality**, including overtime. Other malformed winners still fail. Monte–Legacy has the same marker without a complete round-1 copy, so remains rejected.

Actual backup restores are not broadly admitted: the existing later-complete-suffix ownership rule stays in place. Synthetic regressions cover missing live history, interior bounds, overlaps, numbering resets, non-sentinel bad winners, and a restart sentinel without a complete copy.

## Maps recovered per team

Counts below are active-pool published team-map appearances. “Before” is the site snapshot taken before GPT-33, with the new aliases applied when summing team spellings; “After” comes from `data/site/<map>/teams.json`. Historical Overpass is unchanged and excluded.

| Team | Before | After | Delta |
| --- | ---: | ---: | ---: |
| 100T | 2 | 3 | +1 |
| 9z | 25 | 26 | +1 |
| Aurora | 26 | 31 | +5 |
| FURIA | 22 | 23 | +1 |
| FUT Esports | 17 | 18 | +1 |
| FaZe | 3 | 4 | +1 |
| Falcons | 89 | 96 | +7 |
| G2 | 23 | 28 | +5 |
| Legacy | 30 | 32 | +2 |
| Lynn Vision | 16 | 17 | +1 |
| MOUZ | 27 | 32 | +5 |
| Natus Vincere | 27 | 28 | +1 |
| The MongolZ | 32 | 34 | +2 |
| Vitality | 115 | 138 | +23 |

| Map | Vitality before | Vitality after | Delta | Falcons before | Falcons after | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `de_ancient` | 2 | 2 | +0 | 14 | 14 | +0 |
| `de_anubis` | 16 | 19 | +3 | 11 | 12 | +1 |
| `de_cache` | 8 | 8 | +0 | 0 | 0 | +0 |
| `de_dust2` | 29 | 38 | +9 | 27 | 30 | +3 |
| `de_inferno` | 19 | 22 | +3 | 11 | 12 | +1 |
| `de_mirage` | 22 | 27 | +5 | 16 | 17 | +1 |
| `de_nuke` | 19 | 22 | +3 | 10 | 11 | +1 |
| `de_overpass` | 1 | 1 | +0 | 0 | 0 | +0 |

Machine-readable before/after for every team on every map: `_sync/gpt33/counts-before.json`, `_sync/gpt33/counts-after.json`. New distinct content maps per team (excludes a new recording replacing old content):

- Vitality: 23
- Falcons: 7
- MOUZ: 5
- G2: 5
- Aurora: 5
- Legacy: 2
- The MongolZ: 2
- Lynn Vision: 1
- FaZe: 1
- 100T: 1
- FURIA: 1
- Natus Vincere: 1
- FUT Esports: 1
- 9z: 1

## Aliases and event grouping

- Added `PVISION → PARIVISION`, `BC Game Esports → BC.Game`, `Virtus.pro_ → Virtus.pro`, and `FUT → FUT Esports` in `config/team_aliases.csv`. `FUT Esports` already existed in parsed/site data; its self-alias makes that canonical spelling explicit.
- `playbook.dedupe.demo_event_slug` recognizes the known `virtuspro` / `virtus-pro` archive/member spelling difference. It now resolves the Bounty Virtus.pro–Vitality Dust2 map to the existing configured event/date; no schedule dates were edited.
- Remaining undated active-pool Vitality records: **0**. Details in `_sync/gpt33/verification.json`.

## Remaining failures

No incomplete competitive history was filled by guessing a score or renumbering later rounds. Empty first parts below are awpy round-table results, not claims that the underlying demo bytes contain no events. Recovering them would require a separate raw game-rule/event reconstruction.

| Game/source | Reason | Missing competitive rounds from inspected tables |
| --- | --- | --- |
| `data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2 |
| `data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 |
| `data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p1.dem` (+ sibling parts) | ValueError: Incomplete rounds have no complete copy: [1] | 1 |
| `data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23 |
| `data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2, 3, 4 |
| `data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 |
| `data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2, 3 |
| `data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p1.dem` (+ sibling parts) | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 | 1, 2, 3, 4, 5 |

Exact multipart paths and errors: `_sync/gpt33/remaining-failures.json`; full final CLI output: `_sync/gpt33/parse-full.log`.

## Cache inventory (report only)

- Cache remains in `playbook.export.ACTIVE_POOL`; Vitality has **8** published maps. No Cache UI, map config or project radar was added. `load_map("de_cache")` still returns empty callout/region mappings and the default `(pos_x=0, pos_y=0, scale=1)` transform, which is not verified Cache calibration.
- awpy installed locally is 3.1.0. Its `awpy/data.py` fetches versioned radar/nav/transform assets from `pnxenopoulos/awpy-data`; those assets are not bundled inside the Python wheel.
- **Radar confirmed locally:** `/Users/stephen/.awpy/2000933/radars/de_cache.png`, 1024×1024, SHA-256 `94c058b3deaa5cc24be81006322da3af1ef0bbded116160a3fcdea6d87227967`.
- **Radar transform:** no cached `map_data.json`; exact Cache values could not be verified. **Nav:** no cached nav directory or Cache nav; Cache-specific release membership could not be verified. Do not infer presence of Cache nav merely from a release-level `navs.zip` asset.
- Checked the upstream [awpy-data README](https://github.com/pnxenopoulos/awpy-data/blob/main/README.md) and [latest release](https://github.com/pnxenopoulos/awpy-data/releases/tag/2000934) via the GitHub connector. Latest listed release is `2000934` (2026-10-21); it offers `images.zip`, `navs.zip`, `geometry.zip`, `map_data.json`, and `manifest.json`. The local cache remains `2000933`. Terminal DNS blocked asset downloads; the connector exposed release metadata but could not return release-asset bodies/binary ZIP listings. Saved evidence: `_sync/gpt33/awpy-assets.json`, `_sync/gpt33/awpy-release.json`. Per-Cache transform/nav verification remains a follow-up when release downloads are reachable.

`m_szLastPlaceName` counts below cover all raw per-tick player rows from the eight Cache demos, including warmup, freeze time and dead players (not unique locations or live seconds). Parsed one-second live-position counts are provided alongside them. Exact per-demo raw counts are in `_sync/gpt33/cache-callouts.json`; live counts in `_sync/gpt33/cache-positions.json`.

| Place name | Raw player-tick rows | Live one-second player samples |
| --- | ---: | ---: |
| `TSpawn` | 2182321 | 3943 |
| `CTSpawn` | 2080391 | 2345 |
| `(empty)` | 1099000 | 0 |
| `BombsiteB` | 1089339 | 15090 |
| `Mid` | 908043 | 13003 |
| `BombsiteA` | 878397 | 11637 |
| `Garage` | 495067 | 7426 |
| `AMain` | 483845 | 7039 |
| `Checkers` | 465462 | 6475 |
| `OutsideA` | 441725 | 6692 |
| `BMain` | 429145 | 5849 |
| `BHalls` | 413323 | 6280 |
| `Highway` | 373193 | 5342 |
| `Truck` | 337148 | 4844 |
| `SunRoom` | 324003 | 4705 |
| `CTLane` | 318521 | 4812 |
| `ForkLift` | 289822 | 4056 |
| `Connector` | 264736 | 3844 |
| `TreeRoom` | 217868 | 3232 |
| `AHalls` | 178774 | 2644 |
| `AStairs` | 174083 | 2605 |
| `LongA` | 170656 | 2591 |
| `TYard` | 170191 | 2629 |
| `Squeaky` | 165237 | 2352 |
| `Headshot` | 140389 | 2008 |
| `Corner` | 139188 | 2029 |
| `Quad` | 134725 | 1852 |
| `Heaven` | 113084 | 1607 |
| `BusStop` | 112875 | 1546 |
| `OutsideB` | 109842 | 1626 |
| `Vents` | 102854 | 1465 |
| `Boost` | 102854 | 1547 |
| `Useless` | 101805 | 1546 |
| `Sandbags` | 86735 | 1290 |
| `Catwalk` | 86547 | 1232 |
| `Rafters` | 66224 | 859 |
| `ElectricalBox` | 65410 | 943 |
| `Cubby` | 60992 | 906 |
| `Toxic` | 49505 | 713 |
| `Bear` | 43648 | 612 |
| `Ladder` | 39001 | 579 |
| `MidRoof` | 29544 | 395 |
| `BackHall` | 23323 | 349 |
| `TTruck` | 22859 | 343 |
| `Lockers` | 22429 | 288 |
| `Red` | 12034 | 188 |
| `ABoost` | 12022 | 174 |
| `Middle` | 4266 | 68 |

## Validation and reruns

- `.venv/bin/python -m pytest -q`: all pass; one existing joblib physical-core-detection warning; three environment-dependent skips.
- Production/config edits: `playbook/parse.py`, `playbook/multipart.py`, `playbook/dedupe.py`, `config/hltv_legacy_ids.json`, `config/team_aliases.csv`.
- Test edits: new `tests/test_ingest_fixes.py`; updated `tests/test_import_hltv.py`, `tests/test_dedupe.py`, `tests/test_dates.py`, `tests/test_multipart.py`.
- `.venv/bin/python -u -m playbook parse`: exit 1 for the remaining failures listed above; all other game groups parsed or reused valid existing parquet.
- `.venv/bin/python -u -m playbook export`: exit 0.
- `cp -R data/site/. site-preview/data/`: exit 0; SHA-256 comparison passed.

| Stage | Exit | Seconds |
| --- | ---: | ---: |
| parse-full | 1 | 136.712 |
| export | 0 | 728.973 |
| copy | 0 | 1.185 |

Next steps for the lead: decide Cache configuration/radar work after obtaining the release transform/nav metadata; obtain complete recordings or separately reconstruct missing raw histories for the remaining multipart failures. Export automatically invalidates commentary fact fingerprints where facts changed.

The supplied directory has no `.git` metadata, so this report identifies edited files and SHA-256 preservation evidence rather than a commit. `rg` was unavailable; inspections used `find`, `grep`, Python, and `diff`.
