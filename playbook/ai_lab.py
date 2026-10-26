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
from playbook.config import load_map, load_site
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


def background_rows(candidates: pl.DataFrame, size: int, rng: np.random.Generator) -> list[int]:
    """Row indices of one random state from each of up to `size` distinct training matches."""
    groups = candidates.with_row_index('_row').group_by('demo_id').agg(pl.col('_row').sort()).sort('demo_id')
    rows = groups['_row'].to_list()
    picked = sorted(rng.choice(len(rows), min(size, len(rows)), replace=False).tolist())
    return sorted(int(rows[j][rng.integers(len(rows[j]))]) for j in picked)


def _key(demo: str, rnd: int) -> pl.Expr:
    return (pl.col('demo_id') == demo) & (pl.col('round_num') == rnd)


def showcase_teams() -> list[str]:
    """Showcase teams from config/site.toml, Falcons first (the control example uses it)."""
    teams = list(load_site().get('showcase', ['Falcons']))
    return sorted(teams, key=lambda team: team != 'Falcons')


def choose_rounds(t: dict, teams: list[str] | None = None) -> list[tuple[str, dict]]:
    """One planted gun round (no pistol round) per showcase team, on Mirage when possible, from the
    team's most recent match."""
    if 'rounds' not in t or not {'ct_team', 't_team', 'dur_s'} <= set(t['rounds'].columns):
        return []
    matches = dict(t['matches'].select('demo_id', 'map').iter_rows())
    dates = dict(t['matches'].select('demo_id', 'date').iter_rows()) if 'date' in t['matches'].columns else {}
    planted = set(round_plants(t).select('demo_id', 'round_num').iter_rows())
    pistol = set()
    if 'economy' in t and 'buy_type' in t['economy'].columns:
        pistol = set(t['economy'].filter(pl.col('buy_type') == 'pistol').select('demo_id', 'round_num').iter_rows())
    result = []
    for team in teams or showcase_teams():
        rows = t['rounds'].filter((pl.col('ct_team') == team) | (pl.col('t_team') == team)).sort('demo_id', 'round_num').to_dicts()
        rows = [r for r in rows if (r['demo_id'], r['round_num']) in planted and r['dur_s'] >= 25
                and (r['demo_id'], r['round_num']) not in pistol]
        rows.sort(key=lambda r: (matches[r['demo_id']] != 'de_mirage', -_day(dates.get(r['demo_id'])),
                                 r['demo_id'], r['round_num']))
        if rows:
            result.append((team, dict(rows[0], map=matches[rows[0]['demo_id']])))
    return result


def _day(value) -> int:
    """Sortable day number of an ISO date (0 when unknown)."""
    try:
        return int(str(value).replace('-', '')[:8])
    except (TypeError, ValueError):
        return 0


def _observed_control(pos: pl.DataFrame, grid: np.ndarray) -> dict[int, float | None]:
    return {int(s): replay.t_control(p.filter(pl.col('side') == 'T').select('x', 'y').to_numpy(),
                                   p.filter(pl.col('side') == 'CT').select('x', 'y').to_numpy(), grid)
            for (s,), p in pos.filter(pl.col('alive')).group_by('t_s')}


@threadpool_limits.wrap(limits=1)
def shap_rounds(t: dict, wpr: dict | None, selected: list[tuple[str, dict]]) -> dict:
    out = dict(method='exact_interventional_group_shapley_64_coalitions', groups=list(GROUPS),
        background_size=BACKGROUND_SIZE, active_groups=[],
        inactive_groups_note_zh='当前模型只使用 4 组特征：人数差、血量与装备、区域占位、C4 与倒计时',
        limitations=[
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
        background = candidates[background_rows(candidates, BACKGROUND_SIZE, np.random.default_rng(42))]
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
    out['active_groups'] = [group for group in GROUPS if any(
        state['shap_values'][group] != 0.
        for row in out['rounds'] for state in row['states'])]
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


def ensure_replays(sub: dict, mm, mdir: Path, required: set[tuple[str, int]],
                   wpr: dict | None) -> set[tuple[str, int]]:
    """Extend the freshly exported replay set with every required lab example.

    Called after the regular map exporter so its index cannot overwrite these
    additions. Missing optional scatter samples remain explicitly unavailable.
    """
    replay_dir = mdir/'replay'
    index_path = replay_dir/'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {}
    available = {(demo, int(rnd)) for demo, rounds in index.items() for rnd in rounds
                 if (replay_dir/demo/f'{rnd}.json').exists()}
    # Validate required examples even if an older index already lists them.
    for demo, rnd in required & available:
        data = json.loads((replay_dir/demo/f'{rnd}.json').read_text())
        if not data.get('frames') or not any(any(p is not None for p in frame) for frame in data['frames']):
            available.remove((demo, rnd))
    missing = required-available
    if missing:
        wp = replay.wp_by_round(wpr['states'], wpr['oof'], missing) if wpr else {}
        grid, place_index = replay.map_context(sub['positions'])  # cache hit after the map export
        tables = replay.RoundTables(sub, missing)
        for demo, rnd in sorted(missing):
            data = replay.build_round(sub, mm, demo, rnd, wp.get((demo, rnd)), grid, place_index, tables)
            if not data or not data['frames'] or not any(
                    any(p is not None for p in frame) for frame in data['frames']):
                raise ValueError(f'Lab example has no replay frames: {mm.name}/{demo}/{rnd}')
            _write(replay_dir/demo/f'{rnd}.json', data)
            available.add((demo, rnd))
    fresh_index = {}
    for demo, rnd in sorted(available):
        fresh_index.setdefault(demo, []).append(rnd)
    _write(index_path, fresh_index)
    return available


def export(t: dict, out_dir: Path, wpr: dict | None) -> dict:
    start = time.monotonic()
    attention = []
    selected = choose_rounds(t)
    for map_name in sorted(t['matches']['map'].unique().to_list()):
        ids = t['matches'].filter(pl.col('map') == map_name)['demo_id'].to_list()
        sub = {k: v.filter(pl.col('demo_id').is_in(ids)) for k, v in t.items() if 'demo_id' in v.columns}
        patterns, edges = ct_patterns.build(sub, load_map(map_name))
        required = {(c['medoid']['demo_id'], c['medoid']['round_num']) for c in patterns['clusters']}
        required.update((r['demo_id'], int(r['round_num'])) for _, r in selected if r['map'] == map_name)
        available = ensure_replays(sub, load_map(map_name), out_dir/map_name, required, wpr)
        for cluster in patterns['clusters']:
            cluster['medoid']['replay_available'] = True
        for point in patterns['embedding']['points']:
            point['replay_available'] = (point['demo_id'], point['round_num']) in available
        for edge in edges:
            edge['round']['replay_available'] = True
        _write(out_dir/map_name/'ct_patterns.json', patterns)
        attention.extend(edges)
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
