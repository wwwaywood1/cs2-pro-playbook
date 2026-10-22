"""Numerical fixtures for every GPT-23 metric and its missing-data boundaries."""
import logging

import numpy as np
import polars as pl
import pytest

from playbook.config import MapMeta
from playbook.radar6 import AXES, percentile, player_radar
from playbook.replay import control_grid, kill_wpa, t_control, wp_by_round
from playbook.tactics import _route_names, recipe_extras, route_name


def test_route_name_last_non_site_and_config_validation(tmp_path, monkeypatch, caplog):
    import playbook.tactics as tactics
    (tmp_path / 'route_names.json').write_text('{"test": {"Ramp": "主攻线", "Bogus": "bad"}}')
    monkeypatch.setattr(tactics, 'CONFIG_DIR', tmp_path)
    _route_names.cache_clear()
    mm = MapMeta('test', 'test', {}, {'Ramp': 'APPROACH', 'Other': 'A_SITE', 'BombsiteA': 'A_SITE'})
    with caplog.at_level(logging.WARNING):
        assert route_name(['Other', 'Ramp', 'BombsiteA'], mm) == '主攻线'
        assert route_name(['Other', 'BombsiteA'], mm) == 'Other'
    assert sum('Bogus' in r.message for r in caplog.records) == 1
    _route_names.cache_clear()


def recipe_fixture(second=23):
    plans, positions = [], []
    for rnd in range(1, 5):
        plans.append(dict(demo_id='d', round_num=rnd, team='X', recipe_id='r', commit_s=30.,
                          plant_site='B' if rnd == 1 else None))
        for sid, time in [('a', 20), ('b', second)]:
            positions.append(dict(demo_id='d', round_num=rnd, team='X', steamid=sid,
                                  side='T', alive=True, place='BombsiteA', t_s=time))
    recipe = {'id': 'r', 'site': 'A', 'routes': [{'share': .5}, {'share': .2}]}
    members = [{('d', r, sid) for r in range(1, 5)} for sid in ('a', 'b')]
    return recipe, pl.DataFrame(plans), pl.DataFrame(positions), members


def test_recipe_paired_median_intent_and_boundaries():
    rec, plans, pos, members = recipe_fixture()
    extras = recipe_extras(rec, plans, pos, members)
    assert extras['entry_sync_sec'] == 3
    assert extras['other_site_plant_rate'] == .25  # denominator includes no-plant rounds
    assert extras['median_first_entry_delay_sec'] == 5
    assert extras['intent_badges'] == ['fake', 'sync_pinch', 'rush']
    rec['routes'][1]['share'] = .199
    assert 'sync_pinch' not in recipe_extras(rec, plans, pos, members)['intent_badges']
    rec, plans, pos, members = recipe_fixture(second=24)
    assert 'sync_pinch' not in recipe_extras(rec, plans, pos, members)['intent_badges']
    assert recipe_extras(rec, plans, pos, members[:1])['entry_sync_sec'] is None
    assert recipe_extras(rec, plans, pos.filter(pl.col('steamid') == 'a'), members)['entry_sync_sec'] is None
    assert 'rush' not in recipe_extras(rec, plans, pos.with_columns(pl.lit(24).alias('t_s')), members)['intent_badges']
    assert recipe_extras(rec, plans, pos.clear(), members)['intent_badges'] == ['fake']


def radar_fixture():
    players = [(1, 'T'), (2, 'T'), (3, 'CT'), (4, 'CT')]
    pr = pl.DataFrame([dict(demo_id='d', round_num=1, steamid=sid, side=side,
                            team=side, won=side == 'T') for sid, side in players])
    rows = []
    for t in (0, 16, 17, 19, 20, 21, 23, 30):
        for sid, side in players:
            x = 0 if side == 'T' else 1000
            if sid == 2:
                x = {0: 0, 16: 100, 17: 200, 19: 300, 20: 400, 21: 500, 23: 600, 30: 800}[t]
            if sid == 3 and t >= 16:
                x = 100 if t < 19 else 300
            rows.append(dict(demo_id='d', round_num=1, steamid=sid, team=side, side=side,
                             t_s=t, x=float(x), y=0., z=0., alive=not (sid == 1 and t >= 17 or sid == 3 and t >= 21)))
    kills = pl.DataFrame([
        dict(t_s=16.4, attacker_steamid=3, victim_steamid=1, attacker_side='CT', victim_side='T', assister_steamid=None, assist_flash=False),
        dict(t_s=20.4, attacker_steamid=2, victim_steamid=3, attacker_side='T', victim_side='CT', assister_steamid=1, assist_flash=True),
    ]).with_columns(pl.lit('d').alias('demo_id'), pl.lit(1).alias('round_num'), pl.lit(False).alias('is_post_round'))
    util = pl.DataFrame([dict(demo_id='d', round_num=1, thrower_steamid=2, type='molotov', pop_t_s=16.,
                              land_x=100., land_y=0., land_z=0., is_post_round=False)])
    plants = pl.DataFrame([dict(demo_id='d', round_num=1, t_s=20.)])
    return dict(player_rounds=pr, positions=pl.DataFrame(rows), kills=kills, utility=util,
                plants=plants, rounds=pl.DataFrame([dict(demo_id='d', round_num=1, dur_s=30.)]))


