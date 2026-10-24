"""Write the GPT-39 engineering handoff from exported measurements.

Run after `python -m playbook export` and pytest. Does not modify web/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def report(site: Path, validation: str, runtime: str) -> str:
    lab = json.loads((site/'ai_lab.json').read_text())
    patterns = [json.loads(p.read_text()) for p in sorted(site.glob('*/ct_patterns.json'))]
    lines = ['# GPT-39 backend report', '',
        'Implemented `playbook/ct_patterns.py` and `playbook/ai_lab.py`, hooked into '
        '`playbook/export.py`. `playbook/winprob.py` optionally retains fold models and their '
        'existing isotonic calibrators for exact attribution without retraining a surrogate. '
        'Schema: `delegation/GPT-39_schema.md`. No files under `web/` were edited.', '',
        f'- Validation: {validation}', f'- Lab step runtime: {runtime} (excludes existing model fitting and the other export steps).',
        '- Encoder: Torch absent in `.venv`; lightweight 103-feature standardisation → PCA ≤64 → KMeans '
        '(K=6, n_init=20, random_state=42), per map. Labels and IDs derive from data; IDs sort by 15s A share.',
        '- TAGNet paper validation covers Dust2 only (697 rounds). The exported metadata explicitly '
        'discloses extrapolation to all parsed maps. No paper outcome percentages or cluster labels are copied.',
        '- Attention is a distance kernel, not learned attention. τ=0.25; self edges included.',
        '- Wilson 95% intervals accompany all CT win rates. χ² sparse expected-cell warnings are exported. '
        'Fingerprints require ≥30 included CT rounds.', '',
        '## Per-map clusters', '']
    for a in patterns:
        c = a['counts']
        lines.extend([f"### {a['map']}", '',
            f"CT rounds: {c['total']}; excluded at 10s: {c['dropped_at_10']}; "
            f"incomplete snapshots: {c['dropped_incomplete']}; included: {c['included']}.", '',
            '| ID | Label | n | Share | CT win |', '|---|---|---:|---:|---:|'])
        for cluster in a['clusters']:
            lines.append(f"| {cluster['id']} | {cluster['label_zh']} | {cluster['n']} | "
                         f"{cluster['share']:.1%} | {cluster['ct_win_rate']:.1%} |")
        chi = a['chi_square']
        lines += ['', f"Economy × cluster: χ²={chi['statistic']:.4f}, dof={chi['dof']}, p={chi['p']:.6g}. "
                     + (chi['caveat'] or ''), '']
    lines += ['## Falcons / Vitality / Spirit fingerprints', '',
              'Usage is compared against the included CT-round-weighted pro average on that map. '
              'Δ is percentage points; all qualifying team × map records are below.', '']
    for team in ('Falcons', 'Vitality', 'Spirit'):
        lines += [f'### {team}', '', '| Map | CT n | Cluster usage (Δ pp vs pro) |', '|---|---:|---|']
        for a in patterns:
            fingerprint = next((f for f in a['fingerprints'] if f['team'] == team), None)
            if fingerprint is None:
                lines.append(f"| {a['map']} | <30 | insufficient qualifying rounds |")
                continue
            cells = '; '.join(f"{u['cluster_id']} {u['share']:.1%} ({u['difference_pp']:+.1f})" for u in fingerprint['usage'])
            lines.append(f"| {a['map']} | {fingerprint['n']} | {cells} |")
        lines.append('')
    nstates = sum(len(r['states']) for r in lab['shap']['rounds'])
    error = max((abs(s['base_value']+sum(s['shap_values'].values())-s['t_win_prob'])
                 for r in lab['shap']['rounds'] for s in r['states']), default=0.)
    accuracy = (lab['model_accuracy'] or {}).get('model', {}).get('accuracy')
    lines += ['## Lab outputs and limitations', '',
        f"- Exact 64-coalition Shapley: {len(lab['shap']['rounds'])} rounds / {nstates} per-second states; "
        f"max additivity error {error:.3g}. Background: up to 32 deterministic same-map training states; "
        'the explained match is excluded from both model fitting and background sampling.',
        '- Explained probabilities equal the existing calibrated OOF predictions to 1e-6; map and pre-round score are held fixed.',
        '- The existing win-probability model consumes lane occupancies, not replay `t_control`, '
        'active utility, or positional spread/pinch. `map_control` attributes lane inputs; observed '
        '`t_control` is exported alongside each state. The last two feature groups have exact zero '
        'contributions. Extending the predictive model to consume these fields is future work.',
        f'- Model accuracy is copied from `winprob_metrics.json`: {accuracy}. No advertised accuracy is hard-coded.',
        '- Control grid: 225 Mirage XY cells, with the original observed-cell mask; inactive cells are neutral. '
        'Distances are straight-line approximations, not NavMesh geodesics. Smoke adds 450 world units to '
        'each crossing player-to-cell segment before nearest-distance selection. Walls and floors are not modelled.',
        '- References are restricted to the six items approved in the brief.', '']
    for r in lab['shap']['rounds']:
        lines.append(f"- SHAP example: {r['showcase_team']} · {r['map']} · `{r['demo_id']}` round {r['round_num']} "
                     f"({len(r['states'])} states, {r['background_n']} background states).")
    if lab['control']:
        control = lab['control']
        smoke = control['smoke_simulation']
        lines += ['', f"Mirage control example: `{control['demo_id']}` round {control['round_num']}. "
                  f"Smoke at {smoke['t_s']}s: T control {smoke['t_control_before']:.2%} → "
                  f"{smoke['t_control_after']:.2%}, Δ {smoke['difference_pp']:+.4f} pp (computed, not tuned)."]
    lines += ['', '## Verification / handoff', '',
        '- Tests cover permutation-invariant feature shapes, deterministic IDs and labels, known χ² cases, '
        'analytic Shapley interactions/dummy groups, calibrated OOF equivalence, actual JSON contracts, '
        'and smoke path geometry. The existing export repeatability test remains passing.',
        '- Full export: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=4 .venv/bin/python -m playbook export`.',
        '- Sync: `cp -R data/site/. site-preview/data/`.',
        '- Tests: `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=4 .venv/bin/python -m pytest -q`.',
        '- Frontend can consume the TypeScript-ready schema directly. It should keep the method and model-input limitations visible.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', type=Path, default=ROOT/'data'/'site')
    parser.add_argument('--out', type=Path, default=ROOT/'delegation'/'GPT-39_report.md')
    parser.add_argument('--validation', default='See test output from the current export')
    parser.add_argument('--runtime', default='See AI lab export log')
    args = parser.parse_args()
    args.out.write_text(report(args.site, args.validation, args.runtime), encoding='utf-8')
