"""Numerical and data-contract checks for CT patterns and the research lab."""
from collections import Counter
import json
import re
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from threadpoolctl import threadpool_limits

from playbook import ai_lab as L, ct_patterns as C, winprob as W
from playbook.config import load_map


def synthetic():
    rng = np.random.default_rng(7)
    pos, rounds = [], []
    places = ['BombsiteA', 'Middle', 'BombsiteB', 'CTSpawn', 'TRamp']
    for r in range(1, 73):
        rounds.append(dict(demo_id='fixture', round_num=r, side='CT', team='CT', won=r % 3 != 0,
                           buy_type='pistol' if r in (1, 13) else ('full', 'force', 'eco')[r % 3], equipment_value=18000,
                           opp_equipment_value=20000, score_for=r//3, score_against=r//4))
        rounds.append(dict(rounds[-1], side='T', team='T', won=r % 3 == 0))
        initial = rng.normal(0, 200, (5, 3))
        for second in (0, 1, 2, *C.TIMES):
            for i in range(5):
                for side in ('CT', 'T'):
                    point = initial[i]+[r*15+i*40, second*3+(side == 'T')*900, 0]
                    pos.append(dict(demo_id='fixture', round_num=r, side=side, steamid=i,
                                    t_s=second, alive=not (r == 72 and second == 10 and i == 0 and side == 'CT'),
                                    x=point[0], y=point[1], z=point[2], place=places[(i+r) % 5]))
    return {'positions': pl.DataFrame(pos), 'team_rounds': pl.DataFrame(rounds)}


def test_features_invariant_under_player_permutation():
    xyz = np.array([[i*100, i*i*30, i*20] for i in range(5)])
    lanes = ['A', 'A', 'MID', 'B', 'CT_SPAWN']
    f, depth = C.snapshot_features(xyz, lanes, np.zeros(3), np.full(3, 1000))
    order = [4, 2, 0, 3, 1]
    g, _ = C.snapshot_features(xyz[order], [lanes[i] for i in order], np.zeros(3), np.full(3, 1000))
    assert f.shape == (19,) and depth.shape == (5,)
    np.testing.assert_allclose(f, g)
    np.testing.assert_allclose(f[:4].sum(), 1)


def test_determinism_counts_and_shapes():
    sub = synthetic()
    rows, x, counts = C.extract(sub, load_map('de_mirage'))
    assert x.shape == (69, 103)
    assert counts == dict(total=72, excluded_pistol_rounds=2, eligible_at_10=69, dropped_at_10=1, dropped_incomplete=0, included=69)
    a, edges = C.build(sub, load_map('de_mirage'))
    b, _ = C.build({k: v.reverse() for k, v in sub.items()}, load_map('de_mirage'))
    assert a == b
    k = a['metadata']['k']
    assert 1 <= k <= 2  # 69 rounds cannot support 3 clusters of >=30.
    assert len(a['clusters']) == k
    assert len(set(c['label_zh'] for c in a['clusters'])) == k
    assert all(c['n'] >= 30 for c in a['clusters'])
    shares = [c['region_shares_15s']['A'] for c in a['clusters']]
    assert shares == sorted(shares)
    assert sum(c['n'] for c in a['clusters']) == 69-a['counts']['dropped_outlier']
    assert sum(c['share'] for c in a['clusters']) == pytest.approx(1.)
    for edge in edges:
        for snap in edge['snapshots']:
            assert np.asarray(snap['positions']).shape == (5, 3)
            np.testing.assert_allclose(np.asarray(snap['alpha']).sum(axis=1), 1.)
    json.dumps(a, allow_nan=False)


def assert_player_labels(names):
    assert len({zh for zh, en in names}) == len({en for zh, en in names}) == len(names)
    for zh, en in names:
        assert not any(word in zh for word in ('最多', '最少', '最前', '最后', '均衡', '重 A', '重 B', '警家1'))
        assert sum(map(int, re.findall(r'([1-5])', zh.split('（')[0]))) == 5
        assert sum(map(int, re.findall(r'([1-5])', en.split(' (')[0]))) == 5
        assert '%' not in zh+en


def test_largest_remainder_and_callout_depth_labels():
    np.testing.assert_array_equal(C.player_counts(np.array([.34, .26, .30, .10, 0.])), [2, 1, 2, 0, 0])
    np.testing.assert_array_equal(C.player_counts(np.full(5, .2)), [1, 1, 1, 1, 1])
    shares = np.array([[.4, .4, .2, 0, 0], [.4, .4, .2, 0, 0], [.4, .2, .2, .2, 0]])
    callouts = [Counter(Catwalk=20, SnipersNest=15, BombsiteA=10),
                Counter(Connector=20, TRamp=15, BombsiteB=10),
                Counter(BombsiteA=20, CTSpawn=15)]
    names = C._labels(shares, np.array([.5, .3, .1]), callouts, C.callout_names(load_map('de_mirage')))
    assert_player_labels(names)
    assert names[0][0] == 'A2·中2·B1（B小/VIP 前顶）'
    assert names[1][0] == 'A2·中2·B1（拱门/A1 斜坡）'
    assert names[2][0] == 'A2·中1·B1·警1（A包点/警家 保守）'
    assert names[0][1] == 'A2-M2-B1 (Catwalk/SnipersNest forward)'


def assert_disjoint_callouts(shares, selected, translations):
    for i, places in enumerate(selected):
        assert len(places) <= 2
        for j in range(i):
            if np.array_equal(C.player_counts(shares[i]), C.player_counts(shares[j])):
                assert set(places).isdisjoint(selected[j])
                assert {translations.get(p, p) for p in places}.isdisjoint(
                    translations.get(p, p) for p in selected[j])


def test_same_prefix_labels_use_lift_drop_common_and_have_disjoint_callouts():
    shares = np.array([[.4, .4, .2, 0, 0]]*3 + [[.4, .2, .2, .2, 0]])
    # Unequal sample sizes: rank shares, not raw counts. A and B dominate every
    # sibling; VIP is less frequent than Catwalk in C1 but has higher lift.
    callouts = [Counter(BombsiteA=400, BombsiteB=300, Catwalk=180, Connector=90, SnipersNest=30),
                Counter(BombsiteA=40, BombsiteB=30, Catwalk=14, SnipersNest=12, Connector=4),
                Counter(BombsiteA=40, BombsiteB=30, PalaceInterior=20, Connector=10),
                Counter(BombsiteA=80, CTSpawn=20)]
    translations = C.callout_names(load_map('de_mirage'))
    selected = C._label_callouts(shares, callouts, translations)
    assert selected == [['Catwalk'], ['SnipersNest'], ['PalaceInterior', 'Connector'],
                        ['BombsiteA', 'CTSpawn']]
    assert_disjoint_callouts(shares, selected, translations)
    names = C._labels(shares, np.array([.5, .3, .4, .1]), callouts, translations)
    assert_player_labels(names)
    assert names[0][0] == 'A2·中2·B1（B小 前顶）'
    assert names[1][0] == 'A2·中2·B1（VIP）'
    assert all('A包点' not in zh and 'B包点' not in zh for zh, _ in names[:3])
    assert C._label_callouts(shares[::-1], callouts[::-1], translations)[::-1] == selected
    scaled = [Counter({p: n*10 for p, n in counts.items()}) for counts in callouts]
    assert C._label_callouts(shares, scaled, translations) == selected


def test_lift_ownership_is_disjoint_even_with_aliases_and_multiple_positive_peers():
    shares = np.array([[.4, .4, .2, 0, 0]]*3)
    callouts = [Counter(A=50, B=40, Shared=8, Only0=2),
                Counter(A=50, B=40, Shared=7, Only1=3),
                Counter(A=50, B=40, Alias=1, Only2=9)]
    translations = {'Shared': '同名', 'Alias': '同名'}
    selected = C._label_callouts(shares, callouts, translations)
    assert selected == [['Shared', 'Only0'], ['Only1'], ['Only2']]
    assert_disjoint_callouts(shares, selected, translations)
    # Truly identical summaries have no distinguishing callouts; don't invent any.
    identical = [callouts[0]]*3
    assert C._label_callouts(shares, identical, translations) == [[], [], []]
    assert_player_labels(C._labels(shares, np.ones(3), identical, translations))


def test_pistols_excluded_before_features_and_overtime_retained():
    sub = synthetic()
    rows, x, counts = C.extract(sub, load_map('de_mirage'))
    rounds = {r['round_num'] for r in rows}
    assert not rounds & {1, 13}
    assert {25, 28, 31, 34} <= rounds
    assert counts['excluded_pistol_rounds'] == 2
    # Pistol positions cannot influence the spawn reference or any feature.
    sub['positions'] = sub['positions'].with_columns(
        x=pl.when(pl.col('round_num').is_in([1, 13])).then(1e9).otherwise(pl.col('x')))
    _, changed, _ = C.extract(sub, load_map('de_mirage'))
    np.testing.assert_array_equal(x, changed)
    result, _ = C.build(sub, load_map('de_mirage'))
    assert result['metadata']['excluded_pistol_rounds'] == 2
    assert result['chi_square']['n'] == result['counts']['included']
    assert set(result['chi_square']['economy_types']) == {'eco', 'force', 'full'}
    assert all('pistol' not in c['context_preferences'] for c in result['clusters'])
    assert not {p['round_num'] for p in result['embedding']['points']} & {1, 13}


@threadpool_limits.wrap(limits=1)
def test_singleton_outlier_trimmed_and_cluster_floor_enforced():
    rng = np.random.default_rng(42)
    x = np.vstack([rng.normal(i*8, .1, (100, 4)) for i in range(6)] + [np.full((1, 4), 1e6)])
    keep, _, _, labels, metadata = C._cluster(x)
    assert not keep[-1]  # A singleton must not hide behind its own KMeans centre.
    assert metadata['outlier_filter']['dropped'] == int((~keep).sum())
    assert metadata['k'] == 6 and metadata['k_stayed_6']
    assert np.bincount(labels).min() >= metadata['min_cluster_size']


def test_missing_snapshot_dropped_but_later_death_keeps_original_member():
    sub = synthetic()
    p = sub['positions']
    # Missing one original member at 18s drops a round; death after 10s does not.
    missing = (pl.col('round_num') == 71) & (pl.col('side') == 'CT') & (pl.col('t_s') == 18) & (pl.col('steamid') == 0)
    later_death = (pl.col('round_num') == 70) & (pl.col('side') == 'CT') & (pl.col('t_s') >= 12) & (pl.col('steamid') == 0)
    sub['positions'] = p.filter(~missing).with_columns(alive=pl.when(later_death).then(False).otherwise(pl.col('alive')))
    rows, x, counts = C.extract(sub, load_map('de_mirage'))
    assert counts['included'] == 68 and counts['dropped_incomplete'] == 1
    assert x.shape == (68, 103)
    assert 70 in {r['round_num'] for r in rows} and 71 not in {r['round_num'] for r in rows}
    assert next(r for r in rows if r['round_num'] == 4)['after_loss']


def test_chi_square_known_independence_and_dependence():
    independent = C.chi_square(np.array([[10, 20], [20, 40]]), ['eco', 'full'])
    assert independent['statistic'] == 0 and independent['p'] == 1
    assert independent['n'] == 90 and independent['cramers_v'] == 0
    assert independent['p_display'] == 'p = 1'
    dependent = C.chi_square(np.array([[90, 10], [10, 90]]), ['eco', 'full'])
    assert dependent['dof'] == 1 and dependent['statistic'] == pytest.approx(128)
    assert dependent['p'] < 1e-20
    assert dependent['n'] == 200 and dependent['cramers_v'] == pytest.approx(.8)
    assert dependent['p_display'] == 'p < 0.0001'
    sparse = C.chi_square(np.array([[0, 0, 0], [90, 10, 0], [10, 90, 0]]), ['eco', 'full', 'force'])
    assert sparse['cramers_v'] == dependent['cramers_v']
    assert C.chi_square(np.empty((0, 0), int), [])['n'] == 0
    assert C.chi_square(np.array([[10, 0]]), ['eco', 'full'])['dof'] == 0
    assert C.wilson(0, 10)[1] > 0
    assert C.wilson(10, 10)[0] < 1


def test_shapley_interaction_exactness_and_dummy_groups():
    # v=x0*x1, background 0,0: interaction splits evenly by symmetry.
    x = np.array([[.8, .5, .9], [.4, .6, .1]])
    bg = np.zeros((5, 3))
    base, phi, p = L.exact_shapley(lambda a: a[:, 0]*a[:, 1], x, bg, [[0], [1], [2], [], [], []])
    np.testing.assert_allclose(base, 0)
    np.testing.assert_allclose(phi[:, 0], p/2)
    np.testing.assert_allclose(phi[:, 1], p/2)
    np.testing.assert_allclose(phi[:, 2:], 0)
    np.testing.assert_allclose(base+phi.sum(axis=1), p, atol=1e-6)
    # Unattributed context is held fixed per target; averaging is in probability space.
    base, phi, p = L.exact_shapley(lambda a: a[:, 0]*a[:, 1]+a[:, 2], x, bg, [[0], [1], [], [], [], []])
    np.testing.assert_allclose(base, x[:, 2])
    np.testing.assert_allclose(base+phi.sum(axis=1), p, atol=1e-6)


def test_smoke_changes_computed_ownership_and_penalty_before_minimum():
    grid = np.array([[0., 0.]])
    t = np.array([[-100., 0.]])
    ct = np.array([[60., 0.]])
    owner0, _, c0 = L.ownership(t, ct, grid, np.array([True]))
    owner1, _, c1 = L.ownership(t, ct, grid, np.array([True]), smoke=(np.array([30., 0.]), 10., 450.))
    assert owner0 == ['CT'] and owner1 == ['T'] and c1-c0 == 1
    # A second CT with a longer but unobstructed path becomes nearest.
    d = L.nearest_distances(np.array([[60., 0.], [0., 80.]]), grid, (np.array([30., 0.]), 10., 450.))
    assert d[0] == pytest.approx(80.)


@threadpool_limits.wrap(limits=1)
def test_retained_fold_model_reproduces_calibrated_oof():
    from test_winprob import _tables
    d = W.states(_tables(n_demos=6, rounds=2, secs=24))
    artifacts = []
    p, _ = W.fit_oof(d, model_artifacts=artifacts)
    for artifact in artifacts:
        mask = d['demo_id'].is_in(sorted(artifact['test_demos'])).to_numpy()
        x, names = W.feature_matrix(d.filter(mask), artifact['maps'])
        predicted = artifact['calibrator'].predict(artifact['model'].predict_proba(x)[:, 1])
        np.testing.assert_allclose(predicted, p[mask], atol=1e-10)
        groups = L.model_groups(names)
        used = [j for group in groups for j in group]
        assert len(used) == len(set(used))
        assert set(names[j] for j in set(range(len(names)))-set(used)) == {'score_diff', 'map_de_mirage', 'map_de_nuke'}


def test_lab_examples_exclude_post_round_plants():
    t = {
        'matches': pl.DataFrame([{'demo_id': 'falcons', 'map': 'de_mirage'}]),
        'rounds': pl.DataFrame([dict(demo_id='falcons', round_num=r, t_team='Falcons',
                                     ct_team='Other', dur_s=40.) for r in (1, 2)]),
        'plants': pl.DataFrame([dict(demo_id='falcons', round_num=1, t_s=70., site='A'),
                                dict(demo_id='falcons', round_num=2, t_s=30., site='B')]),
    }
    selected = L.choose_rounds(t)
    assert len(selected) == 1 and selected[0][1]['round_num'] == 2


def test_exported_contract():
    root = Path(__file__).resolve().parents[1]/'data'/'site'
    if not (root/'ai_lab.json').exists():
        pytest.skip('Run python -m playbook export to validate real data')
    lab = json.loads((root/'ai_lab.json').read_text())
    assert lab['schema_version'] == 1 and len(lab['references']) == 6
    assert lab['model_accuracy'] == json.loads((root/'winprob_metrics.json').read_text())
    assert {r['id'] for r in lab['references']} == {r['id'] for r in L.REFERENCES}
    assert len(lab['shap']['rounds']) >= 3
    for r in lab['shap']['rounds']:
        assert r['states']
        assert [s['t_s'] for s in r['states']] == list(range(len(r['states'])))
        for s in r['states']:
            assert set(s['shap_values']) == set(L.GROUPS)
            assert abs(s['base_value']+sum(s['shap_values'].values())-s['t_win_prob']) < 1e-6
    shap = lab['shap']
    assert shap['active_groups'] == [g for g in L.GROUPS if any(
        state['shap_values'][g] != 0 for row in shap['rounds'] for state in row['states'])]
    assert shap['active_groups'] == list(L.GROUPS[:4])
    assert shap['inactive_groups_note_zh'] == '当前模型只使用 4 组特征：人数差、血量与装备、区域占位、C4 与倒计时'
    for edge in lab['attention']:
        assert edge['round']['replay_available'] is True
        assert (root/edge['map']/'replay'/edge['round']['demo_id']/f"{edge['round']['round_num']}.json").exists()
    control = lab['control']
    assert control['map'] == 'de_mirage' and len(control['cells']) == 225
    assert len(control['snapshots']) == 3
    for s in control['snapshots']:
        assert len(s['ownership']) == len(s['delta_distance']) == 225
    for path in sorted(root.glob('*/ct_patterns.json')):
        a = json.loads(path.read_text())
        assert a['schema_version'] == 1
        assert a['counts']['total'] == sum(a['counts'][key] for key in ('included', 'excluded_pistol_rounds', 'dropped_at_10', 'dropped_incomplete', 'dropped_outlier'))
        assert len(a['embedding']['points']) == a['counts']['included']
        k = a['metadata']['k']
        assert len(a['clusters']) == k
        assert len({p['cluster_id'] for p in a['embedding']['points']}) == k
        assert [c['id'] for c in a['clusters']] == [f'C{i}' for i in range(k)]
        assert len({c['label_zh'] for c in a['clusters']}) == k
        assert len({c['label_en'] for c in a['clusters']}) == k
        assert len(a['metadata']['outlier_filter']['excluded_rounds']) == a['counts']['dropped_outlier']
        assert a['metadata']['excluded_pistol_rounds'] == a['counts']['excluded_pistol_rounds']
        chi = a['chi_square']
        assert chi['n'] == a['counts']['included']
        assert set(chi['economy_types']) <= {'eco', 'force', 'full'}
        assert 0 <= chi['cramers_v'] <= 1
        assert chi['p_display'] == ('p < 0.0001' if chi['p'] < 1e-4 else f"p = {chi['p']:.3g}")
        assert_player_labels([(c['label_zh'], c['label_en']) for c in a['clusters']])
        shares = np.array([list(c['region_shares_15s'].values()) for c in a['clusters']])
        selected = [c['label_callouts_15_20s'] for c in a['clusters']]
        translations = C.callout_names(load_map(a['map']))
        assert_disjoint_callouts(shares, selected, translations)
        callouts = [Counter({v['place']: v['n'] for v in c['callouts_15_20s']}) for c in a['clusters']]
        assert selected == C._label_callouts(shares, callouts, translations)
        for c, places in zip(a['clusters'], selected):
            assert all(p in c['label_en'] for p in places)
            assert all(translations.get(p, p) in c['label_zh'] for p in places)
            siblings = [j for j, other in enumerate(a['clusters']) if other['expected_players_15s'] == c['expected_players_15s']]
            if len(siblings) > 1:
                common = set.intersection(*(set(p for p, n in callouts[j].most_common(2)) for j in siblings))
                assert set(places).isdisjoint(common)
        index = json.loads((path.parent/'replay'/'index.json').read_text())
        for point in a['embedding']['points']:
            assert point['round_num'] not in (1, 13)
            assert point['replay_available'] == (point['round_num'] in index.get(point['demo_id'], []))
            if point['replay_available']:
                replay_path = path.parent/'replay'/point['demo_id']/f"{point['round_num']}.json"
                data = json.loads(replay_path.read_text())
                assert data['frames'] and any(any(p is not None for p in frame) for frame in data['frames'])
        for c in a['clusters']:
            ref = c['medoid']
            assert ref['replay_available'] is True
            data = json.loads((path.parent/'replay'/ref['demo_id']/f"{ref['round_num']}.json").read_text())
            assert data['frames'] and any(any(p is not None for p in frame) for frame in data['frames'])
            assert c['n'] >= a['metadata']['min_cluster_size']
            assert sum(c['expected_players_15s'].values()) == 5
            assert '%' not in c['label_zh']+c['label_en']
            assert c['ct_win_ci95'][0] <= c['ct_win_rate'] <= c['ct_win_ci95'][1]


def test_missing_lab_replays_exported_and_index_repaired(tmp_path):
    sub = synthetic()
    sub['positions'] = sub['positions'].filter(pl.col('round_num').is_in([2, 3])).with_columns(
        steamid=pl.col('steamid')+pl.when(pl.col('side') == 'T').then(5).otherwise(0),
        name=pl.col('steamid').cast(pl.String), team=pl.col('side'))
    sub['rounds'] = pl.DataFrame([dict(demo_id='fixture', round_num=r, dur_s=20.,
                                     t_team='T', ct_team='CT', winner_side='CT') for r in (2, 3)])
    sub['kills'] = pl.DataFrame(schema={'demo_id': pl.String, 'round_num': pl.Int64, 'is_post_round': pl.Boolean})
    sub['utility'] = pl.DataFrame(schema={'demo_id': pl.String, 'round_num': pl.Int64, 'is_post_round': pl.Boolean,
                                        'pop_t_s': pl.Float64, 'land_x': pl.Float64})
    sub['plants'] = pl.DataFrame(schema={'demo_id': pl.String, 'round_num': pl.Int64})
    mm = load_map('de_mirage')
    required = {('fixture', 2)}
    available = L.ensure_replays(sub, mm, tmp_path, required, None)
    assert available == required  # Round 3 stays disabled rather than pretending it has frames.
    path = tmp_path/'replay'/'fixture'/'2.json'
    data = json.loads(path.read_text())
    assert data['frames'] and len(data['players']) == 10
    assert any(any(p is not None for p in frame) for frame in data['frames'])
    index_path = tmp_path/'replay'/'index.json'
    assert json.loads(index_path.read_text()) == {'fixture': [2]}
    # A listed medoid with empty frames is rebuilt; nonexistent index entries are removed.
    path.write_text(json.dumps({'frames': []}))
    index_path.write_text(json.dumps({'fixture': [2, 99]}))
    assert L.ensure_replays(sub, mm, tmp_path, required, None) == required
    assert json.loads(path.read_text()) == data
    assert json.loads(index_path.read_text()) == {'fixture': [2]}
    # A second required example extends the index without losing existing replays.
    assert L.ensure_replays(sub, mm, tmp_path, {('fixture', 3)}, None) == {('fixture', 2), ('fixture', 3)}
    assert json.loads(index_path.read_text()) == {'fixture': [2, 3]}


def test_shap_no_model_has_no_active_groups():
    shap = L.shap_rounds({}, None, [])
    assert shap['active_groups'] == [] and shap['rounds'] == []
    assert shap['inactive_groups_note_zh'] == '当前模型只使用 4 组特征：人数差、血量与装备、区域占位、C4 与倒计时'
