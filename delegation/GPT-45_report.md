# GPT-45 — Backend v4.1 report

Implemented the backend brief in `playbook/ct_patterns.py`, `playbook/ai_lab.py`, `playbook/export.py`, and `tests/test_ai_lab.py`. No files under `web/` were edited by this job.

Resumed from interrupted partial edits; the earlier export completed at 06:04 UTC. Replaced the frequency-first label selection and third-callout collision fallback, retained and reviewed the existing pistol/replay/SHAP changes, then reran the complete export and tests.

## Behavior and data contract

- CT analysis excludes regulation rounds 1 and 13 before spawn references and feature extraction. Overtime starts remain eligible. Excluded counts are available in both `metadata.excluded_pistol_rounds` and `counts.excluded_pistol_rounds`; all other exclusions and cluster shares use the remaining rounds.
- Economy × cluster tests use eco/force/full columns (empty columns are removed for the test). `chi_square.n` is the included contingency-table count; `cramers_v` is `sqrt(chi_square / (N * min(rows - 1, columns - 1)))`. Degenerate tables return V=0, p=1, with an insufficient-categories caveat. `p_display` uses `p < 0.0001` below the threshold, otherwise three significant digits.
- Labels apportion 15s region means to exactly five players. Within each count-prefix group, callout lift is `cluster observation share - mean(other sibling observation shares)` at available seconds 15–20 among the original five CT members. Only positive lift is eligible. Each callout (including Chinese aliases) belongs to its strongest-lift sibling; each cluster takes at most two eligible callouts in descending lift order. Singleton prefixes use frequency. Depth thirds add 前顶 / 保守 (forward / conservative); indistinguishable summaries get neutral sample numbers. No third-callout collision suffix remains.
- Interpretation of common callouts: omit the intersection of each sibling’s two most frequent callouts, including translated aliases. Presence alone is not a useful exclusion rule: nearly every Mirage callout occurs at least once in both large sibling clusters. This removes the ubiquitous A包点 from both duplicated Mirage prefixes while retaining distinctive observed positions. `label_callouts_15_20s` exposes the chosen canonical callout IDs; `callouts_15_20s` retains the full counts/shares for audit. Chinese names reuse `config/route_names.json` and existing Cache/Overpass vocabulary. Parsed `place` values reuse the existing map callout lookup.
- AI Lab runs after normal replay export and extends the per-map replay index for missing medoids and selected SHAP/control examples. Every cluster medoid and attention round has `replay_available: true`; every embedding point has a boolean reflecting the indexed file. Unavailable scatter samples remain explicitly false for the frontend to disable.
- `shap.active_groups` is computed from nonzero contributions across all exported states; `inactive_groups_note_zh` is the requested four-feature-group explanation. The win-probability model, features, and fitting code are unchanged. The mandatory standard export reruns its existing fold-fitting pipeline; exported model metrics are exactly equal to the pre-change metrics.

## Per-map statistics

The repository contains the seven active-pool maps plus historical Overpass; all eight are included below so the extra parsed data receives the same fixes.

| Map | Excluded pistols | Included N | Clusters | χ² | df | Cramér’s V | p display |
|---|---:|---:|---:|---:|---:|---:|---|
| de_ancient | 170 | 1731 | 6 | 471.5143 | 10 | 0.369049 | p < 0.0001 |
| de_anubis | 116 | 1125 | 6 | 132.4209 | 10 | 0.242598 | p < 0.0001 |
| de_cache | 60 | 574 | 6 | 39.4223 | 10 | 0.185311 | p < 0.0001 |
| de_dust2 | 362 | 3314 | 6 | 654.1192 | 10 | 0.314150 | p < 0.0001 |
| de_inferno | 220 | 2074 | 6 | 123.3255 | 10 | 0.172428 | p < 0.0001 |
| de_mirage | 322 | 3060 | 6 | 462.0653 | 10 | 0.274774 | p < 0.0001 |
| de_nuke | 228 | 2215 | 6 | 270.3672 | 10 | 0.247044 | p < 0.0001 |
| de_overpass | 12 | 115 | 2 | 9.0780 | 2 | 0.280960 | p = 0.0107 |

## Exported labels

### de_ancient

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | 中3·B2（中路/B包点 前顶） | M3-B2 (Middle/BombsiteB forward) | 358 |
| C1 | A1·B4（B包点/B侧门） | A1-B4 (BombsiteB/SideEntrance) | 88 |
| C2 | A1·中2·B2（中路/B包点 前顶） | A1-M2-B2 (Middle/BombsiteB forward) | 271 |
| C3 | A1·中1·B3（B包点/房屋 保守） | A1-M1-B3 (BombsiteB/House conservative) | 394 |
| C4 | A2·中1·B2（A包点/B侧门 保守） | A2-M1-B2 (BombsiteA/SideEntrance conservative) | 416 |
| C5 | A2·B3（B包点/A包点） | A2-B3 (BombsiteB/BombsiteA) | 204 |

