# GPT-39 backend report

Implemented `playbook/ct_patterns.py` and `playbook/ai_lab.py`, hooked into `playbook/export.py`. `playbook/winprob.py` optionally retains fold models and their existing isotonic calibrators for exact attribution without retraining a surrogate. Schema: `delegation/GPT-39_schema.md`. No files under `web/` were edited.

- Validation: 293 passed, 3 skipped; every map identical across two independent builds
- Lab step runtime: 35.6 seconds (excludes existing model fitting and the other export steps).
- Encoder: Torch absent in `.venv`; lightweight 103-feature standardisation → PCA ≤64 → KMeans (K=6, n_init=20, random_state=42), per map. Labels and IDs derive from data; IDs sort by 15s A share.
- TAGNet paper validation covers Dust2 only (697 rounds). The exported metadata explicitly discloses extrapolation to all parsed maps. No paper outcome percentages or cluster labels are copied.
- Attention is a distance kernel, not learned attention. τ=0.25; self edges included.
- Wilson 95% intervals accompany all CT win rates. χ² sparse expected-cell warnings are exported. Fingerprints require ≥30 included CT rounds.

## Per-map clusters

### de_ancient

CT rounds: 1431; excluded at 10s: 15; incomplete snapshots: 13; included: 1403.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | 中路联防 | 287 | 20.5% | 54.0% |
| C1 | B 区重防 · A 12.4% | 89 | 6.3% | 21.3% |
| C2 | B 区+中路联防 · A 13.0% | 233 | 16.6% | 61.4% |
| C3 | B 区+中路联防 · 前压深度 36.3% | 283 | 20.2% | 55.8% |
| C4 | B 区+中路联防 · A 29.8% | 305 | 21.7% | 58.4% |
| C5 | B 区重防 · A 40.0% | 206 | 14.7% | 47.6% |

Economy × cluster: χ²=452.9773, dof=15, p=4.84712e-87. Expected cells below 5; asymptotic p-value may be unreliable

### de_anubis

CT rounds: 1128; excluded at 10s: 5; incomplete snapshots: 1; included: 1122.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | 中路联防 · A 9.8% | 106 | 9.4% | 53.8% |
| C1 | B 区重防 · A 23.3% | 166 | 14.8% | 44.6% |
| C2 | 中路联防 · A 24.4% | 158 | 14.1% | 36.1% |
| C3 | B 区+中路联防 | 322 | 28.7% | 54.7% |
| C4 | 双点均衡 | 253 | 22.5% | 49.0% |
| C5 | B 区重防 · A 47.5% | 117 | 10.4% | 43.6% |

Economy × cluster: χ²=147.8541, dof=15, p=6.43201e-24. Expected cells below 5; asymptotic p-value may be unreliable

### de_cache

CT rounds: 331; excluded at 10s: 7; incomplete snapshots: 1; included: 323.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | B 区+中路联防 | 47 | 14.6% | 46.8% |
| C1 | 中路联防 | 86 | 26.6% | 53.5% |
| C2 | 双点均衡 · A 26.0% | 87 | 26.9% | 66.7% |
| C3 | 双点均衡 · A 40.4% | 54 | 16.7% | 50.0% |
| C4 | 双点均衡 · A 45.2% | 42 | 13.0% | 35.7% |
| C5 | A 区重防 | 7 | 2.2% | 14.3% |

Economy × cluster: χ²=108.5452, dof=15, p=3.06595e-16. Expected cells below 5; asymptotic p-value may be unreliable

### de_dust2

CT rounds: 2808; excluded at 10s: 129; incomplete snapshots: 8; included: 2671.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | B 区重防 | 183 | 6.9% | 42.1% |
| C1 | A 区重防 · MID 23.1% | 708 | 26.5% | 55.4% |
| C2 | A 区重防 · A 49.2% | 759 | 28.4% | 55.3% |
| C3 | A 区重防 · B 17.1% | 200 | 7.5% | 35.5% |
| C4 | A 区重防 · B 40.0% | 579 | 21.7% | 55.3% |
| C5 | A 区重防 · A 73.0% | 242 | 9.1% | 43.8% |

Economy × cluster: χ²=600.8542, dof=15, p=2.33779e-118. 

### de_inferno

CT rounds: 1427; excluded at 10s: 7; incomplete snapshots: 3; included: 1417.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | 中路联防 | 81 | 5.7% | 50.6% |
| C1 | B 区重防 · A 23.9% | 276 | 19.5% | 52.2% |
| C2 | 双点均衡 · MID 21.9% | 268 | 18.9% | 61.2% |
| C3 | B 区重防 · A 36.1% | 215 | 15.2% | 51.6% |
| C4 | 双点均衡 · CT_SPAWN 12.4% | 217 | 15.3% | 52.1% |
| C5 | 双点均衡 · MID 10.6% | 360 | 25.4% | 55.0% |

