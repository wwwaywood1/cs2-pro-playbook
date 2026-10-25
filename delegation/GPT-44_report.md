# GPT-44 FURIA ingest report

Status: **complete with pre-existing pytest failures**.

## Import and parsing

- Selected **73 FURIA archives**, **54,050,440,821 bytes**; **58 moved**, **15 existing destinations preserved**. Selected archives remain in `data/raw/hltv/`; duplicate source downloads remain untouched.
- Preserved **22 unrelated match archives**. The single-map `esports-world-cup-2026-wildcard-vs-furia-inferno-3fF_EvKlCeYEBMa_00qfxm.rar` was excluded because it does not match the requested `*-bo1/3/5-*` archive pattern; it remains in Downloads.
- **138 imported games**, **35 duplicate identity skips**, **15 off-pool skips**, **0 import failures**. **58 archives contributed imports**; **15 contributed none**.
- Newly parsed map demos: **137**; new FURIA rows retained after content dedupe: **137**.
- Ran `caffeinate -i env BASH_ENV="$PWD/_sync/gpt44/instrument.bash" bash scripts/refresh.sh`. The shell instrumentation scopes archive moves/imports to `_sync/gpt44/archive-members.json`, uses production extraction and per-game checks, records stage timings and full parse output, and checks event/identity metadata before export. No GPT-39 gate was applied.
- The refresh script prints `moved 0` because its unscoped move loop is suppressed; actual selected moves happen in the scoped import stage and are listed in `_sync/gpt44/move.log`. Import inventory and per-archive outcomes: `_sync/gpt44/archive-members.json`, `_sync/gpt44/import-summary.json`.

## Event dates and export

- Event gate: **passed**; unresolved schedules at export: **0**. No dates were invented. Config snapshot: `_sync/gpt44/events-at-export.json`.

- The lead supplied both missing schedules during the first export, after the 600-second wait. They were initially at the JSON root; moved the supplied objects into `events` without changing dates, then ran a complete second production export. No dates were invented. Original supplied file: `_sync/gpt44/events-lead-supplied.json`; repair record: `_sync/gpt44/event-registry-repair.json`; first export audit: `_sync/gpt44/first-export/`.

| Lead-supplied event | Start | End |
| --- | --- | --- |
| fissure-playground-3 | 2026-09-08 | 2026-09-13 |
| pgl-masters-bucharest-2026 | 2026-10-24 | 2026-10-31 |

## Stage wall times

```text
PREPARE elapsed=1.196 archives=73 excluded=22
SHELL_START 0
START 0 scripts/import_hltv.py
REPORT elapsed=0.041 rc=0
END 1239 elapsed=1239 rc=0 scripts/import_hltv.py
START 1239 -m playbook parse
END 2218 elapsed=979 rc=1 -m playbook parse
EVENT_WAIT elapsed=600.037 remaining=2
START 2875 -m playbook export
END 4163 elapsed=1288 rc=0 -m playbook export
START 4163 scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
END 4163 elapsed=0 rc=0 scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis
AUDIT-AFTER elapsed=1.262 rc=0
COPY elapsed=1.655 rc=0
PYTEST elapsed=21.526 rc=1
REPORT elapsed=0.022 rc=0
EXPORT_FINAL elapsed=1289.694 rc=0
AUDIT-AFTER elapsed=1.337 rc=0
COPY elapsed=1.544 rc=0
PYTEST elapsed=20.314 rc=1
REPORT elapsed=0.022 rc=0
```

## FURIA maps before → after

| Map | Published before | Published after | Parsed/deduped before | Parsed/deduped after |
| --- | --- | --- | --- | --- |
| de_ancient | 2 | 13 | 2 | 13 |
| de_anubis | 2 | 8 | 2 | 8 |
| de_cache | 5 | 13 | 5 | 13 |
| de_dust2 | 9 | 37 | 9 | 37 |
| de_inferno | 5 | 27 | 5 | 27 |
| de_mirage | 11 | 45 | 11 | 45 |
| de_nuke | 7 | 28 | 7 | 28 |
| de_overpass | 1 | 1 | 1 | 1 |

