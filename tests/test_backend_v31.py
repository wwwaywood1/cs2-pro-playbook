"""Regressions for displayed route identity, early windows and combat/replay scopes."""
import json

import polars as pl
import pytest

from playbook.config import CONFIG_DIR, load_map
from playbook.export import player_profiles
from playbook.heatmap import build_heatmaps, clean_frames
from playbook.replay import callout_index, event_place
from playbook.tactics import recipe_extras, recipe_routes
from playbook.zones import make_summarizer
from test_gpt23_metrics import recipe_fixture
from test_heatmap import MM, SID, tables
from test_routes import MM as ROUTE_MM, _round


def test_route_name_uses_drawn_stretches_instead_of_time_spent_at_boundary():
    # Palace has three seconds of utility dwell but only one drawn sample;
    # the approach is visibly Ramp. The old dwell key names this Palace.
    path = [(0, 0, 'Spawn'), (0, 0, 'Spawn'), (40, 0, 'Ramp'), (70, 0, 'Ramp'),
            (89, 0, 'Palace'), (89, 0, 'Palace'), (89, 0, 'Palace'), (90, 0, 'BombsiteA')]
    pos = pl.DataFrame(_round('d', 1, {'p': path})).with_columns(pl.col('t_s').cast(pl.Int32))
    plans = pl.DataFrame([dict(demo_id='d', round_num=1, team='Alpha', recipe_id='r', commit_s=7.)])
    route = recipe_routes(plans, pos, ROUTE_MM)['r'][0]
    assert route['name'] == 'Ramp' and 'Palace' not in route['via']
    assert set(route['via']) <= set(route['point_places']) <= set(pos['place'])
    assert route['medoid_member'] == dict(demo_id='d', round_num=1, steamid='p')


def test_merged_extension_keeps_drawn_members_callouts():
    # Majority stops halfway; the minority extends the displayed route.
    short = [(0, 0, 'Spawn')] * 2 + [(40, 0, 'Ramp'), (50, 0, 'Ramp'), (60, 0, 'Mid'), (65, 0, 'Mid')]
    full = [(0, 0, 'Spawn')] * 2 + [(40, 0, 'Ramp'), (60, 0, 'Ramp'), (80, 0, 'BombsiteA'), (90, 0, 'BombsiteA')]
    pos = pl.DataFrame(_round('d', 1, {'a': short, 'b': short, 'c': full})).with_columns(pl.col('t_s').cast(pl.Int32))
    plans = pl.DataFrame([dict(demo_id='d', round_num=1, team='Alpha', recipe_id='r', commit_s=5.)])
    route = recipe_routes(plans, pos, ROUTE_MM)['r'][0]
    assert route['n'] == 3 and route['points'][-1][0] == 90
    assert route['medoid_member']['steamid'] == 'c'
    assert set(route['via']) <= set(route['point_places']) <= set(pos.filter(pl.col('steamid') == 'c')['place'])


def test_all_configured_route_callouts_have_chinese_names():
    names = json.loads((CONFIG_DIR / 'route_names.json').read_text())
    for map_name, translations in names.items():
        if map_name.startswith('_'):
            continue
        assert set(translations) == set(load_map(map_name).callout_region)
        assert all(any('\u4e00' <= c <= '\u9fff' for c in label) for label in translations.values())


def test_sync_uses_first_paired_arrivals_and_excludes_postplant():
    rec, plans, pos, members = recipe_fixture(second=23.1)
    assert 'sync_pinch' not in recipe_extras(rec, plans, pos, members)['intent_badges']
    rec, plans, pos, members = recipe_fixture(second=23)
    # Later presence from either route cannot replace its first arrival.
    later = pos.with_columns(t_s=pl.col('t_s') + 20)
    assert recipe_extras(rec, plans, pl.concat([pos, later]), members)['entry_sync_sec'] == 3
    plans = plans.with_columns(plant_t_s=pl.lit(22.))
    extra = recipe_extras(rec, plans, pos, members)
    assert extra['entry_sync_sec'] is None and extra['entry_sync_rounds'] == 0
    assert 'sync_pinch' not in extra['intent_badges']


