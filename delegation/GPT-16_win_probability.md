# GPT-16 回合胜率模型与动作价值（派给 Codex，经 PAL clink）

---

Repo: `~/Downloads/cs2-pro-playbook` (Python pipeline, `.venv` with scikit-learn installed by the owner). Another Codex session may edit `web/` — do not touch `web/` except `web/src/types.ts` (additive types only).

Background: Szmida & Toka (MIT Sloan 2025) predict per-frame round win probability with a temporal heterogeneous GNN and value actions by the change in win probability; Xenopoulos et al. (arXiv 2011.01324, the awpy author) do the same for CS:GO with simpler models. We implement the simple, reproducible version on our parsed tables.

## 0. First
`config/team_aliases.csv` now maps `FLC` → Falcons. Run `.venv/bin/python -m playbook export` once and report Falcons' per-map match counts (dedupe from GPT-15 must stay on).

## 1. Model — `playbook/winprob.py`
- Training rows: game states sampled every 1 s (or every 4th snapshot) during live play of each round, from `data/parsed` after GPT-15 de-duplication. Exclude knife/warmup.
- Features (T-side perspective): alive T/CT, summed HP T/CT, equipment value T/CT (alive players), armor/helmet/defuser counts, time remaining in the round (or bomb timer after plant), bomb planted flag and site, map one-hot, counts of alive players per side in each lane/zone (A / mid / B / T-side / CT-side, from the existing region/lane labels), distance of nearest T to each bombsite.
- Label: T wins the round.
- Model: `sklearn.ensemble.HistGradientBoostingClassifier`; calibrate (isotonic or Platt) on a held-out split; **split by match** (GroupKFold on demo_id) so the same match never appears in train and test.
- Report: log loss, Brier score, accuracy, calibration table (10 bins) on the test folds, vs a baseline that only uses alive counts + time. Save the model to `data/models/winprob.joblib` (gitignored) and metrics to `data/models/winprob_metrics.json`.

## 2. Action values
- For every kill, death, grenade detonation (smoke/molotov/flash/HE), plant and defuse: ΔWP = WP(state just after, ~1 s) − WP(state just before), from the acting player's team perspective.
- Aggregate and export (additive fields, documented in DESIGN.md):
  - per player per map and side: `wpa_per_round` (sum of ΔWP / rounds), `wpa_kills`, `wpa_utility`, top 3 actions;
  - per recipe (tactics.json): mean ΔWP of the execute (WP at commit − 5 s vs commit + 10 s) and mean WP when the recipe starts;
  - per round: the WP timeline (1 s resolution, rounded to 0.01) for the team page / match replay later — write it only for Falcons' matches for now to keep files small (`data/site/<map>/winprob/<demo_id>.json`).
- Tests: synthetic tables for feature building, group split leakage check (no demo in both folds), ΔWP sign conventions. Run `.venv/bin/python -m pytest -q` and the export.

## Deliverable
`delegation/GPT-16_report.md`: metrics vs baseline, calibration, top features, Falcons players' `wpa_per_round` per map, the 5 recipes with the highest mean ΔWP, and anything unsure. If scikit-learn is missing, stop and say so in the report.