Published active-pool total (excluding historical Overpass): **41 → 171**. Parsed active-pool total: **41 → 171**. Existing historical Overpass output is preserved by the exporter and not regenerated.

## Date precision

- All deduplicated FURIA maps: `{'day': 1, 'event': 171}`; dated range **2026-01-12 → 2026-10-24**.
- New retained map rows: `{'event': 137}`; FURIA subset: `{'event': 137}`.
- Published FURIA active-pool matches: `{'event': 171}`.
`event` = configured event start; `day` = HLTV-ID schedule interpolation estimate; `exact` = explicit date override; `null` = unresolved. Neither event nor day precision is a verified match timestamp. Recent membership inherits this precision.

## Team names and player identities

| Added alias | Canonical | Reason |
| --- | --- | --- |
| G2.Esports | G2 | Obvious punctuation variant of existing G2 Esports; observed FURIA–G2 FISSURE Playground 3 demos. |

Canonical team names new to the dataset: `['9INE Pusulabet', 'Passion UA']`. See `_sync/gpt44/team-names.json`.

| New canonical name not in alias registry | New map appearances |
| --- | --- |
| 9INE Pusulabet | 2 |
| Gentle Mates | 2 |
| Monte | 1 |

Source/config changes compared with the baseline: `['config/events.json', 'config/player_aliases.csv', 'config/team_aliases.csv']`. No speculative team aliases were added. Existing obvious spelling aliases are applied by production parsing/export. Unknown names and demo IDs: `_sync/gpt44/unknown-teams.json`.

Identity audit: **0 remaining same-team/name groups with multiple Steam IDs**, after existing verified aliases. Evidence: `_sync/gpt44/identity-check.json`. New player aliases are recorded only after the all-table `(demo_id, round_num)` co-occurrence check.

Added verified `config/player_aliases.csv` row: **76561198744962365 → 76561199137143905 (yxngstxr)**. Alternate: **53 rounds / 3 maps**, BLAST Bounty S1 Finals 2026. Canonical ID already had **185 rounds** before this ingest and **265 raw rounds** before merging. **0 same-round overlaps** across loadouts, positions, attacker/victim/assister kills, plants, utility, shots and player rounds, before content dedupe. Original evidence: `_sync/gpt44/identity-check-before-alias.json`, `_sync/gpt44/yxngstxr-source-audit.json`; decision: `_sync/gpt44/identity-review.json`.

Verified canonical yxngstxr roster: `[{'steamid': '76561199137143905', 'name': 'yxngstxr', 'color': 4, 'rounds': 318}]`; alternate ID references across both JSON output trees: **0**. Evidence: `_sync/gpt44/alias-output-verification.json`.

## Duplicates and parse failures

- Content duplicates dropped: **72** (baseline **65**); cross-source duplicates: **72**; newly parsed rows dropped: **0**. Kept/dropped IDs: `_sync/gpt44/dedupe-after.json`.
- **14 parse failures**, **1 newly imported**. Broken demos did not stop the run. Full tracebacks: `_sync/gpt44/parse-full.log`.

