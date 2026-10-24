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
    'encoder': '5 snapshots × (4 lane shares + 10 sorted XYZ pair distances /4215.87 + 5 sorted CT-to-T depth values) + 8 context values; standardise, PCA <=64, KMeans K<=6, n_init=20, random_state=42; per-map k and exclusions below',
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


def player_counts(shares: np.ndarray) -> np.ndarray:
    """Hamilton/largest-remainder apportionment, ties in REGIONS order."""
    expected = np.asarray(shares, float)
    expected = expected / expected.sum() * 5
    counts = np.floor(expected).astype(int)
    # Decimal lane shares can produce sub-ULP differences in exact ties.
    order = np.argsort(-np.round(expected-counts, 12), kind='stable')
    counts[order[:5-int(counts.sum())]] += 1
    return counts


def _labels(shares: np.ndarray, depths: np.ndarray) -> list[tuple[str, str]]:
    result = []
    for s in shares:
        counts = player_counts(s)
        zh = '·'.join(f'{r}{n}' for r, n in zip(('A', '中', 'B', '警家', '外围'), counts) if n)
        en = '-'.join(f'{r}{n}' for r, n in zip(('A', 'M', 'B', 'CT', 'O'), counts) if n)
        if counts[0] >= 3:
            style = ('重 A', 'A-heavy')
        elif counts[2] >= 3:
            style = ('重 B', 'B-heavy')
        elif counts[1] >= 3:
            style = ('中路前顶', 'mid pressure')
        elif counts[3] >= 2:
            style = ('回防集结', 'spawn support')
        elif counts[4] >= 2:
            style = ('外围协防', 'outer support')
        else:
            style = ('均衡', 'default')
        result.append((f'{zh} {style[0]}', f'{en} {style[1]}'))
    # Depth is only useful when the same five-player composition collides.
    original = result.copy()
    low, high = np.quantile(depths, [1/3, 2/3])
    for label, n in Counter(original).items():
        if n < 2:
            continue
        group = [i for i, name in enumerate(original) if name == label]
        words = [('前压', 'forward') if depths[i] > high else ('回收', 'deep') if depths[i] < low else None for i in group]
        if len(set(words)) > 1:
            for i, word in zip(group, words):
                if word:
                    result[i] = (f'{label[0]} · {word[0]}', f'{label[1]} · {word[1]}')
    # Compare remaining collisions in measured regional occupancy and depth.
    # Rank words make even several same-direction profiles distinct without %s.
    original = result.copy()
    profiles = np.column_stack((shares, depths))
    regions = ('A 侧', '中路', 'B 侧', '警家', '外围', '站位')
    english = ('A', 'mid', 'B', 'spawn', 'outer', 'position')
    ranks_zh = ('最少', '偏少', '较少', '较多', '偏多', '最多')
    ranks_en = ('lowest', 'low', 'lower', 'higher', 'high', 'highest')
    for label, n in Counter(original).items():
        if n < 2:
            continue
        group = [i for i, name in enumerate(original) if name == label]
        # Most separating measured feature; stable feature order breaks ties.
        feature_order = np.argsort(-np.ptp(profiles[group], axis=0), kind='stable')
        pending = [group]
        for feature in feature_order:
            next_pending = []
            for peers in pending:
                values = sorted(set(profiles[peers, feature]))
                if len(values) == 1:
                    next_pending.append(peers)
                    continue
                for rank, value in enumerate(values):
                    subset = [i for i in peers if profiles[i, feature] == value]
                    word_rank = round(rank * 5 / (len(values)-1))
                    for i in subset:
                        depth_words = ('站位最后', '站位偏后', '站位较后', '站位较前', '站位偏前', '站位最前')
                        zh = f'{regions[feature]}{ranks_zh[word_rank]}' if feature < 5 else depth_words[word_rank]
                        en = f'{english[feature]} {ranks_en[word_rank]}'
                        result[i] = (f'{result[i][0]} · {zh}', f'{result[i][1]} · {en}')
                    if len(subset) > 1:
                        next_pending.append(subset)
            pending = next_pending
            if not pending:
                break
        # Identical summaries cannot support a claimed tactical distinction.
        for peers in pending:
            for rank, i in enumerate(peers, 1):
                result[i] = (f'{result[i][0]} · 同构队形{rank}', f'{result[i][1]} · equivalent formation {rank}')
    return result


