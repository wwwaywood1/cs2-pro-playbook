"""Static research lab: exact model attributions and computed distance control.

References inform the methods; all displayed measurements come from local demos.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

import numpy as np
import polars as pl
from threadpoolctl import threadpool_limits

from playbook import ct_patterns, replay, winprob
from playbook.config import load_map
from playbook.semantics import round_plants

GROUPS = ('alive_diff', 'hp_equipment', 'map_control', 'bomb_state_time',
          'active_utility', 'positional_spread_pinch')
BACKGROUND_SIZE = 32
REFERENCES = [
    dict(id='tagnet', title='TAGNet: Temporal Attention Graph Network for Defensive Tactical Pattern Recognition in Professional Counter-Strike 2',
         authors='Zhang et al.', venue='IEEE Transactions on Games', year=2026,
         doi='10.1109/TG.2026.3745970', url='https://doi.org/10.1109/TG.2026.3745970'),
    dict(id='valuing-actions', title='Valuing Player Actions in Counter-Strike: Global Offensive',
         authors='Xenopoulos et al.', venue='IEEE Big Data', year=2020,
         url='https://arxiv.org/abs/2011.01324'),
    dict(id='sports-gnn', title='Graph Neural Networks to Predict Sports Outcomes',
         authors='Xenopoulos & Silva', venue='IEEE Big Data', year=2021,
         url='https://ieeexplore.ieee.org/search/searchresult.jsp?queryText=Graph%20Neural%20Networks%20to%20Predict%20Sports%20Outcomes'),
    dict(id='shap', title='A Unified Approach to Interpreting Model Predictions',
         authors='Lundberg & Lee', venue='NeurIPS', year=2017,
         url='https://proceedings.neurips.cc/paper/2017/hash/8a20a8621978632d76c43dfd28b67767-Paper.pdf'),
    dict(id='map-architecture', title='Impact of Map Architecture on Competitive Balance in Counter-Strike 2',
         authors='Zanevskyy, Paskiv, Khudoba', venue='International Journal of Sports and Physical Education 11(2):43–48', year=2025,
         doi='10.20431/2454-6380.1102005', url='https://doi.org/10.20431/2454-6380.1102005'),
    dict(id='spray-complexity', title='Complexity Analysis in Counter Strike 2 Spray Patterns',
         authors='Santos & Garcia', venue='SBGames', year=2026,
         url='https://sol.sbc.org.br/index.php/sbgames/article/view/45428'),
]


def model_groups(names: list[str]) -> list[list[int]]:
    alive = {'alive_T', 'alive_CT', 'alive_diff'}
    hp = {'hp_T', 'hp_CT', 'equip_T', 'equip_CT', 'equip_diff'}
    lanes = {f'{s}_{lane}' for s in ('T', 'CT') for lane in winprob.LANES}
    bomb = {'time_left', 'planted', 'planted_A'}
    return [[i for i, name in enumerate(names) if name in fields] for fields in (alive, hp, lanes, bomb, set(), set())]


def exact_shapley(predict, x: np.ndarray, background: np.ndarray,
                  groups: list[list[int]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Enumerate all 2^G coalitions; cache coalitions equivalent under empty groups.

    Other inputs are conditioned on the target. Each background row preserves
    within-group dependence and comes from a different training match.
    """
    n, ng = len(x), len(groups)
    active = [i for i, cols in enumerate(groups) if cols]
    values = np.empty((n, 1 << ng))
    cache = {}
    for mask in range(1 << ng):
        key = tuple(i for i in active if mask & (1 << i))
        if key not in cache:
            hybrid = np.repeat(x[:, None, :], len(background), axis=1)
            for i in active:
                if i not in key:
                    hybrid[:, :, groups[i]] = background[None, :, groups[i]]
            cache[key] = np.asarray(predict(hybrid.reshape(-1, x.shape[1]))).reshape(n, -1).mean(axis=1)
        values[:, mask] = cache[key]
    phi = np.zeros((n, ng))
    for i in range(ng):
        for mask in range(1 << ng):
            if mask & (1 << i):
                continue
            size = mask.bit_count()
            weight = math.factorial(size)*math.factorial(ng-size-1)/math.factorial(ng)
            phi[:, i] += weight*(values[:, mask | (1 << i)]-values[:, mask])
    return values[:, 0], phi, values[:, -1]