### de_anubis

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A1·中2·B2（水渠/桥 前顶） | A1-M2-B2 (Canal/Bridge forward) | 103 |
| C1 | A1·中1·B3（B包点/中路 前顶） | A1-M1-B3 (BombsiteB/Middle forward) | 163 |
| C2 | A1·中2·B2（A包点/走道 保守） | A1-M2-B2 (BombsiteA/Walkway conservative) | 167 |
| C3 | A1·中2·B2（A/A小道） | A1-M2-B2 (Main/Fountain) | 318 |
| C4 | A2·中1·B2（B包点/A 保守） | A2-M1-B2 (BombsiteB/Main conservative) | 256 |
| C5 | A2·B3（B包点/A） | A2-B3 (BombsiteB/Main) | 118 |

### de_cache

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A1·中2·B2（棋盘房/警家连接） | A1-M2-B2 (Checkers/Connector) | 75 |
| C1 | A1·中2·B2（B包点/四箱 前顶） | A1-M2-B2 (BombsiteB/Quad forward) | 114 |
| C2 | A1·中1·B2·警1（B包点/棋盘房 保守） | A1-M1-B2-CT1 (BombsiteB/Checkers conservative) | 139 |
| C3 | A2·中1·B2（棋盘房/中路） | A2-M1-B2 (Checkers/Mid) | 69 |
| C4 | A2·中1·B2（警家连接/警家通道 保守） | A2-M1-B2 (Connector/CTLane conservative) | 108 |
| C5 | A2·中1·B2（B包点/A区大厅 前顶） | A2-M1-B2 (BombsiteB/AHalls forward) | 69 |

### de_dust2

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A1·中1·B3（B包点/B洞 前顶） | A1-M1-B3 (BombsiteB/LowerTunnel forward) | 192 |
| C1 | A3·中1·B1（B包点/A大 保守） | A3-M1-B1 (BombsiteB/LongA conservative) | 839 |
| C2 | A2·中1·B2（B包点/A大） | A2-M1-B2 (BombsiteB/LongA) | 1012 |
| C3 | A3·中1·B1（A小/A台下 保守） | A3-M1-B1 (Catwalk/UnderA conservative) | 235 |
| C4 | A3·B2（B包点/A大 前顶） | A3-B2 (BombsiteB/LongA forward) | 748 |
| C5 | A4·B1（A大/B包点） | A4-B1 (LongA/BombsiteB) | 288 |

### de_inferno

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A1·中1·B3（B包点/香蕉道） | A1-M1-B3 (BombsiteB/Banana) | 355 |
| C1 | A1·中2·B2（香蕉道/中路 前顶） | A1-M2-B2 (Banana/TopofMid forward) | 232 |
| C2 | A2·中1·B2（中路/拱门 保守） | A2-M1-B2 (TopofMid/Arch conservative) | 368 |
| C3 | A2·B3（B包点/A包点 前顶） | A2-B3 (BombsiteB/BombsiteA forward) | 316 |
| C4 | A2·中1·B2（A二楼/四箱） | A2-M1-B2 (Apartments/Quad) | 518 |
| C5 | A2·B2·警1（B包点/A包点 保守） | A2-B2-CT1 (BombsiteB/BombsiteA conservative) | 285 |

### de_mirage

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A2·中2·B1（拱门/警家） | A2-M2-B1 (Connector/CTSpawn) | 490 |
| C1 | A2·中2·B1（白车/VIP） | A2-M2-B1 (Truck/SnipersNest) | 887 |
| C2 | A2·中1·B1·警1（B包点/拱门 保守） | A2-M1-B1-CT1 (BombsiteB/Connector conservative) | 579 |
| C3 | A2·中1·B1·警1（A二楼/B小 保守） | A2-M1-B1-CT1 (PalaceInterior/Catwalk conservative) | 568 |
| C4 | A2·中1·B2（A包点/B包点 前顶） | A2-M1-B2 (BombsiteA/BombsiteB forward) | 352 |
| C5 | A3·中1·B1（A包点/A二楼 前顶） | A3-M1-B1 (BombsiteA/PalaceInterior forward) | 184 |

### de_nuke

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A2·中2·B1（车库/B坡道 前顶） | A2-M2-B1 (Garage/Ramp forward) | 352 |
| C1 | A2·中2·B1（横梁/高架通道 保守） | A2-M2-B1 (Rafters/Catwalk conservative) | 434 |
| C2 | A2·中2·B1（A包点/下层通道 保守） | A2-M2-B1 (BombsiteA/Tunnels conservative) | 310 |
| C3 | A2·中1·B2（B坡道/A包点 前顶） | A2-M1-B2 (Ramp/BombsiteA forward) | 168 |
| C4 | A3·中1·B1（外场/正门） | A3-M1-B1 (Outside/Mini) | 630 |
| C5 | A3·中1·B1（高架通道/办公室） | A3-M1-B1 (Catwalk/Admin) | 321 |

