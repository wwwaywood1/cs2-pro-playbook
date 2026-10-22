"""Schedule estimates, source identity and every exported match context."""
import json

import polars as pl
import pytest

from playbook.dates import attach_dates, attach_example_dates, demo_dates
from playbook.dedupe import demo_event_slug, demo_events
from playbook.export import team_hub_map_stats


@pytest.fixture
def schedule(tmp_path):
    raw = tmp_path / 'raw'
    raw.mkdir()
    config = tmp_path / 'events.json'
    info = {'name': 'Test Event', 'start': '2026-05-01', 'end': '2026-05-11'}
    config.write_text(json.dumps({'events': {'event': info, 'event-alias': info}}))
    overrides = tmp_path / 'match_dates.csv'
    overrides.write_text('demo_id,date\n')
    return dict(raw_dir=raw, events_path=config, overrides_path=overrides)


def demo(schedule, mid, name='a-vs-b-m1-mirage', event='event', hltv=False):
    raw = schedule['raw_dir']
    folder = raw / ('hltv' if hltv else 'cs2povarchive')
    folder = folder / f'{event}-a-vs-b-bo3-hash' if hltv else folder / event / f'{mid}-a-vs-b'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{name}.dem'
    path.touch()
    return {'demo_id': name if hltv else f'{mid}_{name}', 'hltv_match_id': None if hltv else mid}


def test_rank_interpolation_is_order_independent_and_inclusive(schedule):
    # Deliberately unequal numeric gaps: interpolate ordered series, not ID values.
    rows = [demo(schedule, mid) for mid in (50, 10, 1000)]
    result = demo_dates(pl.DataFrame(rows), **schedule)
    assert [result[r['demo_id']]['date'] for r in rows] == ['2026-05-06', '2026-05-01', '2026-05-11']
    assert {r['date_precision'] for r in result.values()} == {'day'}
    assert result == demo_dates(pl.DataFrame(rows[::-1]), **schedule)


def test_series_maps_share_date_without_inflating_id_count(schedule):
    rows = [demo(schedule, 10, f'a-vs-b-m{n}-mirage') for n in (1, 2, 3)]
    rows.append(demo(schedule, 20))
    result = demo_dates(pl.DataFrame(rows), **schedule)
    assert {r['date'] for r in result.values()} == {'2026-05-01'}
    assert {r['date_precision'] for r in result.values()} == {'event'}
    rows.append(demo(schedule, 30))
    result = demo_dates(pl.DataFrame(rows), **schedule)
    assert len({result[r['demo_id']]['date'] for r in rows[:3]}) == 1
    assert result[rows[-2]['demo_id']]['date'] == '2026-05-06'


def test_hltv_archive_and_alias_identity(schedule):
    a = demo(schedule, None, hltv=True)
    b = demo(schedule, None, 'a-vs-b-m2-nuke', hltv=True)
    c = demo(schedule, 10, event='event-alias')
    d = demo(schedule, 20, event='event-alias')
    e = demo(schedule, 30, event='event-alias')
    # Archive maps lack numeric IDs: date falls back to event, maps share it.
    result = demo_dates(pl.DataFrame([a, b, c, d, e]), **schedule)
    assert result[a['demo_id']] == result[b['demo_id']]
    assert result[a['demo_id']]['date_precision'] == 'event'
    assert result[d['demo_id']]['date'] == '2026-05-06'
    path = next((schedule['raw_dir'] / 'hltv').rglob('*.dem'))
    assert demo_event_slug(path, schedule['raw_dir']) == 'event'
    assert demo_events(schedule['raw_dir'])[a['demo_id']] == 'Event'


def test_manual_override_wins_and_applies_to_all_series_maps(schedule):
    rows = [demo(schedule, 10, f'a-vs-b-m{n}-mirage') for n in (1, 2)]
    schedule['overrides_path'].write_text(f"demo_id,date\n{rows[0]['demo_id']},2026-05-08\n")
    result = demo_dates(pl.DataFrame(rows), **schedule)
    assert {r['date'] for r in result.values()} == {'2026-05-08'}
    assert {r['date_precision'] for r in result.values()} == {'exact'}


def test_conflicting_and_invalid_manual_overrides_fail(schedule):
    rows = [demo(schedule, 10, f'a-vs-b-m{n}-mirage') for n in (1, 2)]
    schedule['overrides_path'].write_text('demo_id,date\n' + '\n'.join(
        f"{r['demo_id']},2026-05-0{i+1}" for i, r in enumerate(rows)))
    with pytest.raises(ValueError, match='Conflicting manual'):
        demo_dates(pl.DataFrame(rows), **schedule)
    schedule['overrides_path'].write_text('demo_id,date\na,2026-02-30\n')
    with pytest.raises(ValueError):
        demo_dates(pl.DataFrame(rows), **schedule)