| Scope | Demo path | Reason |
| --- | --- | --- |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p2.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p3.dem | ValueError: Incomplete rounds have no complete copy: [1] |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q/spirit-vs-b8-m1-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q/spirit-vs-b8-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| new | data/raw/hltv/esl-pro-league-season-24-furia-vs-aurora-bo3-aHdx4LZnSFU_o8let4_hJp/furia-vs-aurora-m2-mirage.dem | ValueError: Conflicting clan names within a team |
| pre-existing | data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB/luminosity-vs-spirit-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB/luminosity-vs-spirit-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/iem-cologne-major-2026-furia-vs-mouz-bo3-dC2xyK-KPviXDfpnjaMits/furia-vs-mouz-m1-nuke-p1.dem + data/raw/hltv/iem-cologne-major-2026-furia-vs-mouz-bo3-dC2xyK-KPviXDfpnjaMits/furia-vs-mouz-m1-nuke-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs/spirit-vs-liquid-m1-ancient-p1.dem + data/raw/hltv/iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs/spirit-vs-liquid-m1-ancient-p2.dem | ValueError: Part 2: round has no recognized winner |
| pre-existing | data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p1.dem + data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/pgl-cluj-napoca-2026-mouz-vs-parivision-bo3-kzRdoIlvoGHu2j8Umcovc8/mouz-vs-parivision-m1-dust2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |

FURIA–Aurora EPL S24 Mirage was rejected for conflicting team labels: the source roster labels yuurih (76561198164970560) as `Aurora Gaming`. That alias already correctly maps to Aurora, a distinct team. No alias was added to conceal the conflict. Evidence: `_sync/gpt44/aurora-clans.json`, `_sync/gpt44/aurora-clan-review.json`.

## FURIA roster: name → Steam ID → rounds

Recent = **2026-07-24 through 2026-10-24**, inclusive: three calendar months relative to the task date. Counts are distinct `(demo_id, round_num)` player rounds after content dedupe/verified aliases; whole period includes historical maps. Undated maps count only toward the whole period.

| Name | Steam ID | Last 3 months rounds | Whole-period rounds |
| --- | --- | --- | --- |
| FalleN | 76561197960690195 | 1613 | 3711 |
| KSCERATO | 76561198058500492 | 1613 | 3711 |
| YEKINDAR | 76561198134401925 | 1613 | 3711 |
| molodoy | 76561198200982290 | 1613 | 3711 |
| yuurih | 76561198164970560 | 1613 | 3711 |

Whole-period roster counts agree with exported `data/site/heatmap_teams.json`: **True**. **3711 FURIA rounds**, all with exactly five players: **True**.

Portrait IDs exactly match the recent roster: **True**. Additional recent IDs: `[]`.

| Expected portrait name | Steam ID | Observed recent name | Recent rounds | Portrait exists |
| --- | --- | --- | --- | --- |
| FalleN | 76561197960690195 | FalleN | 1613 | True |
| yuurih | 76561198164970560 | yuurih | 1613 | True |
| YEKINDAR | 76561198134401925 | YEKINDAR | 1613 | True |
| KSCERATO | 76561198058500492 | KSCERATO | 1613 | True |
| molodoy | 76561198200982290 | molodoy | 1613 | True |
Portrait files: `site-preview/players/<steamid>.png`. Evidence: `_sync/gpt44/roster-audit.json`, `_sync/gpt44/portrait-check.json`, `_sync/gpt44/roster-round-coverage.json`.

## Preview and validation

- `cp -R data/site/. site-preview/data/`: exit **0**; **4132 files checked by SHA-256**, **0 mismatches**. Existing preview extras remain untouched.
- `caffeinate -i .venv/bin/python -B -m pytest -q`: exit **1**; `7 failed, 290 passed, 3 skipped, 1 warning in 20.09s`. Log: `_sync/gpt44/pytest.log`.
- `web/`: **8966 file size/mtime records checked**, changes: `[]`. Unrelated match-download changes: `[]`. Production source/config SHA-256 changes: `['config/events.json', 'config/player_aliases.csv', 'config/team_aliases.csv']`.
- Final independent data checks: all 171 active FURIA map counts agree with deduplicated input, zero FURIA maps are undated, supplied schedules match the export snapshot, and all five portraits are indexed. Evidence: `_sync/gpt44/final-data-verification.json`.
- This checkout has no `.git`; verification uses file snapshots in `_sync/gpt44/`.
- Updated `tests/test_player_aliases.py::test_load_player_aliases` to check the seeded donk mapping without assuming the registry contains only one row. Targeted alias tests: `_sync/gpt44/pytest-aliases.log` (**11 passed**).
- Full-suite background-test failures are pre-existing: seven `test_darkroom_synthetic_image` cases expect dark output, whereas the unchanged natural-colour generator returns mean 223.67 on the white synthetic crop. The source SHA-256 matches the starting snapshot. Evidence: `_sync/gpt44/preexisting-test-failures.json`. The generator and those tests were not changed by this ingest.