Economy × cluster: χ²=219.6141, dof=15, p=2.13601e-38. Expected cells below 5; asymptotic p-value may be unreliable

### de_mirage

CT rounds: 2260; excluded at 10s: 30; incomplete snapshots: 4; included: 2226.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | 中路联防 · B 22.8% | 627 | 28.2% | 69.2% |
| C1 | 中路联防 · B 16.9% | 330 | 14.8% | 52.4% |
| C2 | 双点均衡 · A 33.8% | 372 | 16.7% | 61.0% |
| C3 | 双点均衡 · MID 24.9% | 458 | 20.6% | 61.1% |
| C4 | 双点均衡 · MID 7.4% | 170 | 7.6% | 51.2% |
| C5 | A 区重防 | 269 | 12.1% | 48.7% |

Economy × cluster: χ²=393.7734, dof=15, p=1.40598e-74. 

### de_nuke

CT rounds: 1712; excluded at 10s: 2; incomplete snapshots: 17; included: 1693.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | 双点均衡 · MID 36.3% | 355 | 21.0% | 57.2% |
| C1 | 中路联防 | 402 | 23.7% | 62.9% |
| C2 | 双点均衡 · OTHER 40.0% | 1 | 0.1% | 0.0% |
| C3 | 双点均衡 · B 38.5% | 157 | 9.3% | 47.8% |
| C4 | A 区重防 · A 53.6% | 474 | 28.0% | 61.8% |
| C5 | A 区重防 · A 58.1% | 304 | 18.0% | 58.9% |

Economy × cluster: χ²=195.5340, dof=15, p=1.71392e-33. Expected cells below 5; asymptotic p-value may be unreliable

### de_overpass

CT rounds: 128; excluded at 10s: 0; incomplete snapshots: 0; included: 128.

| ID | Label | n | Share | CT win |
|---|---|---:|---:|---:|
| C0 | B 区重防 | 22 | 17.2% | 59.1% |
| C1 | 双点均衡 · 前压深度 36.0% | 35 | 27.3% | 71.4% |
| C2 | 双点均衡 · A 38.7% | 30 | 23.4% | 70.0% |
| C3 | 双点均衡 · 前压深度 27.4% | 19 | 14.8% | 73.7% |
| C4 | A 区重防 · A 55.0% | 20 | 15.6% | 60.0% |
| C5 | A 区重防 · A 90.0% | 2 | 1.6% | 0.0% |

Economy × cluster: χ²=64.3641, dof=15, p=4.41522e-08. Expected cells below 5; asymptotic p-value may be unreliable

## Falcons / Vitality / Spirit fingerprints

Usage is compared against the included CT-round-weighted pro average on that map. Δ is percentage points; all qualifying team × map records are below.

### Falcons

| Map | CT n | Cluster usage (Δ pp vs pro) |
|---|---:|---|
| de_ancient | 156 | C0 24.4% (+3.9); C1 5.8% (-0.6); C2 13.5% (-3.1); C3 16.7% (-3.5); C4 19.9% (-1.9); C5 19.9% (+5.2) |
| de_anubis | 153 | C0 15.0% (+5.6); C1 21.6% (+6.8); C2 13.1% (-1.0); C3 18.3% (-10.4); C4 17.6% (-4.9); C5 14.4% (+4.0) |
| de_cache | <30 | insufficient qualifying rounds |
| de_dust2 | 339 | C0 7.4% (+0.5); C1 31.0% (+4.5); C2 22.1% (-6.3); C3 9.4% (+2.0); C4 19.2% (-2.5); C5 10.9% (+1.9) |
| de_inferno | 139 | C0 5.0% (-0.7); C1 30.9% (+11.5); C2 16.5% (-2.4); C3 25.9% (+10.7); C4 3.6% (-11.7); C5 18.0% (-7.4) |
| de_mirage | 235 | C0 21.3% (-6.9); C1 14.9% (+0.1); C2 20.0% (+3.3); C3 27.7% (+7.1); C4 7.7% (+0.0); C5 8.5% (-3.6) |
| de_nuke | 139 | C0 13.7% (-7.3); C1 22.3% (-1.4); C2 0.0% (-0.1); C3 9.4% (+0.1); C4 27.3% (-0.7); C5 27.3% (+9.4) |
| de_overpass | <30 | insufficient qualifying rounds |

### Vitality