def test_radar_all_six_raw_metrics_and_missing_clutches():
    sub = radar_fixture()
    wp = pl.DataFrame([dict(demo_id='d', round_num=1, t_s=17, wp_t=.3),
                       dict(demo_id='d', round_num=1, t_s=21, wp_t=.8)])
    out = player_radar(sub, wp)
    a, b, d = out[('1', 'T')], out[('2', 'T')], out[('4', 'CT')]
    assert a['entry']['raw'] == 1 and b['entry']['raw'] == 0
    assert a['trade_components']['own_deaths_traded_rate'] == 1
    assert b['trade_components']['teammate_deaths_traded_rate'] == 1
    assert a['trade']['raw'] == 1 and b['trade']['raw'] == 1
    assert b['lurk_distance']['raw'] == 100 and d['lurk_distance']['raw'] is None
    assert b['space_gain']['raw'] == 800
    assert a['utility_counts']['flash_assists'] == 1
    assert b['utility_counts']['molotov_displacements'] == 1
    assert a['utility_impact']['raw'] == b['utility_impact']['raw'] == 1
    assert b['clutch_wpa']['raw'] == .7 and b['clutch_situations'] == 1
    assert d['clutch_wpa']['raw'] == -.2  # CT perspective: 0 - (1 - .8)
    assert a['clutch_wpa']['raw'] is None
    assert all(b[axis]['percentile'] is None for axis in AXES)  # <50 rounds
    assert player_radar(sub)[('2', 'T')]['clutch_wpa']['raw'] is None


def test_trade_window_and_molotov_radius_movement_vertical_boundaries():
    sub = radar_fixture()
    sub['kills'] = sub['kills'].with_columns(pl.when(pl.col('attacker_steamid') == 2).then(20.41).otherwise(pl.col('t_s')).alias('t_s'))
    sub['utility'] = sub['utility'].with_columns(pl.lit(121.).alias('land_z'))
    out = player_radar(sub)
    assert out[('1', 'T')]['trade']['raw'] == 0
    assert out[('2', 'T')]['utility_impact']['raw'] == 0
    sub = radar_fixture()
    # Exactly 150 units of movement is insufficient; >150 is required.
    sub['positions'] = sub['positions'].with_columns(pl.when((pl.col('steamid') == 3) & (pl.col('t_s') >= 19)).then(250.).otherwise(pl.col('x')).alias('x'))
    assert player_radar(sub)[('2', 'T')]['utility_counts']['molotov_displacements'] == 0


def test_percentiles_same_side_minimum_rounds_ties_and_ct_lurk():
    sub = radar_fixture()
    extra = sub['player_rounds'].filter(pl.col('steamid').is_in([1, 2, 3]))
    sub['player_rounds'] = pl.concat([sub['player_rounds'], *[extra.with_columns(pl.lit(i, dtype=pl.Int64).alias('round_num')) for i in range(2, 51)]])
    out = player_radar(sub)
    assert out[('1', 'T')]['eligible'] and not out[('4', 'CT')]['eligible']
    assert out[('1', 'T')]['entry']['percentile'] == 75
    assert out[('2', 'T')]['entry']['percentile'] == 25
    assert out[('3', 'CT')]['entry']['percentile'] == 50
    assert out[('3', 'CT')]['lurk_distance']['percentile'] is None
    assert percentile(5, [5, 5]) == 50 and percentile(None, [1]) is None


def test_control_occupied_grid_nearest_alive_ties_and_absent_sides():
    pos = pl.DataFrame({'x': [0., 100., 100.], 'y': [0., 100., 100.], 't_s': [0, 0, 1]})
    grid = control_grid(pos)
    assert len(grid) == 2  # observed cells only, not all 225 cells
    t, ct = np.array([[0., 0.]]), np.array([[100., 100.]])
    assert t_control(t, ct, grid) == .5
    assert t_control(t, t, grid) == 0  # ties do not count as closer
    empty = np.empty((0, 2))
    assert t_control(t, empty, grid) == 1 and t_control(empty, ct, grid) == 0
    assert t_control(empty, empty, grid) is None


def test_kill_wpa_sign_terminal_outcome_missing_states_and_second_indexes():
    assert kill_wpa(1.2, 'T', [.5, .4, .5, .7], 5, 'T') == .3
    assert kill_wpa(1.2, 'CT', [.5, .4, .5, .7], 5, 'T') == -.3
    assert kill_wpa(3.2, 'CT', [.5, .4, .5, .7], 3.5, 'CT') == .7
    assert kill_wpa(2, None, [.5] * 5, 5, 'T') is None
    assert kill_wpa(2, 'T', [], 5, 'T') is None
    s = pl.DataFrame({'demo_id': ['d', 'd'], 'round_num': [1, 1], 't_s': [0, 2]})
    assert wp_by_round(s, np.array([.4, .8]), {('d', 1)})[('d', 1)] == [.4, None, .8]