def test_unknown_event_or_missing_raw_stays_null_unless_overridden(schedule):
    rows = [demo(schedule, 10, event='unknown'), {'demo_id': 'missing', 'hltv_match_id': 99}]
    result = demo_dates(pl.DataFrame(rows), **schedule)
    assert result[rows[0]['demo_id']] == {'date': None, 'date_precision': None, 'event': 'Unknown'}
    assert result['missing'] == {'date': None, 'date_precision': None, 'event': None}
    schedule['overrides_path'].write_text('demo_id,date\nmissing,2026-05-03\n')
    assert demo_dates(pl.DataFrame(rows), **schedule)['missing']['date_precision'] == 'exact'


def test_export_metadata_recipes_and_full_archive_sort_by_date(schedule):
    rows = [demo(schedule, mid) for mid in (10, 20, 30)]
    schedule['overrides_path'].write_text(f"demo_id,date\n{rows[0]['demo_id']},2026-05-12\n")
    matches = attach_dates(pl.DataFrame(rows), **schedule)
    recipes = [{'examples': [{'demo_id': r['demo_id'], 'round_num': 1} for r in rows]}]
    attach_example_dates(recipes, matches)
    assert [e['date'] for e in recipes[0]['examples']] == ['2026-05-12', '2026-05-11', '2026-05-06']
    profile = {'sides': {s: {'rounds': 1, 'won': 1, 'win_rate': 1} for s in ('T', 'CT')},
               'low_sample': False, 'matches': [dict(r, score_for=13, score_against=5) for r in matches.to_dicts()] * 3}
    results = team_hub_map_stats(profile)['results']
    assert len(results) == 9  # archive is not truncated before filtering
    assert results[0]['date'] == '2026-05-12'


def test_raw_population_stabilizes_dates_and_unparsed_override_dates_series(schedule):
    rows = [demo(schedule, mid) for mid in (10, 20, 30)]
    # Export only the middle demo: ranking still includes the raw endpoints.
    assert demo_dates(pl.DataFrame([rows[1]]), **schedule)[rows[1]['demo_id']]['date'] == '2026-05-06'
    sibling = demo(schedule, 20, 'a-vs-b-m2-nuke')
    schedule['overrides_path'].write_text(f"demo_id,date\n{sibling['demo_id']},2026-05-09\n")
    value = demo_dates(pl.DataFrame([rows[1]]), **schedule)[rows[1]['demo_id']]
    assert (value['date'], value['date_precision']) == ('2026-05-09', 'exact')


def test_frontend_calendar_window_boundaries_and_date_sort():
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which('node')
    if not node:
        pytest.skip('Node with native TypeScript support is not installed')
    source = Path(__file__).resolve().parents[1] / 'web/src/matchDates.ts'
    script = f'''import assert from 'node:assert/strict';
import {{inTimeRange, newestMatch, matchDateLabel}} from {json.dumps(source.as_uri())};
const within = (date, months, through) => inTimeRange({{date}}, months, through);
assert.equal(within('2026-02-28', '1', '2026-03-31'), true);
assert.equal(within('2026-02-27', '1', '2026-03-31'), false);
assert.equal(within('2024-02-29', '1', '2024-03-31'), true);
assert.equal(within('2025-11-01', '3', '2026-02-01'), true);
assert.equal(within('2025-10-31', '3', '2026-02-01'), false);
assert.equal(within('2026-08-02', '1', '2026-08-01'), false);
assert.equal(within(null, '1', '2026-08-01'), false);
assert.equal(within(null, 'all', null), true);
assert.equal(within('2026-08-01', '1', null), false);
assert.equal(matchDateLabel({{date:'2026-05-09', date_precision:'event', event:'PGL Astana 2026'}}), '2026-05 · PGL Astana 2026');
const rows = [{{demo_id:'old', date:'2026-01-01', hltv_match_id:99}},
              {{demo_id:'new', date:'2026-02-01', hltv_match_id:1}},
              {{demo_id:'unknown', date:null, hltv_match_id:100}}];
assert.deepEqual(rows.sort(newestMatch).map(row => row.demo_id), ['new','old','unknown']);
'''
    subprocess.run([node, '--input-type=module', '-e', script], check=True, capture_output=True, text=True)