## Archive details

| Archive | Maps | Imported | Duplicate | Off-pool | Failed | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| blast-bounty-2026-season-1-9ine-vs-furia-bo3-MkQoRlfBmxkBCbF0DvJmNE.rar | de_anubis, de_inferno | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-1-finals-heroic-vs-furia-bo3-lks2Hs2GKnZOSw7VzYaKtQ.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-1-finals-parivision-vs-furia-bo3-OWWuEF0tMU9bni1nLziiyX.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-1-fut-vs-furia-bo3-Ooo2A2Cr6F8fALvRMag2iD.rar | de_anubis, de_dust2, de_overpass | 2 | 0 | 1 | 0 | — |
| blast-bounty-2026-season-2-dendele-vs-furia-bo3-BgzrJtVU0wzYp6fxw601kT.rar | de_anubis, de_cache, de_mirage | 3 | 0 | 0 | 0 | — |
| blast-open-porto-2026-furia-vs-pain-bo3-MubDLaELy5MHFr4bXaUfPk.rar | de_cache, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-furia-vs-vitality-bo3-KULcN3Jf23XthDsJCBq9hT.rar | de_cache, de_dust2, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| blast-open-porto-2026-m80-vs-furia-bo3-R1DuzZH2V8D9cTvDELyPB-.rar | de_cache, de_dust2 | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-spirit-vs-furia-bo3-DLIuxJDviZLxHemrpqI9i8.rar | de_ancient, de_cache | 0 | 2 | 0 | 0 | duplicate identity |
| blast-open-rotterdam-2026-aurora-vs-furia-bo3-vH8nO4Zu3tcUldh_sQ8ejM.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-falcons-vs-furia-bo3-zp0pciKDSVhfKCDy7k3zv2.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-furia-vs-tyloo-bo3-y-6T34bM323RMIz91m8dCL.rar | de_mirage, de_overpass | 1 | 0 | 1 | 0 | — |
| blast-open-rotterdam-2026-nrg-vs-furia-bo3-LFfc9svnjaw58w44cKHkWT.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-rivals-2026-season-1-faze-vs-furia-bo3-3YtoX5_ndmrBisoeZ2F9SJ.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-rivals-2026-season-1-furia-vs-gamerlegion-bo3-qfgwNQNC_y9ZnqCCwD5twG.rar | de_inferno, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-23-stage-2-furia-vs-3dmax-bo3-Or836bgdA8NMqIsifloIVM.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-stage-2-furia-vs-astralis-bo3-qeNKaXMk9GJgED-c100Okx.rar | de_dust2, de_inferno, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-23-stage-2-furia-vs-b8-bo3-zJqO-eze9ez7IAjqmXN-tv.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-stage-2-furia-vs-heroic-bo3-zArYYvhkuQbazmRwzP-G5t.rar | de_dust2, de_inferno, de_overpass | 2 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-stage-2-furia-vs-pain-bo3-Qr99lkfl5gfsiCrfCH6Yz1.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-furia-vs-9z-bo3-_EeeERbAcm9Uje2t-MD94C.rar | de_inferno, de_nuke | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-furia-vs-aurora-bo3-aHdx4LZnSFU_o8let4_hJp.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-furia-vs-betboom-bo3-HrKVopT1MgspQOnVWtbqQ-.rar | de_cache, de_mirage | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-furia-vs-mouz-bo3-AQemmoZYCf5pJfMkkZ7dIt.rar | de_inferno, de_nuke | 0 | 2 | 0 | 0 | duplicate identity |
| esl-pro-league-season-24-furia-vs-mouz-bo3-vM7Zs--CZxiZO8U1kjgh9F.rar | de_cache, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| esl-pro-league-season-24-parivision-vs-furia-bo3-gHiq7z34UTFifZztgVskJU.rar | de_ancient, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-furia-vs-9z-bo3-1BT7QxqU1S2HcWSrbcLwWZ.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-furia-vs-aurora-bo3-8ElLAnsM7OHWsN1oO6LDhA.rar | de_ancient, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-furia-vs-fut-bo3-o4-MY_r0RKTJE9T5M-6UvG.rar | de_ancient, de_dust2, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-furia-vs-legacy-bo3-pSaQCOHjDbFDklvGLGQxvu.rar | de_ancient, de_dust2, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-g2-vs-furia-bo3-3q-KSSd6Wxfi72Ts9irMaF.rar | de_ancient, de_anubis, de_dust2 | 3 | 0 | 0 | 0 | — |
| fissure-playground-3-furia-vs-g2-bo3-HjCesaOmEm1EmqlkTW_ubg.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| fissure-playground-3-furia-vs-gamerlegion-bo3-ytYJtxdvVOKJPLQfvFobo1.rar | de_cache, de_dust2, de_mirage | 3 | 0 | 0 | 0 | — |
| fissure-playground-3-legacy-vs-furia-bo3-tWbxU-NnclaZIA3C7t-cT1.rar | de_ancient, de_mirage | 2 | 0 | 0 | 0 | — |
| fissure-playground-3-parivision-vs-furia-bo3-oqaDRCoLbOjhqoalTClzFz.rar | de_ancient, de_inferno | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-9z-vs-furia-bo3-75cz7uIfE_qsSVElgPGGkW.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-cologne-major-2026-aurora-vs-furia-bo3-MtUgV-8SDzm10cS7MVFYln.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-betboom-vs-furia-bo3-Ay-MJrMMkab9PC7QYnN27N.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-cologne-major-2026-furia-vs-b8-bo3-LSPtJbBXRrIsAojIoBTpvc.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-furia-vs-falcons-bo5-KYwh5Z9rwDlzjmTFrwu0mb.rar | de_anubis, de_inferno, de_mirage | 0 | 3 | 0 | 0 | duplicate identity |
| iem-cologne-major-2026-furia-vs-mouz-bo3-dC2xyK-KPviXDfpnjaMits.rar | de_inferno, de_nuke, de_overpass | 0 | 2 | 1 | 0 | duplicate identity |
| iem-krakw-2026-astralis-vs-furia-bo3-xudgaKgYU0Ln3aG94b9Zq9.rar | de_mirage, de_nuke, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-krakw-2026-furia-vs-aurora-bo3-0SHtb-SP2eItuD9F4xOrf3.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-furia-vs-fut-bo3-2YAkzpe_twYrzQp5b7_6q_.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-furia-vs-natus-vincere-bo3-Yy4UTf844IsWQBAQgG5QLr.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| iem-krakw-2026-furia-vs-vitality-bo5-mm8dtsK9binWQO0i_PtQVF.rar | de_inferno, de_mirage, de_nuke, de_overpass | 0 | 3 | 1 | 0 | duplicate identity |
| iem-krakw-2026-spirit-vs-furia-bo3-xg2IF7BkV4uvqIFjZDhn6_.rar | de_dust2, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| iem-krakw-2026-the-mongolz-vs-furia-bo3-osQQ2qb5QmTGPogNefNFS2.rar | de_inferno, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| iem-rio-2026-falcons-vs-furia-bo3-QxdR81Huln7yrstVaq3fnQ.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-furia-vs-mouz-bo3-Z2rTAoiITmGibqgyRsRqWD.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| iem-rio-2026-furia-vs-passion-ua-bo3-gWfKT6v0cD51rasOuCYqs4.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-furia-vs-vitality-bo3--OutGDctKNBZKy28qkTgMB.rar | de_ancient, de_overpass | 0 | 1 | 1 | 0 | duplicate identity |
| iem-rio-2026-natus-vincere-vs-furia-bo3-qLZX6MdaBCbmtkWux805qr.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| pgl-astana-2026-furia-vs-falcons-bo3-8IztXknpPEEl1NsCKq6LgX.rar | de_dust2, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| pgl-astana-2026-furia-vs-gentle-mates-bo3-bavtBEBkvCguSvfitdFrWq.rar | de_inferno, de_nuke, de_overpass | 2 | 0 | 1 | 0 | — |
| pgl-astana-2026-furia-vs-heroic-bo3-ftj_X_pYP8io6no--aXw-x.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-furia-vs-monte-bo3-EmBLEcPGN4n_QRIcUwYoHp.rar | de_nuke, de_overpass | 1 | 0 | 1 | 0 | — |
| pgl-astana-2026-furia-vs-spirit-bo3-EOF1N3EPnLVYSd7SJXSkzP.rar | de_dust2, de_mirage, de_overpass | 0 | 2 | 1 | 0 | duplicate identity |
| pgl-cluj-napoca-2026-furia-vs-b8-bo3-7rXlQ0z4N2waa-0Yt666Fu.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-furia-vs-falcons-bo3-OfIsfrpSwnaD_LueyZEScm.rar | de_anubis, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-furia-vs-fut-bo3-HbuNe8W0g4NKkKGrtjg94O.rar | de_anubis, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| pgl-cluj-napoca-2026-furia-vs-parivision-bo3-Wowc5KzueGNaKKWlTthpDh.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-furia-vs-the-mongolz-bo3-uvTP_jPQxvkgKOfIm8feIR.rar | de_dust2, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| pgl-masters-bucharest-2026-furia-vs-dendele-bo3-4fiS232Z31yAz9TtPWxxXN.rar | de_ancient, de_inferno | 2 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-furia-vs-mibr-bo3-rSv3cKIpaBU3z-5k-LbjC8.rar | de_cache, de_inferno, de_nuke | 3 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-mibr-vs-furia-bo3-uHN5dgPTlEkFdIqOSgSoSY.rar | de_mirage, de_nuke | 2 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-mouz-vs-furia-bo3-4nJ64OX1scgBdZLnojD1I2.rar | de_cache, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| starladder-starseries-fall-2026-vitality-vs-furia-bo3-HgWry2z6SZbWx6OAju7RT-.rar | de_anubis, de_cache | 0 | 2 | 0 | 0 | duplicate identity |
| starladder-starseries-fall-2026-vitality-vs-furia-bo3-T02CXrqqgCdzggCxkdcv3r.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| thunderpick-world-championship-2026-furia-vs-aurora-bo3-EvTUc7zohJvV3jcFASmDIT.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| thunderpick-world-championship-2026-furia-vs-betboom-bo3-UGaXtgpe7fp5k0C7EQw_AX.rar | de_ancient, de_mirage | 2 | 0 | 0 | 0 | — |
| thunderpick-world-championship-2026-furia-vs-betboom-bo5-WHIRt9tsXT6rseHazRIbi8.rar | de_ancient, de_cache, de_dust2, de_mirage, de_nuke | 5 | 0 | 0 | 0 | — |
| thunderpick-world-championship-2026-legacy-vs-furia-bo3-decMt23HeUp2jsOvlynIdo.rar | de_cache, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |

## Follow-up

- No missing schedules remain after the supplied-date repair and second export.
- Review the seven pre-existing background-test expectations against the natural-colour renderer.
- Review or re-download failed recordings; incomplete histories were rejected. Review newly observed canonical team names before adding aliases.