def _key(demo: str, rnd: int) -> pl.Expr:
    return (pl.col('demo_id') == demo) & (pl.col('round_num') == rnd)


def choose_rounds(t: dict) -> list[tuple[str, dict]]:
    """One planted Mirage round for Falcons and each additional showcase team."""
    if 'rounds' not in t or not {'ct_team', 't_team', 'dur_s'} <= set(t['rounds'].columns):
        return []
    matches = dict(t['matches'].select('demo_id', 'map').iter_rows())
    planted = set(round_plants(t).select('demo_id', 'round_num').iter_rows())
    result = []
    for team in ('Falcons', 'Vitality', 'Spirit'):
        rows = t['rounds'].filter((pl.col('ct_team') == team) | (pl.col('t_team') == team)).sort('demo_id', 'round_num').to_dicts()
        rows = [r for r in rows if (r['demo_id'], r['round_num']) in planted and r['dur_s'] >= 25]
        rows.sort(key=lambda r: (matches[r['demo_id']] != 'de_mirage', r['demo_id'], r['round_num']))
        if rows:
            result.append((team, dict(rows[0], map=matches[rows[0]['demo_id']])))
    return result


def _observed_control(pos: pl.DataFrame, grid: np.ndarray) -> dict[int, float | None]:
    return {int(s): replay.t_control(p.filter(pl.col('side') == 'T').select('x', 'y').to_numpy(),
                                   p.filter(pl.col('side') == 'CT').select('x', 'y').to_numpy(), grid)
            for (s,), p in pos.filter(pl.col('alive')).group_by('t_s')}


@threadpool_limits.wrap(limits=1)
def shap_rounds(t: dict, wpr: dict | None, selected: list[tuple[str, dict]]) -> dict:
    out = dict(method='exact_interventional_group_shapley_64_coalitions', groups=list(GROUPS),
        background_size=BACKGROUND_SIZE, limitations=[
            'Existing model uses lane occupancies as spatial inputs; replay t_control is observed separately and is not a model feature.',
            'Active utility and positional spread/pinch are not inputs to the existing model and have zero attribution.',
            'Map and pre-round score are held fixed; background size is capped at 32 to bound export runtime.',
            'Explains calibrated match-held-out model, not a separately trained surrogate.'], rounds=[])
    if not wpr or not wpr.get('model_artifacts'):
        out['limitations'].append('No trained model artifacts available; no attributions emitted.')
        return out
    d = wpr['states']
    grids = {}
    for team, row in selected:
        demo, rnd, map_name = row['demo_id'], row['round_num'], row['map']
        artifact = next(a for a in wpr['model_artifacts'] if demo in a['test_demos'])
        states = d.filter(_key(demo, rnd)).sort('t_s')
        candidates = d.filter((pl.col('map') == map_name) & ~pl.col('demo_id').is_in(sorted(artifact['test_demos']))).sort('demo_id', 'round_num', 't_s')
        if candidates.is_empty() or states.is_empty():
            continue
        rng = np.random.default_rng(42)
        background = candidates[rng.choice(candidates.height, min(BACKGROUND_SIZE, candidates.height), replace=False).tolist()]
        x, names = winprob.feature_matrix(states, artifact['maps'])
        bg, _ = winprob.feature_matrix(background, artifact['maps'])
        def predict(xs):
            return artifact['calibrator'].predict(artifact['model'].predict_proba(xs)[:, 1])
        base, phi, p = exact_shapley(predict, x, bg, model_groups(names))
        if not np.allclose(base+phi.sum(axis=1), p, atol=1e-6, rtol=0):
            raise AssertionError('Shapley additivity failed')
        mask = (d['demo_id'] == demo) & (d['round_num'] == rnd)
        if not np.allclose(p, wpr['oof'][mask.to_numpy()], atol=1e-6, rtol=0):
            raise AssertionError('Explained model differs from exported OOF predictions')
        if map_name not in grids:
            ids = t['matches'].filter(pl.col('map') == map_name)['demo_id']
            grids[map_name] = replay.control_grid(t['positions'].filter(pl.col('demo_id').is_in(ids.implode())))
        pos = t['positions'].filter(_key(demo, rnd) & (pl.col('t_s') >= 0))
        controls = _observed_control(pos, grids[map_name])
        out['rounds'].append(dict(map=map_name, demo_id=demo, round_num=int(rnd), showcase_team=team,
            model='existing_hist_gradient_boosting_match_oof_plus_isotonic', background_n=len(bg),
            states=[dict(t_s=int(second), base_value=float(base[i]), t_win_prob=float(p[i]),
                         shap_values=dict(zip(GROUPS, phi[i].tolist())), observed_t_control=controls.get(int(second)))
                    for i, second in enumerate(states['t_s'])]))
    return out