| Map | CT n | Cluster usage (Δ pp vs pro) |
|---|---:|---|
| de_ancient | 36 | C0 8.3% (-12.1); C1 5.6% (-0.8); C2 22.2% (+5.6); C3 13.9% (-6.3); C4 25.0% (+3.3); C5 25.0% (+10.3) |
| de_anubis | 213 | C0 6.6% (-2.9); C1 10.3% (-4.5); C2 18.8% (+4.7); C3 24.4% (-4.3); C4 28.2% (+5.6); C5 11.7% (+1.3) |
| de_cache | 81 | C0 19.8% (+5.2); C1 30.9% (+4.2); C2 33.3% (+6.4); C3 7.4% (-9.3); C4 8.6% (-4.4); C5 0.0% (-2.2) |
| de_dust2 | 332 | C0 4.2% (-2.6); C1 31.6% (+5.1); C2 34.9% (+6.5); C3 6.0% (-1.5); C4 19.3% (-2.4); C5 3.9% (-5.1) |
| de_inferno | 245 | C0 4.5% (-1.2); C1 12.2% (-7.2); C2 20.0% (+1.1); C3 6.9% (-8.2); C4 24.5% (+9.2); C5 31.8% (+6.4) |
| de_mirage | 303 | C0 30.0% (+1.9); C1 16.5% (+1.7); C2 17.8% (+1.1); C3 16.5% (-4.1); C4 7.9% (+0.3); C5 11.2% (-0.9) |
| de_nuke | 244 | C0 19.3% (-1.7); C1 27.9% (+4.1); C2 0.0% (-0.1); C3 7.4% (-1.9); C4 24.2% (-3.8); C5 21.3% (+3.4) |
| de_overpass | <30 | insufficient qualifying rounds |

### Spirit

| Map | CT n | Cluster usage (Δ pp vs pro) |
|---|---:|---|
| de_ancient | 218 | C0 23.9% (+3.4); C1 5.5% (-0.8); C2 14.7% (-1.9); C3 28.4% (+8.3); C4 19.3% (-2.5); C5 8.3% (-6.4) |
| de_anubis | 172 | C0 7.0% (-2.5); C1 5.8% (-9.0); C2 16.9% (+2.8); C3 25.6% (-3.1); C4 41.3% (+18.7); C5 3.5% (-6.9) |
| de_cache | 81 | C0 7.4% (-7.1); C1 30.9% (+4.2); C2 28.4% (+1.5); C3 21.0% (+4.3); C4 11.1% (-1.9); C5 1.2% (-0.9) |
| de_dust2 | 364 | C0 6.9% (+0.0); C1 15.1% (-11.4); C2 22.0% (-6.4); C3 4.1% (-3.4); C4 44.2% (+22.6); C5 7.7% (-1.4) |
| de_inferno | <30 | insufficient qualifying rounds |
| de_mirage | 355 | C0 33.2% (+5.1); C1 12.4% (-2.4); C2 18.9% (+2.2); C3 20.0% (-0.6); C4 2.3% (-5.4); C5 13.2% (+1.2) |
| de_nuke | 175 | C0 10.9% (-10.1); C1 20.0% (-3.7); C2 0.0% (-0.1); C3 5.7% (-3.6); C4 38.9% (+10.9); C5 24.6% (+6.6) |
| de_overpass | <30 | insufficient qualifying rounds |

## Lab outputs and limitations

- Exact 64-coalition Shapley: 3 rounds / 313 per-second states; max additivity error 2.22e-16. Background: up to 32 deterministic same-map training states; the explained match is excluded from both model fitting and background sampling.
- Explained probabilities equal the existing calibrated OOF predictions to 1e-6; map and pre-round score are held fixed.
- The existing win-probability model consumes lane occupancies, not replay `t_control`, active utility, or positional spread/pinch. `map_control` attributes lane inputs; observed `t_control` is exported alongside each state. The last two feature groups have exact zero contributions. Extending the predictive model to consume these fields is future work.
- Model accuracy is copied from `winprob_metrics.json`: 0.7474. No advertised accuracy is hard-coded.
- Control grid: 225 Mirage XY cells, with the original observed-cell mask; inactive cells are neutral. Distances are straight-line approximations, not NavMesh geodesics. Smoke adds 450 world units to each crossing player-to-cell segment before nearest-distance selection. Walls and floors are not modelled.
- References are restricted to the six items approved in the brief.

- SHAP example: Falcons · de_mirage · `9z-vs-falcons-m2-mirage` round 3 (121 states, 32 background states).
- SHAP example: Vitality · de_mirage · `aurora-vs-vitality-m3-mirage` round 1 (68 states, 32 background states).
- SHAP example: Spirit · de_mirage · `2394865_spirit-vs-betboom-mirage` round 3 (124 states, 32 background states).

Mirage control example: `9z-vs-falcons-m2-mirage` round 3. Smoke at 53s: T control 41.57% → 40.45%, Δ -1.1236 pp (computed, not tuned).

## Verification / handoff

- Tests cover permutation-invariant feature shapes, deterministic IDs and labels, known χ² cases, analytic Shapley interactions/dummy groups, calibrated OOF equivalence, actual JSON contracts, and smoke path geometry. The existing export repeatability test remains passing.
- Full export: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=4 .venv/bin/python -m playbook export`.
- Sync: `cp -R data/site/. site-preview/data/`.
- Tests: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=4 .venv/bin/python -m pytest -q`.
- Frontend can consume the TypeScript-ready schema directly. It should keep the method and model-input limitations visible.
