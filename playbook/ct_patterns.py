"""Data-derived CT formations, lightweight TAGNet-inspired encoder.

Method inspired by Zhang et al., TAGNet, DOI 10.1109/TG.2026.3745970.
No upstream code is copied. This is not a trained GAT/GRU reproduction.
"""
from __future__ import annotations

from collections import Counter
import json
import re
import numpy as np
import polars as pl
from scipy.stats import chi2_contingency
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from playbook.config import CONFIG_DIR, MapMeta

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
    'pistol_exclusion': 'MR12 regulation rounds 1 and 13 only; overtime half starts are retained.',
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
    n = int(a.sum())
    if min(a.shape, default=0) < 2:
        return dict(statistic=0., dof=0, p=1., p_display='p = 1', n=n, cramers_v=0., economy_types=types,
                    observed=a.tolist(), min_expected=None, caveat='Insufficient nonempty categories')
    stat, p, dof, expected = chi2_contingency(a, correction=False)
    return dict(statistic=float(stat), dof=int(dof), p=float(p),
                p_display='p < 0.0001' if p < 1e-4 else f'p = {p:.3g}',
                n=n, cramers_v=float(np.sqrt(stat/(n*min(a.shape[0]-1, a.shape[1]-1)))), economy_types=types,
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
    pistols = tr.filter(pl.col('round_num').is_in([1, 13])).height
    counts = dict(total=tr.height, excluded_pistol_rounds=pistols, eligible_at_10=0,
                  dropped_at_10=0, dropped_incomplete=0, included=0)
    tr = tr.filter(~pl.col('round_num').is_in([1, 13]))
    if positions.is_empty() or tr.is_empty():
        counts['dropped_at_10'] = tr.height
        return [], np.empty((0, 103)), counts
    positions = positions.filter(~pl.col('round_num').is_in([1, 13]))
    ct_spawn, t_spawn = _spawn(positions, 'CT'), _spawn(positions, 'T')
    pos = positions.filter((pl.col('side') == 'CT') & pl.col('t_s').is_in(sorted(set(TIMES) | set(range(15, 21)))))
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
        callouts = Counter()
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
        callouts.update(place for place in g.filter(
            pl.col('t_s').is_between(15, 20) & pl.col('steamid').is_in(sids))['place'].to_list()
            if place in mm.callout_region)
        lanes15 = [lane if lane in REGIONS else 'OTHER' for lane in lanes15]
        order = sorted(range(5), key=lambda i: (REGIONS.index(lanes15[i]), depths[i], sids[i]))
        xyz = np.stack(snapshots)[:, order]
        radar = np.empty_like(xyz)
        radar[:, :, 0] = (xyz[:, :, 0]-mm.radar['pos_x'])/mm.radar['scale']
        radar[:, :, 1] = (mm.radar['pos_y']-xyz[:, :, 1])/mm.radar['scale']
        radar[:, :, 2] = (xyz[:, :, 2] < mm.radar.get('lower_level_max_z', -np.inf)).astype(int)
        after_loss = previous.get((row['demo_id'], row['round_num'], row['team'])) is False
        row.update(xyz=xyz, radar=radar, shares=np.array([lanes15.count(l)/5 for l in REGIONS]),
                   depth=float(np.mean(depths)), after_loss=after_loss, callouts=callouts)
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


# Cache has no route_names entry; these callout names follow the reviewed Cache
# spot vocabulary (config/spots/de_cache.toml) and the existing callout translations.
CACHE_CALLOUT_ZH = {
    'TSpawn': '匪家', 'TYard': '匪家外院', 'TTruck': '匪家卡车',
    'OutsideA': 'A区外场', 'AMain': 'A区主通道', 'AHalls': 'A区大厅',
    'AStairs': 'A区楼梯', 'LongA': 'A区长廊', 'Lockers': '更衣室',
    'BombsiteA': 'A包点', 'Truck': '警家卡车', 'ForkLift': '叉车',
    'Squeaky': 'A区铁门', 'Corner': 'A区底角', 'Quad': '四箱',
    'Catwalk': 'A区猫道', 'ElectricalBox': '电箱', 'Toxic': 'A区毒箱',
    'Ladder': 'A区梯子', 'ABoost': 'A区双架', 'Mid': '中路',
    'Middle': '中路高台', 'Garage': '车库', 'Highway': '公路',
    'Vents': '通风管', 'Boost': '中路双架', 'Sandbags': '沙袋',
    'Cubby': '中路凹槽', 'MidRoof': '中路屋顶', 'Red': '红箱',
    'BMain': 'B区主通道', 'BHalls': 'B区大厅', 'SunRoom': '日光房',
    'OutsideB': 'B区外场', 'Useless': '无用房', 'BombsiteB': 'B包点',
    'Checkers': '棋盘房', 'TreeRoom': '树房', 'Headshot': '爆头位',
    'Heaven': 'B区天堂', 'Rafters': 'B区横梁', 'BackHall': 'B区后廊',
    'CTSpawn': '警家', 'CTLane': '警家通道', 'BusStop': '公交站',
    'Connector': '警家连接', 'Bear': '熊位',
}


# Existing Overpass callout vocabulary; this historical map has no route config.
OVERPASS_CALLOUT_ZH = {'UpperPark': '上公园',
 'Restroom': '厕所',
 'BombsiteA': 'A 包点',
 'Playground': '游乐场',
 'Lobby': '大厅',
 'StorageRoom': '储藏室',
 'Fountain': '喷泉',
 'LowerPark': '下公园',
 'BackofA': 'A 后',
 'UnderA': 'A 下',
 'SnipersNest': '狙位',
 'Connector': '连接',
 'Walkway': '走道',
 'Stairs': '楼梯',
 'Tunnels': '隧道',
 'Water': '水域',
 'Bridge': '桥',
 'TSpawn': '匪家',
 'Construction': '工地',
 'Pipe': '管道',
 'BombsiteB': 'B 包点',
 'TStairs': 'T 楼梯',
 'Alley': '小巷',
 'Canal': '水渠',
 'SideAlley': '侧巷'}


def callout_names(mm: MapMeta) -> dict[str, str]:
    """Reuse configured callout translations, removing route-only wording."""
    path = CONFIG_DIR / 'route_names.json'
    routes = json.loads(path.read_text()).get(mm.name, {}) if path.exists() else {}
    names = {place: re.sub(r'(?:主攻|夹击|进攻|出发)?线$', '', name)
             for place, name in routes.items() if place in mm.callout_region}
    if mm.name == 'de_cache':
        names.update(CACHE_CALLOUT_ZH)
    elif mm.name == 'de_overpass':
        names.update(OVERPASS_CALLOUT_ZH)
    return names


def _label_callouts(shares: np.ndarray, callouts: list[Counter],
                    names_zh: dict[str, str]) -> list[list[str]]:
    """Select at most two distinctive callouts per five-player count prefix.

    Lift is own observation share minus the unweighted mean of sibling shares.
    Shared top-two callouts are background noise; mere presence in every large
    cluster is not enough to call a place common. Each translated callout belongs
    only to its strongest positive-lift sibling, keeping label sets disjoint.
    Singleton prefixes use observation share (the peer baseline is zero).
    """
    groups = {}
    for i, share in enumerate(shares):
        groups.setdefault(tuple(player_counts(share)), []).append(i)
    selected = [[] for _ in shares]
    for siblings in groups.values():
        frequency = {i: {p: n/max(1, callouts[i].total()) for p, n in callouts[i].items() if n > 0}
                     for i in siblings}
        top = {i: set(sorted(frequency[i], key=lambda p: (-frequency[i][p], p))[:2])
               for i in siblings}
        common = set.intersection(*(top[i] for i in siblings)) if len(siblings) > 1 else set()
        # Compare display names too: aliases must not appear in sibling labels.
        common_zh = {names_zh.get(p, p) for p in common}
        owners = {}
        for i in siblings:
            peers = [j for j in siblings if j != i]
            for place, own in frequency[i].items():
                zh = names_zh.get(place, place)
                if zh in common_zh:
                    continue
                lift = own - sum(frequency[j].get(place, 0.) for j in peers)/max(1, len(peers))
                if lift <= 1e-12:
                    continue
                candidate = (lift, own, -i, place)
                if zh not in owners or candidate > owners[zh][0]:
                    owners[zh] = (candidate, i, place)
        for i in siblings:
            candidates = [(candidate, place) for candidate, owner, place in owners.values() if owner == i]
            selected[i] = [place for _, place in sorted(candidates, key=lambda item: (
                -item[0][0], -item[0][1], item[1]))[:2]]
    return selected


def _labels(shares: np.ndarray, depths: np.ndarray, callouts: list[Counter],
            names_zh: dict[str, str]) -> list[tuple[str, str]]:
    """Five-player prefix + up to two sibling-exclusive lift callouts + depth."""
    low, high = np.quantile(depths, [1/3, 2/3])
    selected = _label_callouts(shares, callouts, names_zh)
    labels = []
    for s, depth, places in zip(shares, depths, selected):
        counts = player_counts(s)
        prefix_zh = '·'.join(f'{r}{n}' for r, n in zip(('A', '中', 'B', '警', '外围'), counts) if n)
        prefix_en = '-'.join(f'{r}{n}' for r, n in zip(('A', 'M', 'B', 'CT', 'O'), counts) if n)
        word = ('前顶', 'forward') if depth > high else ('保守', 'conservative') if depth < low else ('', '')
        zh = '/'.join(names_zh.get(p, p) for p in places) or '开局'
        en = '/'.join(places) or 'opening'
        labels.append((f'{prefix_zh}（{zh}{" " if word[0] else ""}{word[0]}）',
                       f'{prefix_en} ({en}{" " if word[1] else ""}{word[1]})'))
    # No invented geographic distinctions when identical summaries have no lift.
    return [(zh[:-1]+f' #{i+1}）', en[:-1]+f' #{i+1})') if any(
        i != j and (zh == other_zh or en == other_en)
        for j, (other_zh, other_en) in enumerate(labels)) else (zh, en)
        for i, (zh, en) in enumerate(labels)]


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
    out = dict(schema_version=1, map=mm.name, method=METHOD, metadata={**METADATA, 'excluded_pistol_rounds': counts['excluded_pistol_rounds']}, counts=counts,
               clusters=[], chi_square=chi_square(np.empty((0, 0), int), []), fingerprints=[],
               embedding={'method': 'pca_2d', 'points': []})
    counts['dropped_outlier'] = 0
    if not len(rows):
        out['metadata'].update(k=0, requested_k=6, k_stayed_6=False, clustering_note='No eligible rounds')
        return out, []
    keep, scaled, reduced, labels, clustering = _cluster(x)
    out['metadata'].update(clustering)
    out['metadata']['labels'] = '15s mean region shares apportioned to five players by largest remainders; up to two callouts ranked by positive share lift over the mean of other same-prefix clusters; shared top-two callouts omitted, each translated callout owned by its highest-lift sibling; singleton prefixes use frequency; cluster mean depth thirds (forward/conservative); identical summaries receive neutral sample numbers. IDs retain ascending mean A-share order.'
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
    callouts = [sum((rows[j]['callouts'] for j in np.flatnonzero(labels == c)), Counter()) for c in order]
    translations = callout_names(mm)
    names = _labels(means, mean_depths, callouts, translations)
    label_places = _label_callouts(means, callouts, translations)
    ids = {c: f'C{i}' for i, c in enumerate(order)}
    contexts = {b: np.array([r['buy_type'] == b for r in rows]) for b in ('full', 'force', 'eco')}
    contexts.update(trailing=np.array([r['score_for'] < r['score_against'] for r in rows]),
                    leading=np.array([r['score_for'] > r['score_against'] for r in rows]),
                    after_loss=np.array([r['after_loss'] for r in rows]))
    attention = []
    eco_types = ['eco', 'force', 'full']
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
            label_callouts_15_20s=label_places[i],
            callouts_15_20s=[dict(place=p, label_zh=callout_names(mm).get(p, p), n=int(count),
                                  share=count/max(1, callouts[i].total()))
                              for p, count in sorted(callouts[i].items(), key=lambda item: (-item[1], item[0]))],
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
