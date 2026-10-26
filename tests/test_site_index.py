"""Derived site indexes: the palette's search_index.json and per-map lineup_index.json."""
import json
import shutil
from pathlib import Path

import pytest

from playbook import site_index
from playbook.site_index import (
    LINEUP_COLUMNS,
    MATCH_COLUMNS,
    PLAYER_COLUMNS,
    RECIPE_COLUMNS,
    build_lineup_index,
    build_search_index,
    write_site_indexes,
)

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')


def _lineup(lineup_id, side='T', kind='smoke', throw='TSpawn', land='Middle', n=5, name=None, z=1.0):
    row = {'id': lineup_id, 'side': side, 'type': kind, 'throw_place': throw, 'land_place': land,
           'n_throws': n, 'n_matches': 2, 'teams': ['A', 'B'], 'throwers': ['x'],
           'throw': {'x': 1.0, 'y': 2.0, 'z': z, 'pitch': -10.5, 'yaw': 90.25, 'radar_x': 100.0, 'radar_y': 200.0},
           'land': {'x': 3.0, 'y': 4.0, 'z': 0.0, 'radar_x': 300.0, 'radar_y': 400.0},
           'practice_cmd': 'setpos 1 2 1;setang -10.5 90.25 0', 'example': {'demo_id': 'd', 'round_num': 1, 'throw_tick': 1}}
    if name:
        row['name'] = name
    return row


@pytest.fixture
def site(tmp_path):
    out = tmp_path / 'site'
    _write(out / 'index.json', {'schema_version': 1, 'generated_at': '2026-10-25T00:00:00+00:00', 'maps': [
        {'map': 'de_mirage', 'display_name': 'Mirage', 'n_matches': 3},
        {'map': 'de_cache', 'display_name': 'Cache', 'n_matches': 0},  # no data: skipped
    ]})
    def result(demo, opp, date):
        return {'demo_id': demo, 'hltv_match_id': None, 'opponent': opp, 'score_for': 13,
                'score_against': 7, 'date': date, 'date_precision': 'event', 'event': 'Major'}

    _write(out / 'heatmap_teams.json', [
        {'team': 'Vitality', 'slug': 'vitality', 'n_matches': 2, 'roster': [], 'maps': [
            {'map': 'de_mirage', 'display_name': 'Mirage', 'n_matches': 2, 'results': [result('m1', 'B8', '2026-05-01'), result('m2', 'FaZe', None)]},
            {'map': 'de_overpass', 'display_name': 'Overpass', 'n_matches': 1, 'results': [result('o1', 'B8', None)]},
        ]},
        {'team': 'B8', 'slug': 'b8', 'n_matches': 1, 'roster': [], 'maps': [
            {'map': 'de_mirage', 'display_name': 'Mirage', 'n_matches': 1, 'results': [result('m1', 'Vitality', '2026-05-01')]},
        ]},
    ])
    def ref(spot, order, lineups, name=None, label=None):
        return {'spot_id': spot, 'type': 'smoke', 'label': label or 'BombsiteA #3', 'place': 'BombsiteA', 'order': order,
                'name': name, 'share': .8, 'lineups': [{'lineup_id': i, 'n_throws': 9} for i in lineups]}

    _write(out / 'de_mirage/tactics.json', {
        'map': 'de_mirage', 'definitions': {}, 't_overview': {}, 'ct_overview': {'setups_20s': []},
        'recipes': [{'id': 'de_mirage-a-r01', 'site': 'A', 'n_rounds': 20,
                     'core': [ref('s2', 2, ['L1'], name={'zh': '丛林烟', 'en': 'Jungle smoke'})],
                     'options': [ref('s1', 1, ['L2'])]}],
        'spots': [{'spot_id': 's3', 'side': 'CT', 'lineups': [{'lineup_id': 'L3', 'n_throws': 4}]}],
    })
    _write(out / 'de_mirage/lineups.json', [
        _lineup('L1', n=40, name={'zh': '丛林烟', 'en': 'Jungle smoke'}),
        _lineup('L2', n=6, land='BombsiteA'),
        _lineup('L3', side='CT', kind='flashbang', n=4, land='BombsiteA', throw='CTSpawn'),
        _lineup('L4', n=7),                           # same group as L1 (T smoke TSpawn -> Middle)
        _lineup('L5', side='CT', kind='he', n=2),    # referenced only by a team heatmap
        _lineup('L6', side='CT', kind='he', n=2, throw='Ticket'),  # unreferenced, a 2-throw group
        {**_lineup('L7', n=9), 'land': {'radar_x': None, 'radar_y': 1}},  # no landing: never indexed
    ])
    _write(out / 'de_mirage/heatmaps/teams/vitality.json', {'summary': {'7656': {'CT': {'utility': {'spots': [
        {'spot_id': 'u1', 'lineups': [{'lineup_id': 'L5', 'n': 2}, {'lineup_id': 'gone', 'n': 1}]}]}}}}})
    _write(out / 'de_mirage/players.json', [
        {'steamid': '7656', 'name': ' ZywOo ', 'team': 'Vitality', 'T': {}, 'CT': {}},
        {'steamid': '1111', 'name': 'b8player', 'team': 'B8', 'T': {}, 'CT': {}},
    ])
    return out


def _rows(table):
    return [dict(zip(table['columns'], row)) for row in table['rows']]


