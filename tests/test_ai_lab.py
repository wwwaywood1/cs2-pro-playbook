"""Numerical and data-contract checks for CT patterns and the research lab."""
import json
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
                           buy_type=('full', 'force', 'eco', 'pistol')[r % 4], equipment_value=18000,
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
    assert x.shape == (71, 103)
    assert counts == dict(total=72, eligible_at_10=71, dropped_at_10=1, dropped_incomplete=0, included=71)
    a, edges = C.build(sub, load_map('de_mirage'))
    b, _ = C.build({k: v.reverse() for k, v in sub.items()}, load_map('de_mirage'))
    assert a == b
    k = a['metadata']['k']
    assert 1 <= k <= 2  # 71 rounds cannot support 3 clusters of >=30.
    assert len(a['clusters']) == k
    assert len(set(c['label_zh'] for c in a['clusters'])) == k
    assert all(c['n'] >= 30 for c in a['clusters'])
    shares = [c['region_shares_15s']['A'] for c in a['clusters']]
    assert shares == sorted(shares)
    assert sum(c['n'] for c in a['clusters']) == 71-a['counts']['dropped_outlier']
    assert sum(c['share'] for c in a['clusters']) == pytest.approx(1.)
    for edge in edges:
        for snap in edge['snapshots']:
            assert np.asarray(snap['positions']).shape == (5, 3)
            np.testing.assert_allclose(np.asarray(snap['alpha']).sum(axis=1), 1.)
    json.dumps(a, allow_nan=False)


def test_largest_remainder_compositions_and_distinct_word_labels():
    np.testing.assert_array_equal(C.player_counts(np.array([.34, .26, .30, .10, 0.])), [2, 1, 2, 0, 0])
    np.testing.assert_array_equal(C.player_counts(np.full(5, .2)), [1, 1, 1, 1, 1])
    # Two balanced profiles in the middle depth third require a regional word.
    shares = np.array([[.30, .30, .40, 0, 0], [.36, .25, .39, 0, 0],
                       [.20, .20, .60, 0, 0], [.60, .20, .20, 0, 0]])
    names = C._labels(shares, np.array([.3, .3, .1, .5]))
    assert len({zh for zh, en in names}) == len({en for zh, en in names}) == 4
    assert names[0][0].startswith('A2·中1·B2 均衡')
    assert all('%' not in zh+en for zh, en in names)
    assert all('前压' not in zh and '回收' not in zh for zh, en in names)
    for s in shares:
        assert C.player_counts(s).sum() == 5
    depths = np.array([.1, .9])
    names = C._labels(shares[:1].repeat(2, axis=0), depths)
    assert '回收' in names[0][0] and '前压' in names[1][0]


def test_colliding_labels_in_same_depth_third_omit_redundant_depth_word():
    shares = np.array([[.30, .30, .40, 0, 0], [.36, .25, .39, 0, 0],
                       [.80, .20, 0, 0, 0], [0, .80, .20, 0, 0],
                       [.20, 0, .80, 0, 0], [.20, 0, 0, .80, 0]])
    # Both balanced profiles are in the bottom third; depth cannot separate them.
    names = C._labels(shares, np.array([.10, .11, .30, .40, .50, .60]))
    assert len({zh for zh, en in names}) == len({en for zh, en in names}) == 6
    for zh, en in names[:2]:
        assert zh.startswith('A2·中1·B2 均衡')
        assert '回收' not in zh and '前压' not in zh
        assert 'deep' not in en and 'forward' not in en
        assert '%' not in zh+en


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
    assert counts['included'] == 70 and counts['dropped_incomplete'] == 1
    assert x.shape == (70, 103)
    assert 70 in {r['round_num'] for r in rows} and 71 not in {r['round_num'] for r in rows}
    assert next(r for r in rows if r['round_num'] == 4)['after_loss']


def test_chi_square_known_independence_and_dependence():
    independent = C.chi_square(np.array([[10, 20], [20, 40]]), ['eco', 'full'])
    assert independent['statistic'] == 0 and independent['p'] == 1
    dependent = C.chi_square(np.array([[90, 10], [10, 90]]), ['eco', 'full'])
    assert dependent['dof'] == 1 and dependent['statistic'] == pytest.approx(128)
    assert dependent['p'] < 1e-20
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
    control = lab['control']
    assert control['map'] == 'de_mirage' and len(control['cells']) == 225
    assert len(control['snapshots']) == 3
    for s in control['snapshots']:
        assert len(s['ownership']) == len(s['delta_distance']) == 225
    for path in sorted(root.glob('*/ct_patterns.json')):
        a = json.loads(path.read_text())
        assert a['schema_version'] == 1
        assert a['counts']['total'] == sum(a['counts'][key] for key in ('included', 'dropped_at_10', 'dropped_incomplete', 'dropped_outlier'))
        assert len(a['embedding']['points']) == a['counts']['included']
        k = a['metadata']['k']
        assert len(a['clusters']) == k
        assert len({p['cluster_id'] for p in a['embedding']['points']}) == k
        assert [c['id'] for c in a['clusters']] == [f'C{i}' for i in range(k)]
        assert len({c['label_zh'] for c in a['clusters']}) == k
        assert len({c['label_en'] for c in a['clusters']}) == k
        assert len(a['metadata']['outlier_filter']['excluded_rounds']) == a['counts']['dropped_outlier']
        for c in a['clusters']:
            assert c['n'] >= a['metadata']['min_cluster_size']
            assert sum(c['expected_players_15s'].values()) == 5
            assert '%' not in c['label_zh']+c['label_en']
            assert c['ct_win_ci95'][0] <= c['ct_win_rate'] <= c['ct_win_ci95'][1]