def test_early_heatmap_and_zone_summary_share_six_to_twenty_window():
    sub = tables()
    # Distinct places for t=5 vs t=6. A frame at t=20 must be mid.
    sub['positions'] = sub['positions'].with_columns(
        place=pl.when(pl.col('t_s') < 6).then(pl.lit('Spawn')).otherwise(pl.col('place')))
    frame20 = sub['positions'].tail(1).with_columns(t_s=pl.lit(20, dtype=pl.Int32))
    sub['positions'] = pl.concat([sub['positions'], frame20])
    sub['team_rounds'] = sub['team_rounds'].with_columns(plant_t_s=pl.lit(None, dtype=pl.Float64))
    hm = build_heatmaps(sub, MM, summaries=make_summarizer(MM))
    early = hm['frames']['presence'].filter(pl.col('phase') == 'early')
    assert early['t_s'].to_list() == [6, 7, 8]
    assert 'Spawn' not in early['place'].to_list()
    assert hm['baseline']['spawn_skip_s'] == 6 and hm['baseline']['early_s'] == 20
    summary = hm['teams']['red']['summary'][str(SID)]['T']
    assert summary['zones']['early'][0]['place'] == 'Spot'
    assert sum(hm['teams']['red']['players'][str(SID)]['data']['T']['early']['presence'][1::2]) == early.height


def test_kpr_includes_eco_all_sides_and_missing_coordinates_but_separates_teams():
    sub = tables()
    base = sub['player_rounds'].filter(pl.col('steamid') == SID)
    extra = [base.with_columns(round_num=pl.lit(n, dtype=pl.Int32), buy_type=pl.lit(buy),
                               side=pl.lit(side), team=pl.lit(team), kills=pl.lit(kills, dtype=pl.Int64))
             for n, buy, side, team, kills in [(2, 'eco', 'T', 'Red', 3), (3, 'full', 'CT', 'Red', 5),
                                               (4, 'full', 'T', 'Green', 10)]]
    sub['player_rounds'] = pl.concat([sub['player_rounds'], *extra])
    # A kill without radar coordinates cannot enter the spatial layer.
    sub['kills'] = sub['kills'].with_columns(attacker_x=pl.lit(None, dtype=pl.Float64))
    hm = build_heatmaps(sub, MM, summaries=make_summarizer(MM))
    player = hm['teams']['red']['players'][str(SID)]
    assert player['stats']['kpr'] == 3 and player['stats']['kills'] == 9 and player['stats']['rounds'] == 3
    assert player['stats']['sides']['T']['kpr'] == 2
    assert player['stats']['sides']['CT']['kpr'] == 5
    fights = hm['teams']['red']['summary'][str(SID)]['T']['fights']
    assert fights['kills_pr'] == 2 and fights['rounds'] == 2 and fights['kills'] == 4
    assert fights['places'] == []
    # Supply the unrelated profile columns to exercise the real profile exporter.
    sub['player_rounds'] = sub['player_rounds'].with_columns(
        site_entry_rank=pl.lit(None, dtype=pl.Int32), hs_kills=pl.lit(0), death_traded=pl.lit(False),
        is_awp=pl.lit(False), util_thrown=pl.lit(0), dist_to_team_30s=pl.lit(None, dtype=pl.Float64),
        lane_15s=pl.lit('A'), place_30s=pl.lit('Spot'))
    profiles = [p for p in player_profiles(sub) if p['steamid'] == str(SID)]
    assert {p['team']: p['kpr'] for p in profiles} == {'Red': 3, 'Green': 10}
    assert next(p for p in profiles if p['team'] == 'Red')['kpr'] == player['stats']['kpr']


def test_replay_place_prefers_parsed_landing_or_victim_and_falls_back_by_height():
    pos = pl.DataFrame({'x': [10., 10.], 'y': [10., 10.], 'z': [0., 300.], 'place': ['Lower', 'Upper']})
    idx = callout_index(pos)
    assert event_place(dict(land_x=10., land_y=10., land_z=300.), 'land_', idx) == 'Upper'
    assert event_place(dict(victim_x=10., victim_y=10., victim_z=0.), 'victim_', idx) == 'Lower'
    assert event_place(dict(land_place='Parsed', land_x=10., land_y=10., land_z=300.), 'land_', idx) == 'Parsed'
    assert event_place(dict(land_x=float('nan'), land_y=10., land_z=300.), 'land_', idx) is None


