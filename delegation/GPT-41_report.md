# GPT-41 MOUZ ingest report

Status: **in progress / see stage logs**.

## Import and parsing

- Found **64 MOUZ archives**, **44,697,434,338 bytes**. Moved 50; preserved 14 existing destinations. Archives were retained.
- Preserved **8 unrelated HLTV downloads**. Full inventories: `_sync/gpt41/archive-members.json`, `_sync/gpt41/excluded-downloads.json`.
- Selected archives: **110 imported games**, **37 duplicate identity skips**, **11 off-pool skips**, **0 import failures**. 50 archives contributed imports; 14 contributed none.
- Full refresh incidental imports from pre-existing non-selected archives: **0**. Detailed results: `_sync/gpt41/import-summary.json`.
- Newly parsed map demos: **108**; new MOUZ rows retained after dedupe: **108**.
- Import was scoped to the 64 selected MOUZ archives using the production extractor and per-game import checks in `_sync/gpt41/import_stage.py`. The initial full historical rescan was cancelled; six newly copied demos were preserved under `_sync/gpt41/interrupted-raw/` and re-imported cleanly to avoid retaining any interrupted copy. Stage logs retain the cancelled attempts.
- Ran `bash scripts/refresh.sh` with `BASH_ENV=_sync/gpt41/instrument.bash` for scoped archive moves, stage timings, full parse logging and pre-export gates. Production source and scripts were not edited. `web/`, `playbook/ct_patterns.py` and `playbook/ai_lab.py` were not edited by this ingest job.

## Export ordering and event dates

- GPT-39 round 2 gate: **timeout**; waited **900.161 seconds**; section: `not observed yet`. Checks run every 60 seconds, for at most 60 minutes, before export. Evidence: `_sync/gpt41/gpt39-poll.log`, `_sync/gpt41/gpt39-report-at-export.md`.
- Missing event schedules at final check: **0**. No event dates were invented. Event schedule snapshot: `_sync/gpt41/events-at-export.json`.

## Stage wall times

```text
PREPARE elapsed=0.854 archives=64 excluded=8
SHELL_START 0
MOVE elapsed=0
START 0 scripts/import_hltv.py
INITIAL_IMPORT_CANCELLED: scoped 64 selected archives; full historical rescan avoided
SHELL_START 0
MOVE elapsed=0
START 0 scripts/import_hltv.py
SHELL_START 0
MOVE elapsed=0
START 0 scripts/import_hltv.py
SHELL_START 0
MOVE elapsed=0
START 0 scripts/import_hltv.py
END 1084 elapsed=1084 rc=0 scripts/import_hltv.py
START 1084 -m playbook parse
END 1860 elapsed=776 rc=1 -m playbook parse
GPT39_WAIT timeout wall_elapsed=29643.905 observed_monotonic=900.161 checks=16; NO_EXPORT
PYTEST elapsed=21.191 rc=0
```

## MOUZ maps before → after

| Map | Published before | Published after | Deduplicated parsed |
| --- | --- | --- | --- |
| de_ancient | 7 | 7 | 19 |
| de_anubis | 0 | 0 | 0 |
| de_cache | 1 | 1 | 7 |
| de_dust2 | 14 | 14 | 34 |
| de_inferno | 6 | 6 | 27 |
| de_mirage | 12 | 12 | 35 |
| de_nuke | 11 | 11 | 24 |
| de_overpass | 0 | 0 | 0 |

Published active-pool total (excludes historical Overpass): **51 → 51**.

## Date precision

- All deduplicated MOUZ maps: `{'day': 1, 'event': 145}`; date range **2026-01-28 → 2026-10-03**.
- Newly parsed maps retained by content dedupe: `{'event': 108}`; MOUZ subset: `{'event': 108}`.
- Published MOUZ active-pool profiles: `{'event': 37, 'day': 14}`.
`event` means configured event start; `day` means an HLTV-ID interpolation estimate; `exact` means an explicit date override; `null` means unresolved. Date ranges and the recent roster window inherit that precision.

## Team names and player identities