def _projection(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    scaled = StandardScaler().fit_transform(x)
    reduced = PCA(n_components=min(64, *scaled.shape), svd_solver='full').fit_transform(scaled)
    return scaled, reduced


def _cluster(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
    """Trim a reported .5% tail, then reduce K until all clusters meet the floor.

    Pilot centres exclude the radial tail first: otherwise a singleton outlier
    can acquire its own centre and misleadingly have zero nearest-centre distance.
    Refit scaling and PCA after trimming so outliers do not set the final metric.
    """
    _, pilot = _projection(x)
    radius = np.linalg.norm(pilot-np.median(pilot, axis=0), axis=1)
    central = radius <= np.quantile(radius, .995)
    pilot_k = min(6, len(np.unique(pilot[central], axis=0)))
    model = KMeans(n_clusters=pilot_k, n_init=20, random_state=42).fit(pilot[central])
    distance = model.transform(pilot).min(axis=1)
    cutoff = float(np.quantile(distance, .995))
    keep = distance <= cutoff
    scaled, reduced = _projection(x[keep])
    floor = max(30, int(np.ceil(.03*len(x))))
    initial_k = min(6, len(np.unique(x[keep], axis=0)))
    attempts = []
    for k in range(initial_k, 0, -1):
        labels = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(reduced)
        sizes = np.bincount(labels, minlength=k)
        attempts.append(dict(k=k, sizes=sorted(sizes.tolist())))
        if sizes.min() >= floor or k == 1:
            break
    metadata = dict(k=k, requested_k=6, k_stayed_6=k == 6, min_cluster_size=floor,
        min_cluster_size_met=bool(sizes.min() >= floor), cluster_attempts=attempts,
        clustering_note='K=6 retained' if k == 6 else f'K reduced to {k} to enforce minimum cluster size {floor}',
        outlier_filter=dict(method='robust_pilot_nearest_centre_distance', quantile=.995,
            pilot='Exclude radial distances above the 99.5th percentile from componentwise median before fitting pilot centres; refit standardisation/PCA after nearest-centre trimming.',
            distance_cutoff=cutoff, input_rounds=len(x), dropped=int((~keep).sum())))
    if sizes.min() < floor:
        metadata['clustering_note'] = f'Only {len(labels)} retained rounds; one cluster, minimum {floor} is infeasible'
    return keep, scaled, reduced, labels, metadata


@threadpool_limits.wrap(limits=1)
def build(sub: dict, mm: MapMeta) -> tuple[dict, list[dict]]:
    rows, x, counts = extract(sub, mm)
    out = dict(schema_version=1, map=mm.name, method=METHOD, metadata=METADATA.copy(), counts=counts,
               clusters=[], chi_square=chi_square(np.empty((0, 0), int), []), fingerprints=[],
               embedding={'method': 'pca_2d', 'points': []})
    counts['dropped_outlier'] = 0
    if not len(rows):
        out['metadata'].update(k=0, requested_k=6, k_stayed_6=False, clustering_note='No eligible rounds')
        return out, []
    keep, scaled, reduced, labels, clustering = _cluster(x)
    out['metadata'].update(clustering)
    out['metadata']['labels'] = '15s mean region shares apportioned to five expected players by largest remainders (ties in A/MID/B/CT_SPAWN/OTHER order); depth thirds only distinguish colliding compositions, then strongest observed regional/depth difference in words. IDs retain ascending mean A-share order.'
    out['metadata']['outlier_filter']['excluded_rounds'] = [round_ref(r) for i, r in enumerate(rows) if not keep[i]]
    rows = [r for i, r in enumerate(rows) if keep[i]]
    x = x[keep]
    counts.update(dropped_outlier=int((~keep).sum()), included=len(rows))
    k = clustering['k']
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
            region_shares_15s=dict(zip(REGIONS, means[i].tolist())),
            expected_players_15s=dict(zip(REGIONS, player_counts(means[i]).tolist())), push_depth=float(mean_depths[i]),
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
