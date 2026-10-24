"""Export references stay valid while all eligible grenades reach analysis."""
import json
import polars as pl
import pytest
from playbook import export
from playbook.tactics import analyse_map
from playbook.store import write_tables
from test_heatmap import tables
from test_tactics import MM, _round


def synthetic_tables():
    parts = []
    for n in range(10):
        sub = tables()
        tactical = _round([(2800., 2000.), (2000., 2800.)])
        sub['positions'] = tactical['positions']
        sub['plants'] = tactical['plants'].with_columns(demo_id=pl.lit('d'), round_num=pl.lit(1, dtype=pl.Int32))
        sub['team_rounds'] = tactical['team_rounds'].with_columns(planted=pl.lit(True))
        sub['matches'] = pl.DataFrame({'demo_id': ['d'], 'map': ['de_test']})
        rows = []
        for kind, x in [('smoke', 2000.), ('molotov', 2400.), ('smoke', 2800.)][:3 if n < 4 else 2]:
            row = sub['utility'].row(0, named=True)
            row.update(nade_id=n * 3 + len(rows), type=kind, matched=True, throw_tick=100 + len(rows),
                       throw_x=100. if n < 2 else 100. + n * 100., throw_y=x, throw_z=0.,
                       throw_place='Ramp', land_x=x, land_y=2000., land_place='BombsiteA',
                       land_lane='A', pop_t_s=28., throw_t_s=26., thrower_name='red1',
                       pitch=0., yaw=0., is_jumping=False, is_crouched=False, is_walking=False, throw_speed=0.)
            rows.append(row)
        sub['utility'] = pl.DataFrame(rows, schema_overrides={'nade_id': pl.UInt32, 'round_num': pl.Int32,
                                                            'thrower_steamid': pl.UInt64})
        parts.append({k: v.with_columns(demo_id=pl.lit(f'd{n % 2}'), round_num=pl.lit(n + 1, dtype=pl.Int32))
                      if 'round_num' in v.columns else v.with_columns(demo_id=pl.lit(f'd{n % 2}'))
                      for k, v in sub.items()})
    result = {k: pl.concat([p[k] for p in parts]) for k in parts[0]}
    result['matches'] = result['matches'].unique()
    return result


@pytest.mark.parametrize('minimum', [2, 100])
@pytest.mark.parametrize('named', [False, True])
def test_export_has_no_dangling_lineups(tmp_path, monkeypatch, minimum, named):
    sub = synthetic_tables()
    monkeypatch.setattr(export, 'LINEUP_MIN_THROWS', minimum)
    lineups, mapping = export.build_lineups(sub, MM)
    assert mapping.height == sub['utility'].height
    assert mapping['lineup_id'].n_unique() > len(lineups)
    assert all(l['n_throws'] >= minimum for l in lineups)
    if minimum == 2:
        assert len(lineups) == 3 and {l['n_throws'] for l in lineups} == {2}
    raw = analyse_map(sub, MM, mapping)
    assert raw['recipes'] and raw['recipes'][0]['core'] and raw['recipes'][0]['options']
    # Only unrelated profile builders are stubbed; analysis and export run normally.
    monkeypatch.setattr(export, 'ACTIVE_POOL', {'de_test'})
    monkeypatch.setattr(export, 'load_map', lambda _: MM)
    community_name = {'en': 'CT smoke', 'zh': '警家烟'}
    configured = [dict(side='T', type='smoke', x=2000., y=2000., radius=200,
                       **community_name)] if named else []
    monkeypatch.setattr(export, 'load_spot_names', lambda _: configured)
    monkeypatch.setattr(export, 'team_profiles', lambda *_: [])
    monkeypatch.setattr(export, 'player_profiles', lambda *_: [])
    parsed, site = tmp_path / 'parsed', tmp_path / 'site'
    write_tables(sub, 'synthetic', parsed)
    export.export_site(parsed, site)
    mdir = site / 'de_test'
    exported = json.loads((mdir / 'lineups.json').read_text())
    ids = {l['id'] for l in exported}
    assert [{k: v for k, v in row.items() if k != 'name'} for row in exported] == lineups
    named_rows = [row for row in exported if row.get('name')]
    if named and minimum == 2:
        assert len(named_rows) == 1
        assert named_rows[0]['name'] == community_name
        assert named_rows[0]['type'] == 'smoke'
        assert named_rows[0]['land']['x'] == 2000.
    else:
        assert not named_rows
    tactics = json.loads((mdir / 'tactics.json').read_text())
    groups = [tactics['spots']]
    for recipe in tactics['recipes']:
        groups.extend([recipe['core'], recipe['options']])
    heatmap_spots = []
    for path in (mdir / 'heatmaps' / 'teams').glob('*.json'):
        for sides in json.loads(path.read_text())['summary'].values():
            for summary in sides.values():
                heatmap_spots.extend(summary['utility']['spots'])
    assert heatmap_spots
    groups.append(heatmap_spots)
    refs = [ref['lineup_id'] for group in groups for spot in group for ref in spot['lineups']]
    assert set(refs) <= ids
    assert bool(refs) == bool(ids)
    assert sum(s['n'] for s in heatmap_spots) == sub['utility'].height
    assert json.loads((site / 'index.json').read_text())['maps'][0]['n_lineups'] == len(ids)