def test_replay_exports_actor_side_destination_place_and_filterable_flashes():
    from playbook.replay import build_round
    pos = pl.DataFrame([
        dict(demo_id='d', round_num=1, t_s=t, steamid=sid, name=sid, side=side, team=side,
             x=x, y=10., z=0., alive=True, place=place)
        for t in range(4) for sid, side, x, place in [('a', 'T', 10., 'Thrower'), ('b', 'CT', 100., 'Victim')]])
    sub = dict(
        positions=pos,
        rounds=pl.DataFrame([dict(demo_id='d', round_num=1, dur_s=3., t_team='T', ct_team='CT', winner_side='T')]),
        kills=pl.DataFrame([dict(demo_id='d', round_num=1, t_s=2., is_post_round=False, attacker_steamid='a',
                                victim_steamid='b', victim_x=100., victim_y=10., victim_z=0., victim_place='Victim', weapon='ak47')]),
        utility=pl.DataFrame([dict(demo_id='d', round_num=1, pop_t_s=1., is_post_round=False, type=kind,
                                  thrower_steamid='b', land_x=10., land_y=10., land_z=0., land_place='Landing')
                             for kind in ['smoke', 'flashbang']]),
        plants=pl.DataFrame([dict(demo_id='d', round_num=1, t_s=3., site='A', steamid='a', x=10., y=10., z=0., place='BombsiteA')]))
    r = build_round(sub, MM, 'd', 1, [.5, .6, .8, 1.])
    utils = [e for e in r['events'] if e['kind'] == 'util']
    assert len(utils) == 2 and all(e['side'] == 'CT' and e['place'] == 'Landing' for e in utils)
    assert [e['is_flash'] for e in utils] == [False, True]
    kill = next(e for e in r['events'] if e['kind'] == 'kill')
    assert kill['side'] == 'T' and kill['place'] == 'Victim' and kill['wpa'] == .2
    plant = next(e for e in r['events'] if e['kind'] == 'plant')
    assert plant['side'] == 'T' and plant['site'] == 'A' and r['players'][plant['by']]['name'] == 'a'


def test_wpa_side_baselines_are_round_weighted_and_center_each_side():
    from playbook.export import side_baselines
    rows = {("1", "A", "T"): (100, -0.03, -0.02, -0.01), ("2", "B", "T"): (300, -0.01, -0.01, 0.0),
            ("3", "A", "CT"): (200, 0.02, 0.015, 0.005), ("4", "C", "T"): (0, 9.0, 9.0, 9.0)}
    base = side_baselines(rows)
    assert base["T"] == pytest.approx((-0.015, -0.0125, -0.0025))   # (100*-0.03 + 300*-0.01) / 400
    assert base["CT"] == pytest.approx((0.02, 0.015, 0.005))
    centered = sum(v[0] * (v[1] - base["T"][0]) for k, v in rows.items() if k[2] == "T")
    assert centered == pytest.approx(0)


def test_player_name_columns_are_trimmed_in_every_table():
    from playbook.export import tidy_player_names
    t = {"player_rounds": pl.DataFrame({"steamid": [1, 1], "name": [" NAF-FLY", "NAF-FLY "]}),
         "positions": pl.DataFrame({"steamid": [1], "name": [" NAF-FLY"], "place": [" Mid"]}),
         "kills": pl.DataFrame({"attacker_name": [" a "], "victim_name": ["b "], "weapon": [" ak47"]})}
    out = tidy_player_names(t)
    assert out["player_rounds"]["name"].to_list() == ["NAF-FLY", "NAF-FLY"]
    assert out["positions"]["name"].to_list() == ["NAF-FLY"] and out["positions"]["place"].to_list() == [" Mid"]
    assert out["kills"]["attacker_name"].to_list() == ["a"] and out["kills"]["victim_name"].to_list() == ["b"]
    assert out["kills"]["weapon"].to_list() == [" ak47"]