def nearest_distances(players: np.ndarray, grid: np.ndarray, smoke=None) -> np.ndarray:
    """Nearest straight path, with penalty BEFORE minimising across players."""
    if not len(players):
        return np.full(len(grid), np.inf)
    start = players[None, :, :]
    vector = grid[:, None, :]-start
    distances = np.linalg.norm(vector, axis=2)
    if smoke is not None:
        center, radius, penalty = smoke
        fraction = np.clip(((np.asarray(center)-start)*vector).sum(axis=2)/np.maximum((vector*vector).sum(axis=2), 1e-12), 0, 1)
        closest = start+fraction[:, :, None]*vector
        crosses = np.linalg.norm(closest-center, axis=2) <= radius
        distances += crosses*penalty
    return distances.min(axis=1)


def ownership(t: np.ndarray, ct: np.ndarray, grid: np.ndarray, occupied: np.ndarray, smoke=None) -> tuple[list[str], list, float | None]:
    td, cd = nearest_distances(t, grid, smoke), nearest_distances(ct, grid, smoke)
    with np.errstate(invalid='ignore'):
        delta = cd-td
    owner = np.where(td < cd, 'T', np.where(cd < td, 'CT', 'neutral'))
    owner[~occupied] = 'neutral'
    control = float(((td < cd) & occupied).sum()/occupied.sum()) if occupied.any() and (len(t) or len(ct)) else None
    return owner.tolist(), [float(v) if np.isfinite(v) and occupied[i] else None for i, v in enumerate(delta)], control