### de_overpass

| ID | 中文 | English | n |
|---|---|---|---:|
| C0 | A2·中1·B2（走道/水域 保守） | A2-M1-B2 (Walkway/Water conservative) | 55 |
| C1 | A2·中1·B2（上公园/水渠 前顶） | A2-M1-B2 (UpperPark/Canal forward) | 60 |

## Mirage label review: same-prefix siblings

Shared dominant callouts are removed before lift ranking. Each row below is a selected, sibling-exclusive callout; lift is in percentage points of 15–20s callout observations.

| Cluster | Prefix | Selected callout | Own share | Sibling mean share | Lift |
|---|---|---|---:|---:|---:|
| C0 | A2·中2·B1 | 拱门 / Connector | 8.59% | 5.17% | +3.42 pp |
| C0 | A2·中2·B1 | 警家 / CTSpawn | 7.79% | 4.72% | +3.07 pp |
| C1 | A2·中2·B1 | 白车 / Truck | 10.06% | 4.29% | +5.77 pp |
| C1 | A2·中2·B1 | VIP / SnipersNest | 11.03% | 9.24% | +1.79 pp |
| C2 | A2·中1·B1·警1 | B包点 / BombsiteB | 12.85% | 7.69% | +5.16 pp |
| C2 | A2·中1·B1·警1 | 拱门 / Connector | 5.81% | 2.99% | +2.82 pp |
| C3 | A2·中1·B1·警1 | A二楼 / PalaceInterior | 8.94% | 1.77% | +7.16 pp |
| C3 | A2·中1·B1·警1 | B小 / Catwalk | 9.75% | 6.45% | +3.30 pp |

## Replay and SHAP verification

| Map | Medoids with frames | Available scatter points | Disabled scatter points |
|---|---:|---:|---:|
| de_ancient | 6/6 | 380 | 1351 |
| de_anubis | 6/6 | 340 | 785 |
| de_cache | 6/6 | 38 | 536 |
| de_dust2 | 6/6 | 767 | 2547 |
| de_inferno | 6/6 | 331 | 1743 |
| de_mirage | 6/6 | 609 | 2451 |
| de_nuke | 6/6 | 344 | 1871 |
| de_overpass | 2/2 | 2 | 113 |

- 44/44 medoids have actual replay frames. 2811 scatter points are available; 11397 are explicitly disabled.
- SHAP active groups: `alive_diff`, `hp_equipment`, `map_control`, `bomb_state_time`.
- Chinese note: 当前模型只使用 4 组特征：人数差、血量与装备、区域占位、C4 与倒计时。
- SHAP: 3 examples, 313 states; maximum additivity residual 2.22e-16.
- Model metrics unchanged: 745 matches; accuracy 75.24%; log loss 0.4571.

## Commands and validation

```sh
caffeinate -i env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=4 PYTHONUNBUFFERED=1 .venv/bin/python -m playbook export
cp -R data/site/. site-preview/data/
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=4 .venv/bin/python -m pytest -q
```

- Focused label/replay/SHAP numerical tests: **15 passed, 1 deselected** (the real-data contract was deferred until regeneration).
- Full export: completed successfully; log `_sync/gpt45/export.log`.
- Preview data: copied and verified byte-for-byte against every file in `data/site/`; existing preview-only files preserved.
- Full pytest (log `_sync/gpt45/pytest.log`): 301 passed, 3 skipped in 19.77s.
- Tests cover pistol exclusion and overtime retention, pistol spawn-reference isolation, label uniqueness and five-player prefixes in both languages, positive-lift ranking, disjoint same-prefix callout sets, translated aliases, the two-callout cap, known χ²/effect-size cases, missing/empty replay repair and index merging, active SHAP groups, and regenerated real-data contracts.

## Limits / frontend handoff

- The frontend job must consume the availability flags and active groups to disable unavailable scatter points and hide inactive SHAP bars. No frontend files were changed here.
- χ² is a descriptive round-level association. Rounds within a match are not independent; the existing small-expected-cell caveat remains available. Historical Overpass has a much smaller sample than the active maps.


- Audit: `_sync/gpt45/audit.json` records preview equality, unchanged model metrics, replay coverage, and observed concurrent `web/` changes. This backend task performed no web writes and did not revert frontend work.

- The hash comparison observed 7913 concurrent changes under `web/`, including `web/src/components/CTTrajectories.tsx` and `web/src/lab.css` plus generated data/assets; these were preserved.
