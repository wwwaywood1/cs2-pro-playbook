"""Data-derived CT formations, lightweight TAGNet-inspired encoder.

Method inspired by Zhang et al., TAGNet, DOI 10.1109/TG.2026.3745970.
No upstream code is copied. This is not a trained GAT/GRU reproduction.
"""
from __future__ import annotations

from collections import Counter
import numpy as np
import polars as pl
from scipy.stats import chi2_contingency
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from playbook.config import MapMeta

TIMES = (10, 12, 15, 18, 20)
REGIONS = ('A', 'MID', 'B', 'CT_SPAWN', 'OTHER')
DISTANCE_SCALE = 4215.87
METHOD = 'lightweight_standardised_pca_kmeans'
METADATA = {
    'paper_scope': 'TAGNet was validated on Dust2 only (697 rounds); this project applies a lightweight method to all parsed maps. Results below are computed from our demos.',
    'encoder': '5 snapshots × (4 lane shares + 10 sorted XYZ pair distances /4215.87 + 5 sorted CT-to-T depth values) + 8 context values; standardise, PCA <=64, KMeans K=6, n_init=20, random_state=42',
    'depth': 'distance from observed CT spawn centroid / (distance to CT spawn + distance to T spawn); centroids from alive spawn frames t=0..2 per map',
    'unknown_lanes': 'OTHER/T_SPAWN remain in denominator, omitted from four encoder shares; reported as OTHER in summaries',
    'snapshots': list(TIMES), 'later_deaths': 'Use recorded positions of the original five CT members, including dead members after 10s; drop incomplete/non-finite rounds.',
    'trajectory_slots': '15s lane A/MID/B/CT_SPAWN/OTHER, depth, steamid; fixed member identity across snapshots',
    'torch_available': False,
}


def wilson(won: int, n: int) -> list[float]:
    if not n:
        return [0., 1.]
    z = 1.959963984540054
    p, q = won / n, z*z/n
    mid = (p + q/2)/(1+q)
    half = z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+q)
    return [float(mid-half), float(mid+half)]


def chi_square(table: np.ndarray, economy_types: list[str]) -> dict:
    a = np.asarray(table, dtype=int)
    a = a[a.sum(axis=1) > 0]
    keep = a.sum(axis=0) > 0
    a = a[:, keep]
    types = [e for e, k in zip(economy_types, keep) if k]
    if min(a.shape, default=0) < 2:
        return dict(statistic=0., dof=0, p=1., economy_types=types,
                    observed=a.tolist(), min_expected=None, caveat='Insufficient nonempty categories')
    stat, p, dof, expected = chi2_contingency(a, correction=False)
    return dict(statistic=float(stat), dof=int(dof), p=float(p), economy_types=types,
                observed=a.tolist(), min_expected=float(expected.min()),
                caveat='Expected cells below 5; asymptotic p-value may be unreliable' if expected.min() < 5 else None)


def _spawn(pos: pl.DataFrame, side: str) -> np.ndarray:
    p = pos.filter((pl.col('side') == side) & pl.col('alive') & pl.col('t_s').is_between(0, 2))
    if p.is_empty():
        raise ValueError(f'No {side} spawn observations')
    return np.nanmedian(p.select('x', 'y', 'z').to_numpy(), axis=0)