def test_search_index_contents(site):
    index = build_search_index(site)
    assert index['schema_version'] == 1 and index['generated_at'] == '2026-10-25T00:00:00+00:00'
    assert _rows(index['maps']) == [{'map': 'de_mirage', 'display_name': 'Mirage'}]
    teams = _rows(index['teams'])
    assert [t['slug'] for t in teams] == ['vitality', 'b8'] and teams[0]['maps'] == [0]  # inactive Overpass dropped
    assert index['matches']['columns'] == MATCH_COLUMNS
    matches = _rows(index['matches'])
    assert [(m['team'], m['demo_id'], m['opponent'], m['date']) for m in matches] == [
        (0, 'm1', 'B8', '2026-05-01'), (0, 'm2', 'FaZe', None), (1, 'm1', 'Vitality', '2026-05-01')]
    assert index['events'] == ['Major'] and {m['event'] for m in matches} == {0}
    # Recipe spots are listed in their recipe order, with both name languages.
    assert index['recipes']['columns'] == RECIPE_COLUMNS
    (recipe,) = _rows(index['recipes'])
    assert recipe['id'] == 'de_mirage-a-r01' and recipe['map'] == 0 and recipe['site'] == 'A'
    assert recipe['spots'] == [['smoke', 'BombsiteA', 'BombsiteA #3', None, None],
                               ['smoke', 'BombsiteA', 'BombsiteA #3', '丛林烟', 'Jungle smoke']]
    # Lineups collapse to their palette label; the group links to its most-thrown lineup.
    assert index['lineups']['columns'] == LINEUP_COLUMNS
    lineups = {(r['side'], r['type'], r['throw_place'], r['land_place']): r for r in _rows(index['lineups'])}
    jungle = lineups[('T', 'smoke', 'TSpawn', 'Middle')]
    assert jungle['id'] == 'L1' and jungle['n_throws'] == 40 + 7 + 9 and jungle['name'] == ['丛林烟', 'Jungle smoke']
    assert ('CT', 'he', 'Ticket', 'Middle') not in lineups  # 2 throws < MIN_SEARCH_THROWS
    assert [r['n_throws'] for r in _rows(index['lineups'])] == sorted((r['n_throws'] for r in _rows(index['lineups'])), reverse=True)
    assert index['players']['columns'] == PLAYER_COLUMNS
    assert _rows(index['players']) == [{'steamid': '1111', 'name': 'b8player', 'teams': [[0, 'B8']]},
                                       {'steamid': '7656', 'name': 'ZywOo', 'teams': [[0, 'Vitality']]}]


def test_lineup_index_rows(site):
    index = build_lineup_index(site / 'de_mirage', json.loads((site / 'de_mirage/lineups.json').read_text()),
                               json.loads((site / 'de_mirage/tactics.json').read_text()))
    # Tactics refs (L1, L2, recipe; L3, spot) and team-heatmap refs (L5); never unreferenced or broken rows.
    assert list(index) == ['L1', 'L2', 'L3', 'L5']
    assert index['L1'] == {'side': 'T', 'type': 'smoke', 'throw_place': 'TSpawn', 'land_place': 'Middle', 'n_throws': 40,
                           'throw': [100.0, 200.0], 'land': [300.0, 400.0], 'setpos': [1.0, 2.0, 1.0, -10.5, 90.25],
                           'name': {'zh': '丛林烟', 'en': 'Jungle smoke'}}
    assert 'setpos' not in index['L5'] and 'name' not in index['L5']  # heatmap-only: drawing fields only


def test_write_site_indexes_writes_compact_files(site):
    write_site_indexes(site)
    search = (site / 'search_index.json').read_text(encoding='utf-8')
    assert '\n' not in search and ': ' not in search
    assert json.loads(search) == build_search_index(site)
    assert set(json.loads((site / 'de_mirage/lineup_index.json').read_text())) == {'L1', 'L2', 'L3', 'L5'}
    assert not (site / 'de_cache/lineup_index.json').exists()
    assert not list(site.rglob('*.tmp'))


def test_missing_and_malformed_inputs_are_skipped(site):
    (site / 'de_mirage/lineups.json').write_text('{not json', encoding='utf-8')
    (site / 'de_mirage/players.json').unlink()
    (site / 'heatmap_teams.json').write_text('{}', encoding='utf-8')
    write_site_indexes(site)
    index = json.loads((site / 'search_index.json').read_text())
    assert index['teams']['rows'] == [] and index['lineups']['rows'] == [] and index['players']['rows'] == []
    assert len(index['recipes']['rows']) == 1
    assert not (site / 'de_mirage/lineup_index.json').exists()
    empty = site.parent / 'empty'
    empty.mkdir()
    write_site_indexes(empty)
    assert json.loads((empty / 'search_index.json').read_text())['maps']['rows'] == []


def test_committed_samples_carry_current_indexes(tmp_path):
    site = tmp_path / 'site'
    shutil.copytree(ROOT / 'samples/site', site)
    write_site_indexes(site)
    lineups = {row['id'] for row in json.loads((site / 'de_mirage/lineups.json').read_text())}
    search = json.loads((site / 'search_index.json').read_text())
    assert {row[0] for row in search['teams']['rows']} == {'vitality', 'b8'}
    assert {row[0] for row in search['lineups']['rows']} <= lineups
    assert set(json.loads((site / 'de_mirage/lineup_index.json').read_text())) <= lineups
    # samples/site ships the generated indexes (CI and frontend dev); regenerate them after editing samples.
    for name in ('search_index.json', 'de_mirage/lineup_index.json'):
        assert (ROOT / 'samples/site' / name).read_text(encoding='utf-8') == (site / name).read_text(encoding='utf-8'), name


def test_search_columns_match_the_frontend():
    source = (ROOT / 'web/src/data.ts').read_text(encoding='utf-8')
    for name, columns in [('matches', MATCH_COLUMNS), ('recipes', RECIPE_COLUMNS),
                          ('lineups', LINEUP_COLUMNS), ('players', PLAYER_COLUMNS)]:
        assert f'{name}: {json.dumps(columns, separators=(", ", ": "))},' in source, name
    assert site_index.SCHEMA_VERSION == 1