| New canonical name not in alias registry | New map appearances |
| --- | --- |
| FOKUS | 2 |
| Gentle Mates | 3 |
| Nuclear TigeRES | 2 |
| magic | 2 |

No speculative aliases were added. Team aliases already normalize obvious existing spellings; newly observed canonical candidates above are listed for review. Exact demo IDs: `_sync/gpt41/unknown-teams.json`.

Player identity audit found **0 remaining same-name / multiple-ID groups**, after existing verified aliases. New `config/player_aliases.csv` rows: **0**. Evidence: `_sync/gpt41/identity-check.json`.

## Duplicates and parse failures

- Content duplicates dropped: **65**, baseline **52**; cross-source duplicates: **65**. Newly parsed rows dropped: **0**. Detailed kept/dropped IDs: `_sync/gpt41/dedupe-after.json`.
- Parse failures: **13** (2 newly imported). Broken demos did not stop other games. Full traceback: `_sync/gpt41/parse-full.log`.

| Scope | Demo path | Reason |
| --- | --- | --- |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394773-b8-vs-tyloo-iem-cologne-major-2026-stage-1/b8-vs-tyloo-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394845-m80-vs-sharks-iem-cologne-major-2026-stage-1/m80-vs-sharks-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p2.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394881-monte-vs-legacy-iem-cologne-major-2026-stage-2/monte-vs-legacy-ancient-p3.dem | ValueError: Incomplete rounds have no complete copy: [1] |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394885-b8-vs-gamerlegion-iem-cologne-major-2026-stage-2/b8-vs-gamerlegion-m1-inferno-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p1.dem + data/raw/cs2povarchive/iem_cologne_major_2026/2394971-furia-vs-mouz-iem-cologne-major/furia-vs-mouz-m1-nuke-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q/spirit-vs-b8-m1-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-23-stage-2-spirit-vs-b8-bo3-yoFdNgX69x2aaIWbhMEv1q/spirit-vs-b8-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p1.dem + data/raw/hltv/esl-pro-league-season-24-falcons-vs-natus-vincere-bo3-3Y4ykAiGXZrr2p0dvri2C9/falcons-vs-natus-vincere-m3-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-falcons-vs-astralis-bo3-8OSQG1t8N4d5BnOd-4S3m7/falcons-vs-astralis-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB/luminosity-vs-spirit-m1-ancient-p1.dem + data/raw/hltv/esports-world-cup-2026-luminosity-vs-spirit-bo3-5zkz1BErF0dwAyXR0jKoQB/luminosity-vs-spirit-m1-ancient-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| new | data/raw/hltv/iem-cologne-major-2026-furia-vs-mouz-bo3-dC2xyK-KPviXDfpnjaMits/furia-vs-mouz-m1-nuke-p1.dem + data/raw/hltv/iem-cologne-major-2026-furia-vs-mouz-bo3-dC2xyK-KPviXDfpnjaMits/furia-vs-mouz-m1-nuke-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| pre-existing | data/raw/hltv/iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs/spirit-vs-liquid-m1-ancient-p1.dem + data/raw/hltv/iem-rio-2026-spirit-vs-liquid-bo3-hqiOEyrzam4W4LtTob5Zrs/spirit-vs-liquid-m1-ancient-p2.dem | ValueError: Part 2: round has no recognized winner |
| pre-existing | data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p1.dem + data/raw/hltv/iem-rio-2026-vitality-vs-natus-vincere-bo3-uFptDDHw379gQSG-jLrk6r/vitality-vs-natus-vincere-m1-mirage-p2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |
| new | data/raw/hltv/pgl-cluj-napoca-2026-mouz-vs-parivision-bo3-kzRdoIlvoGHu2j8Umcovc8/mouz-vs-parivision-m1-dust2.dem | ValueError: Incomplete or restored round history: need consecutive rounds starting at 1 |

## MOUZ roster: name → Steam ID → rounds

Recent = **2026-07-24 through 2026-10-24**, inclusive (three calendar months relative to the task date). Counts are distinct `(demo_id, round_num)` player rounds after content dedupe and verified aliases. Whole period includes historical maps; recent dates use the precision described above.