def snapshot_features(xyz: np.ndarray, lanes: list[str], ct_spawn: np.ndarray,
                      t_spawn: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """19 permutation-invariant features and per-member normalised push depth."""
    dc = np.linalg.norm(xyz-ct_spawn, axis=1)
    dt = np.linalg.norm(xyz-t_spawn, axis=1)
    depth = dc/np.maximum(dc+dt, 1.)
    distances = np.linalg.norm(xyz[:, None]-xyz[None, :], axis=2)[np.triu_indices(5, 1)]
    f = [lanes.count(lane)/5 for lane in REGIONS[:4]]
    return np.r_[f, np.sort(distances)/DISTANCE_SCALE, np.sort(depth)], depth


def round_ref(row: dict) -> dict:
    return {'demo_id': row['demo_id'], 'round_num': int(row['round_num']), 'team': row['team'],
            'economy': row['buy_type'], 'score': {'ct': int(row['score_for']), 't': int(row['score_against'])}}


def extract(sub: dict, mm: MapMeta) -> tuple[list[dict], np.ndarray, dict]:
    tr = sub['team_rounds'].filter(pl.col('side') == 'CT').sort('demo_id', 'round_num')
    positions = sub['positions']
    counts = dict(total=tr.height, eligible_at_10=0, dropped_at_10=0, dropped_incomplete=0, included=0)
    if positions.is_empty() or tr.is_empty():
        counts['dropped_at_10'] = counts['total']
        return [], np.empty((0, 103)), counts
    ct_spawn, t_spawn = _spawn(positions, 'CT'), _spawn(positions, 'T')
    pos = positions.filter((pl.col('side') == 'CT') & pl.col('t_s').is_in(TIMES))
    grouped = {key: g for key, g in pos.group_by('demo_id', 'round_num', maintain_order=True)}
    # Previous result follows this team, not a fixed side, including half transitions.
    previous = {}
    for (_, _), g in sub['team_rounds'].sort('round_num').group_by('demo_id', 'team'):
        last = None
        for row in g.sort('round_num').iter_rows(named=True):
            previous[(row['demo_id'], row['round_num'], row['team'])] = last
            last = bool(row['won'])
    rows, features = [], []
    for row in tr.iter_rows(named=True):
        g = grouped.get((row['demo_id'], row['round_num']))
        at10 = g.filter((pl.col('t_s') == 10) & pl.col('alive')) if g is not None else pl.DataFrame()
        if at10.height != 5 or at10['steamid'].n_unique() != 5:
            counts['dropped_at_10'] += 1
            continue
        counts['eligible_at_10'] += 1
        if row.get('dur_s', 20) < 20:
            counts['dropped_incomplete'] += 1
            continue
        sids = sorted(at10['steamid'].to_list())
        snapshots, fs, depths, lanes15 = [], [], [], []
        for second in TIMES:
            p = g.filter((pl.col('t_s') == second) & pl.col('steamid').is_in(sids)).sort('steamid')
            if p.height != 5 or p['steamid'].to_list() != sids:
                break
            xyz = p.select('x', 'y', 'z').to_numpy().astype(float)
            if not np.isfinite(xyz).all():
                break
            lanes = [mm.lane(place) for place in p['place'].to_list()]
            f, depth = snapshot_features(xyz, lanes, ct_spawn, t_spawn)
            fs.extend(f)
            snapshots.append(xyz)
            if second == 15:
                lanes15, depths = lanes, depth
        if len(snapshots) != 5:
            counts['dropped_incomplete'] += 1
            continue
        lanes15 = [lane if lane in REGIONS else 'OTHER' for lane in lanes15]
        order = sorted(range(5), key=lambda i: (REGIONS.index(lanes15[i]), depths[i], sids[i]))
        xyz = np.stack(snapshots)[:, order]
        radar = np.empty_like(xyz)
        radar[:, :, 0] = (xyz[:, :, 0]-mm.radar['pos_x'])/mm.radar['scale']
        radar[:, :, 1] = (mm.radar['pos_y']-xyz[:, :, 1])/mm.radar['scale']
        radar[:, :, 2] = (xyz[:, :, 2] < mm.radar.get('lower_level_max_z', -np.inf)).astype(int)
        after_loss = previous.get((row['demo_id'], row['round_num'], row['team'])) is False
        row.update(xyz=xyz, radar=radar, shares=np.array([lanes15.count(l)/5 for l in REGIONS]),
                   depth=float(np.mean(depths)), after_loss=after_loss)
        context = [row['equipment_value']/25000, row['opp_equipment_value']/25000,
                   (row['score_for']-row['score_against'])/12, float(after_loss),
                   *[float(row['buy_type'] == b) for b in ('full', 'force', 'eco', 'pistol')]]
        rows.append(row)
        features.append(np.r_[fs, context])
    counts['included'] = len(rows)
    return rows, np.array(features).reshape(-1, 103), counts


def _labels(shares: np.ndarray, depths: np.ndarray) -> list[tuple[str, str]]:
    result = []
    for s, d in zip(shares, depths):
        if d >= np.quantile(depths, .8) and d > .55:
            label = ('激进前压', 'Forward pressure')
        elif s[0] >= .48:
            label = ('A 区重防', 'A-heavy defence')
        elif s[2] >= .48:
            label = ('B 区重防', 'B-heavy defence')
        elif s[1] >= max(s[0], s[2]):
            label = ('中路联防', 'Mid-oriented defence')
        elif s[2]+s[1] > .65:
            label = ('B 区+中路联防', 'B and mid defence')
        else:
            label = ('双点均衡', 'Balanced sites')
        result.append(label)
    counts = Counter(result)
    original_labels = result.copy()
    # Append actual strongest separation from other colliding centroids, not cluster index.
    for i, label in enumerate(result.copy()):
        if counts[label] <= 1:
            continue
        vals = np.r_[shares[i], depths[i]]
        others = np.array([np.r_[shares[j], depths[j]] for j in range(len(shares)) if j != i and original_labels[j] == label])
        k = int(np.argmax(np.abs(vals-others.mean(axis=0))))
        zh = (*REGIONS, '前压深度')[k]
        en = (*REGIONS, 'depth')[k]
        result[i] = (f'{label[0]} · {zh} {vals[k]:.1%}', f'{label[1]} · {en} {vals[k]:.1%}')
    # In the rare event of identical displayed feature values, expose full measured profile.
    seen = set()
    for i, label in enumerate(result):
        if label in seen:
            suffix = '/'.join(f'{x:.4f}' for x in [*shares[i], depths[i]])
            result[i] = (f'{label[0]} [{suffix}]', f'{label[1]} [{suffix}]')
        seen.add(result[i])
    return result


@threadpool_limits.wrap(limits=1)
def build(sub: dict, mm: MapMeta) -> tuple[dict, list[dict]]:
    rows, x, counts = extract(sub, mm)
    out = dict(schema_version=1, map=mm.name, method=METHOD, metadata=METADATA.copy(), counts=counts,
               clusters=[], chi_square=chi_square(np.empty((0, 0), int), []), fingerprints=[],
               embedding={'method': 'pca_2d', 'points': []})
    if not len(rows):
        return out, []
    scaled = StandardScaler().fit_transform(x)
    reduced = PCA(n_components=min(64, *scaled.shape), svd_solver='full').fit_transform(scaled)
    k = min(6, len(np.unique(x, axis=0)))
    labels = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(reduced)
    shares = np.stack([r['shares'] for r in rows])
    depths = np.array([r['depth'] for r in rows])
    # Sorting by the spatial centroid resolves equal A shares deterministically.
    order = sorted(range(k), key=lambda c: tuple(shares[labels == c].mean(axis=0)) + tuple(x[labels == c].mean(axis=0)))
    means = np.array([shares[labels == c].mean(axis=0) for c in order])
    mean_depths = np.array([depths[labels == c].mean() for c in order])
    names = _labels(means, mean_depths)
    ids = {c: f'C{i}' for i, c in enumerate(order)}
    contexts = {b: np.array([r['buy_type'] == b for r in rows]) for b in ('full', 'force', 'eco', 'pistol')}
    contexts.update(trailing=np.array([r['score_for'] < r['score_against'] for r in rows]),
                    leading=np.array([r['score_for'] > r['score_against'] for r in rows]),
                    after_loss=np.array([r['after_loss'] for r in rows]))
    attention = []
    eco_types = sorted({r['buy_type'] for r in rows})
    contingency = []
    for i, c in enumerate(order):
        members = np.flatnonzero(labels == c)
        n = len(members)
        medoid_i = members[np.argmin(np.linalg.norm(reduced[members]-reduced[members].mean(axis=0), axis=1))]
        medoid = rows[medoid_i]
        trajectory = np.stack([rows[j]['radar'] for j in members]).mean(axis=0)
        trajectory[:, :, 2] = np.rint(trajectory[:, :, 2])
        won = sum(bool(rows[j]['won']) for j in members)
        prefs = {name: {'n': int(mask[members].sum()), 'share': float(mask[members].mean()),
                        'map_share': float(mask.mean()), 'difference_pp': float(100*(mask[members].mean()-mask.mean()))}
                 for name, mask in contexts.items()}
        out['clusters'].append(dict(id=ids[c], label_zh=names[i][0], label_en=names[i][1], n=n,
            share=n/len(rows), ct_win_rate=won/n, ct_win_ci95=wilson(won, n),
            region_shares_15s=dict(zip(REGIONS, means[i].tolist())), push_depth=float(mean_depths[i]),
            trajectories=[{'t_s': s, 'positions': trajectory[j].round(3).tolist()} for j, s in enumerate(TIMES)],
            medoid=round_ref(medoid), context_preferences=prefs))
        contingency.append([sum(rows[j]['buy_type'] == b for j in members) for b in eco_types])
        snaps = []
        for j, s in enumerate(TIMES):
            xyz = medoid['xyz'][j]
            distances = np.linalg.norm(xyz[:, None]-xyz[None, :], axis=2)
            logits = np.exp(-distances/DISTANCE_SCALE/.25)
            weights = np.exp(logits-logits.max(axis=1, keepdims=True))
            weights /= weights.sum(axis=1, keepdims=True)
            snaps.append(dict(t_s=s, positions=medoid['radar'][j].round(3).tolist(), alpha=weights.tolist()))
        attention.append(dict(map=mm.name, cluster_id=ids[c], round=round_ref(medoid),
                              method='distance_kernel', tau=.25, snapshots=snaps))
    out['chi_square'] = chi_square(np.array(contingency), eco_types)
    for team in sorted({r['team'] for r in rows}):
        mask = np.array([r['team'] == team for r in rows])
        n = int(mask.sum())
        if n < 30:
            continue
        out['fingerprints'].append(dict(team=team, n=n, usage=[dict(cluster_id=ids[c],
            share=float((labels[mask] == c).mean()), pro_share=float((labels == c).mean()),
            difference_pp=float(100*((labels[mask] == c).mean()-(labels == c).mean()))) for c in order]))
    embedding = np.pad(reduced[:, :2], ((0, 0), (0, max(0, 2-reduced.shape[1]))))
    out['embedding']['points'] = [dict(**round_ref(r), cluster_id=ids[labels[i]],
                                     x=float(embedding[i, 0]), y=float(embedding[i, 1])) for i, r in enumerate(rows)]
    out['metadata'].update(n_components=reduced.shape[1], k=k, feature_count=x.shape[1],
                           explained_variance_ratio=float(np.nan_to_num(PCA(n_components=min(2, *scaled.shape)).fit(scaled).explained_variance_ratio_).sum()))
    return out, attention