def control_example(t: dict, selected: list[tuple[str, dict]]) -> dict | None:
    row = next((r for team, r in selected if team == 'Falcons' and r['map'] == 'de_mirage'), None)
    if row is None:
        return None
    demo, rnd = row['demo_id'], row['round_num']
    mm = load_map('de_mirage')
    ids = t['matches'].filter(pl.col('map') == 'de_mirage')['demo_id'].to_list()
    map_pos = t['positions'].filter(pl.col('demo_id').is_in(ids) & (pl.col('t_s') >= 0))
    xy = map_pos.select('x', 'y').to_numpy()
    xy = xy[np.isfinite(xy).all(axis=1)]
    low, high = xy.min(axis=0), xy.max(axis=0)
    size = np.maximum(high-low, 1.)/15
    ij = np.array([(i, j) for j in range(15) for i in range(15)])
    grid = low+(ij+.5)*size
    occupied_cells = set(map(tuple, np.clip(((xy-low)/size).astype(int), 0, 14)))
    occupied = np.array([tuple(v) in occupied_cells for v in ij])
    pos = map_pos.filter(_key(demo, rnd) & pl.col('alive'))
    def players(second):
        p = pos.filter(pl.col('t_s') == second)
        return tuple(p.filter(pl.col('side') == s).select('x', 'y').to_numpy() for s in ('T', 'CT'))
    plant = float(round_plants(t).filter(_key(demo, rnd))['plant_t_s'].min())
    plan = t['team_rounds'].filter(_key(demo, rnd) & (pl.col('side') == 'T')).row(0, named=True)
    execute = plan.get('exec_start_s')
    before = max(0, int(min(execute if execute is not None else plant-5, plant-1))-1)
    seconds = sorted(pos['t_s'].unique().to_list())
    def sampled(target):
        return min(seconds, key=lambda s: (abs(s-target), s))
    phases = [('round_start', sampled(0)), ('before_execute', sampled(before)), ('after_plant', sampled(math.ceil(plant)))]
    snapshots = []
    for phase, second in phases:
        owner, delta, control = ownership(*players(second), grid, occupied)
        snapshots.append(dict(phase=phase, t_s=int(second), ownership=owner, delta_distance=delta, t_control=control))
    # Actual observed SnipersNest anchor, otherwise observed MID centroid; never tune for desired effect.
    anchor = map_pos.filter(pl.col('place') == 'SnipersNest')
    if anchor.is_empty():
        anchor = map_pos.filter(pl.col('lane') == 'MID')
    center = np.nanmedian(anchor.select('x', 'y').to_numpy(), axis=0)
    second = phases[1][1]
    owner0, _, c0 = ownership(*players(second), grid, occupied)
    owner1, _, c1 = ownership(*players(second), grid, occupied, smoke=(center, 144., 450.))
    cells = [dict(index=i, gx=int(ij[i, 0]), gy=int(ij[i, 1]), radar_x=float(mm.to_radar(*p)[0]),
                  radar_y=float(mm.to_radar(*p)[1]), occupied=bool(occupied[i])) for i, p in enumerate(grid)]
    return dict(map='de_mirage', demo_id=demo, round_num=int(rnd), grid_size=15,
        method='Existing occupied 15x15 XY replay grid; straight-line nearest-player distances, no NavMesh or walls',
        cells=cells, snapshots=snapshots,
        smoke_simulation=dict(t_s=int(second), center_world=center.tolist(), center_radar=list(mm.to_radar(*center)),
            radius_units=144., penalty_units=450, ownership_before=owner0, ownership_after=owner1,
            t_control_before=c0, t_control_after=c1, difference_pp=100*(c1-c0) if c0 is not None and c1 is not None else None))


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')


def export(t: dict, out_dir: Path, wpr: dict | None) -> dict:
    start = time.monotonic()
    attention = []
    for map_name in sorted(t['matches']['map'].unique().to_list()):
        ids = t['matches'].filter(pl.col('map') == map_name)['demo_id'].to_list()
        sub = {k: v.filter(pl.col('demo_id').is_in(ids)) for k, v in t.items() if k in ('positions', 'team_rounds')}
        patterns, edges = ct_patterns.build(sub, load_map(map_name))
        _write(out_dir/map_name/'ct_patterns.json', patterns)
        attention.extend(edges)
    selected = choose_rounds(t)
    metrics = out_dir/'winprob_metrics.json'
    obj = dict(schema_version=1, method=ct_patterns.METHOD,
        metadata={'paper_scope': ct_patterns.METADATA['paper_scope'],
                  'attention': 'Distance kernel, not learned attention; self edges included; tau=0.25',
                  'runtime_scope': 'This lab step excludes pre-existing winprob model fitting and other export steps.'},
        model_accuracy=wpr['metrics'] if wpr else (json.loads(metrics.read_text()) if metrics.exists() else None),
        attention=attention, shap=shap_rounds(t, wpr, selected), control=control_example(t, selected), references=REFERENCES)
    elapsed = time.monotonic()-start
    _write(out_dir/'ai_lab.json', obj)
    print(f"AI lab: {len(attention)} patterns, {len(obj['shap']['rounds'])} explained rounds, {elapsed:.1f}s")
    return obj