| Name | Steam ID | Recent rounds | Whole-period rounds |
| --- | --- | --- | --- |
| Brollan | 76561198138828475 | 0 | 1187 |
| Jimpphat | 76561198855375325 | 0 | 1006 |
| PR | 76561198310561479 | 1310 | 1310 |
| Spinx | 76561198063336407 | 1310 | 3122 |
| jL | 76561198176878303 | 0 | 625 |
| torzsi | 76561198355739212 | 1310 | 3122 |
| xelex | 76561198998266210 | 1310 | 2116 |
| xertioN | 76561198193174134 | 1310 | 3122 |

Exported roster source: `data/site/heatmap_teams.json` (8 identities). Independently recomputed player-round counts agree with the export: **None**.

## Preview and tests

- `cp -R data/site/. site-preview/data/`: exit **None**, **0** generated files compared by SHA-256; mismatches: **0**.
- `.venv/bin/python -m pytest -q`: exit **0**; `296 passed, 3 skipped in 20.94s`. Log: `_sync/gpt41/pytest.log`.

## Archive details

| Archive | Maps | Imported | Duplicate | Off-pool | Failed | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| blast-bounty-2026-season-2-finals-3dmax-vs-mouz-bo3-2GZ-7ujSl175S4d4wrpQAP.rar | de_dust2, de_inferno, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-finals-astralis-vs-mouz-bo3-GL6fIr97PN55FAkr3XSu7F.rar | de_ancient, de_dust2, de_mirage | 3 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-finals-spirit-vs-mouz-bo5--wn1awkp4iFRmswi58ug57.rar | de_ancient, de_dust2, de_mirage, de_nuke | 0 | 4 | 0 | 0 | duplicate identity |
| blast-bounty-2026-season-2-fokus-vs-mouz-bo3-5lm0SkLmjUMrO_TBE5e5qq.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-bounty-2026-season-2-nuclear-tigeres-vs-mouz-bo3-ebQxWf7iEoB5eaKtGYzf97.rar | de_ancient, de_nuke | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-inner-circle-vs-mouz-bo3-ssCYIosT42NoQRvjJQOAui.rar | de_ancient, de_mirage | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-mouz-vs-9z-bo3-fnGIdV3faPuq_oJcQbmF4s.rar | de_cache, de_nuke | 2 | 0 | 0 | 0 | — |
| blast-open-porto-2026-mouz-vs-falcons-bo3-prw6BqDfxCxFQUiDy4b4ey.rar | de_ancient, de_inferno, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| blast-open-porto-2026-mouz-vs-vitality-bo3-V3i93ufoKzBC0MBPii8PGf.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| blast-open-porto-2026-spirit-vs-mouz-bo5-sZmuJNNeP4vy0G6o8VuS_u.rar | de_ancient, de_dust2, de_mirage, de_nuke | 0 | 4 | 0 | 0 | duplicate identity |
| blast-open-rotterdam-2026-mouz-vs-9z-bo3-uHRpKn3rXGI5DYr9rA9MEo.rar | de_dust2, de_inferno, de_nuke | 3 | 0 | 0 | 0 | — |
| blast-open-rotterdam-2026-mouz-vs-the-mongolz-bo3-mdEx2QIh_CL5B8AE5ckJp7.rar | de_inferno, de_nuke | 2 | 0 | 0 | 0 | — |
| cs-asia-championships-2026-b8-vs-mouz-bo3-yEqj9Xtfb0MKLEI6xpiWmk.rar | de_ancient, de_overpass | 1 | 0 | 1 | 0 | — |
| cs-asia-championships-2026-falcons-vs-mouz-bo3--bPrjLQ2TP-mMaeM2Zy1DS.rar | de_dust2, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| cs-asia-championships-2026-m80-vs-mouz-bo3-K8BOqmEH09jyXZ1PmLSv8Y.rar | de_inferno, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| cs-asia-championships-2026-mouz-vs-mibr-bo3-L0hlthaQQ6K4Go0uZPMjWg.rar | de_ancient, de_overpass | 1 | 0 | 1 | 0 | — |
| cs-asia-championships-2026-mouz-vs-pain-bo3-2ixs2bpHtUSx3e-0ECa9h2.rar | de_nuke, de_overpass | 1 | 0 | 1 | 0 | — |
| cs-asia-championships-2026-nrg-vs-mouz-bo3-CRFreBMCPVPJVZAHQ1VNmf.rar | de_ancient, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-23-finals-mouz-vs-fut-bo3-JBl40cwhFZKQ8JMmkxP4VS.rar | de_dust2, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-stage-2-mouz-vs-astralis-bo3-MnL0qh_PiLDaVIIr-9W24r.rar | de_ancient, de_mirage, de_overpass | 2 | 0 | 1 | 0 | — |
| esl-pro-league-season-23-stage-2-mouz-vs-heroic-bo3-cxoiZzfrdLP28C5KHdPUuv.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| esl-pro-league-season-23-stage-2-mouz-vs-the-mongolz-bo3-ViB55INzIaobVF_kkbF6XP.rar | de_ancient, de_overpass | 1 | 0 | 1 | 0 | — |
| esl-pro-league-season-24-furia-vs-mouz-bo3-AQemmoZYCf5pJfMkkZ7dIt.rar | de_inferno, de_nuke | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-furia-vs-mouz-bo3-vM7Zs--CZxiZO8U1kjgh9F.rar | de_cache, de_mirage | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-mouz-vs-m80-bo3-_aBGdI5aLEO4sdGnjzfcZT.rar | de_cache, de_mirage | 2 | 0 | 0 | 0 | — |
| esl-pro-league-season-24-mouz-vs-spirit-bo3-sqctTxs0ADRlg-g18Xysab.rar | de_dust2, de_mirage, de_nuke | 0 | 3 | 0 | 0 | duplicate identity |
| esl-pro-league-season-24-spirit-vs-mouz-bo3-1EAS0FkXk363N7dvfZunnl.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| esl-pro-league-season-24-vitality-vs-mouz-bo5-HHVdkDbJrwRclevPphxD2-.rar | de_cache, de_dust2, de_inferno | 0 | 3 | 0 | 0 | duplicate identity |
| esports-world-cup-2026-fut-vs-mouz-bo3-qVyLGT2Gvu2SDaIG5B_gMZ.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| esports-world-cup-2026-fut-vs-mouz-bo3-y2tUP23LPdKvpCZCEKG3KK.rar | de_ancient, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-gamerlegion-vs-mouz-bo3-mP2q-GsUznSGgohB8Xd2Ga.rar | de_ancient, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| esports-world-cup-2026-mouz-vs-parivision-bo3-CNjSTW-OJOcy5aOcOdBcN8.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-furia-vs-mouz-bo3-dC2xyK-KPviXDfpnjaMits.rar | de_inferno, de_nuke, de_overpass | 2 | 0 | 1 | 0 | — |
| iem-cologne-major-2026-mouz-vs-fut-bo3-vQt8pRuSzsbHnHmzHXAXQZ.rar | de_ancient, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-mouz-vs-legacy-bo3--ElOVseOL1THYQayaTTDSJ.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| iem-cologne-major-2026-vitality-vs-mouz-bo3-E9khg_TX6BxGaIZNKJ3X1O.rar | de_dust2, de_inferno, de_mirage | 0 | 3 | 0 | 0 | duplicate identity |
| iem-krakw-2026-falcons-vs-mouz-bo3-0NmDSYe_8UmJAHamjCMBo8.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-g2-vs-mouz-bo3-UF-ur5s86qDKU2ldf4aDm5.rar | de_dust2, de_overpass | 1 | 0 | 1 | 0 | — |
| iem-krakw-2026-mouz-vs-aurora-bo3-QZePMng7xycADr_e1iC2pu.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-mouz-vs-faze-bo3-777zRHG-4_gkPdPO3SCIHr.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-mouz-vs-nrg-bo3-0ctVRKXMrinTWci6ybknvL.rar | de_ancient, de_dust2 | 2 | 0 | 0 | 0 | — |
| iem-krakw-2026-spirit-vs-mouz-bo3-CEc0ZCsgWfgqi6LSlIvIKf.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| iem-krakw-2026-vitality-vs-mouz-bo3-UD0TEnJpRupm9E_EHc4hZG.rar | de_dust2, de_nuke | 0 | 2 | 0 | 0 | duplicate identity |
| iem-rio-2026-furia-vs-mouz-bo3-Z2rTAoiITmGibqgyRsRqWD.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-legacy-vs-mouz-bo3-WLoUZF6r4vRd6oQTBDXyY4.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| iem-rio-2026-mouz-vs-aurora-bo3-zxoPbQXwcJ85j6kfPHgr_s.rar | de_dust2, de_mirage | 2 | 0 | 0 | 0 | — |
| iem-rio-2026-spirit-vs-mouz-bo3-LLeNrfxqmFATTTqxsNE47B.rar | de_dust2, de_mirage | 0 | 2 | 0 | 0 | duplicate identity |
| pgl-astana-2026-mouz-vs-9z-bo3-jmXnFh-GccQVB9VXNn2W77.rar | de_ancient, de_inferno, de_nuke | 3 | 0 | 0 | 0 | — |
| pgl-astana-2026-mouz-vs-aurora-bo3-7v1mBqJ4l5KJN7j7YaEwKL.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-mouz-vs-aurora-bo3-nSGl8QLc6t_xuBxu8U5gl4.rar | de_dust2, de_nuke | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-mouz-vs-g2-bo3-yJWNdKTuWPZkrwynmoK5Gu.rar | de_dust2, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| pgl-astana-2026-mouz-vs-gentle-mates-bo3-s0PcA1JHYgs5qnMJ8IHlqy.rar | de_ancient, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| pgl-astana-2026-mouz-vs-magic-bo3-5cj1DEhMI6AgOO3VchljuY.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| pgl-astana-2026-mouz-vs-spirit-bo3-_ww1ZOkFS016IKZt45YjUx.rar | de_dust2, de_nuke | 0 | 2 | 0 | 0 | duplicate identity |
| pgl-cluj-napoca-2026-mouz-vs-fut-bo3-K16bryMvg5QmoTExlDn6wj.rar | de_mirage, de_overpass | 1 | 0 | 1 | 0 | — |
| pgl-cluj-napoca-2026-mouz-vs-natus-vincere-bo3-df-t_0_ASkWYD7zhNGcnjC.rar | de_ancient, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-mouz-vs-parivision-bo3-kzRdoIlvoGHu2j8Umcovc8.rar | de_dust2, de_inferno, de_overpass | 2 | 0 | 1 | 0 | — |
| pgl-cluj-napoca-2026-mouz-vs-the-mongolz-bo3-oP1nj_XCVRujdIf-_j5BE5.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-mouz-vs-vitality-bo3-k_w5VQbpH9bZlYTAZc8SyE.rar | de_dust2, de_inferno | 0 | 2 | 0 | 0 | duplicate identity |
| pgl-cluj-napoca-2026-natus-vincere-vs-mouz-bo3-pF5CAlIN1EQAXuMyzVH3dm.rar | de_inferno, de_mirage | 2 | 0 | 0 | 0 | — |
| pgl-cluj-napoca-2026-parivision-vs-mouz-bo3-O9ErX8PSVdmQ-SDHz9KJUT.rar | de_dust2, de_inferno | 2 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-mouz-vs-furia-bo3-4nJ64OX1scgBdZLnojD1I2.rar | de_cache, de_mirage, de_nuke | 3 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-mouz-vs-natus-vincere-bo3-wTg1fxgq_wavTerF_uOtKS.rar | de_cache, de_inferno, de_mirage | 3 | 0 | 0 | 0 | — |
| starladder-starseries-fall-2026-mouz-vs-nrg-bo3-UcUFCq1OhZJzucP9rt1ysH.rar | de_cache, de_dust2, de_inferno | 3 | 0 | 0 | 0 | — |

Roster completeness: **3122 rounds**, all with exactly five players: **True**. Evidence: `_sync/gpt41/roster-round-coverage.json`.

## Follow-up

- Review or re-download the broken demo recordings listed above; no incomplete round history was silently accepted.
- Review new canonical team-name candidates before adding identities. The roster window uses available event/interpolated dates, not verified exact match dates.
