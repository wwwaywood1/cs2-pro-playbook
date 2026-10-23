"""GPT-33 archive identities and observed awpy recording boundary cases."""
from pathlib import Path

import polars as pl
import pytest

from playbook.config import canonical_team, load_team_aliases
from playbook.dedupe import demo_event_slug, deduplicate_tables
from playbook.multipart import _stitch_rounds
from playbook.parse import _leading_round_bounds, _validate_rounds, demo_identity
from tests.test_multipart import rounds


def test_archive_identity_is_series_scoped_and_multipart_stable():
    a = Path('raw/hltv/bounty-a-vs-b-bo3-hash/a-vs-b-m3-mirage-p1.dem')
    b = Path('raw/hltv/epl-a-vs-b-bo3-hash/a-vs-b-m3-mirage-p1.dem')
    assert demo_identity(a) != demo_identity(b)
    assert demo_identity(a) == demo_identity(a.with_name('a-vs-b-m3-mirage-p2.dem'))
    assert demo_identity(a)['hltv_match_id'] is None
    assert demo_identity(a) == demo_identity(Path('/elsewhere') / a)


def test_legacy_binding_is_explicit_and_new_series_cannot_steal_it(monkeypatch):
    monkeypatch.setattr('playbook.parse._hltv_legacy_ids', lambda: {'old/a-vs-b-m1-nuke':'a-vs-b-m1-nuke'})
    assert demo_identity(Path('hltv/old/a-vs-b-m1-nuke.dem'))['demo_id'] == 'a-vs-b-m1-nuke'
    assert demo_identity(Path('hltv/new/a-vs-b-m1-nuke.dem'))['demo_id'] != 'a-vs-b-m1-nuke'
    assert demo_identity(Path('hltv/new/42_a-vs-b-nuke.dem')) == {
        'demo_id':'42_a-vs-b-nuke', 'hltv_match_id':42}


def test_scoped_archive_copies_still_content_dedupe():
    ids = [demo_identity(Path(f'hltv/{series}/a-vs-b-m1-nuke.dem'))['demo_id'] for series in ('one','two')]
    m = pl.DataFrame([dict(demo_id=i,map='de_nuke',team_a='A',team_b='B',n_rounds=2,score_a=1,score_b=1) for i in ids])
    r = pl.DataFrame([dict(demo_id=i,round_num=n,winner_team=t) for i in ids for n,t in [(1,'A'),(2,'B')]])
    tables, dropped = deduplicate_tables({'matches':m,'rounds':r})
    assert tables['matches'].height == 1
    assert tables['rounds'].height == 2
    assert len(dropped) == 1


def test_leading_missing_start_preserves_every_live_tick():
    r = rounds([1,2]).with_columns(pl.when(pl.col('round_num') == 1).then(None).otherwise('start_tick').alias('start_tick'))
    # Polars 'otherwise' treats the column name as an expression.
    fixed = _leading_round_bounds(r)
    assert fixed['start_tick'].to_list() == [10,100]
    assert fixed['freeze_end_tick'].to_list() == r['freeze_end_tick'].to_list()
    _validate_rounds(fixed)


def test_half_recording_with_observed_freeze_end_is_recoverable():
    second = rounds([13,14]).with_columns(pl.when(pl.col('round_num') == 13).then(None).otherwise('start_tick').alias('start_tick'))
    r, kept, offsets = _stitch_rounds([rounds(list(range(1,13))),second])
    _validate_rounds(r)
    assert r['round_num'].to_list() == list(range(1,15))
    assert kept[1]['start_tick'][0] == kept[1]['freeze_end_tick'][0] == 10


@pytest.mark.parametrize('case', ['missing_freeze','interior_start','overlap','reset'])
def test_real_missing_live_history_and_restores_still_rejected(case):
    r = rounds([1,2,3])
    if case == 'missing_freeze':
        r = r.with_columns(pl.when(pl.col('round_num') == 1).then(None).otherwise('freeze_end_tick').alias('freeze_end_tick'))
    elif case == 'interior_start':
        r = r.with_columns(pl.when(pl.col('round_num') == 2).then(None).otherwise('start_tick').alias('start_tick'))
    elif case == 'overlap':
        r = r.with_columns(pl.when(pl.col('round_num') == 2).then(85).otherwise('start_tick').alias('start_tick'))
    else:
        r = r.with_columns(pl.Series('round_num',[1,2,2]))
    with pytest.raises(ValueError):
        _validate_rounds(_leading_round_bounds(r))


def restart_marker():
    r = rounds([1]).with_columns(start_tick=None,freeze_end_tick=None,end_tick=pl.lit(1),official_end_tick=pl.lit(1),
                                winner_side=pl.lit('unassigned'),winner=pl.lit(0),reason=pl.lit(0),reason_name=pl.lit('still_in_progress'))
    return r


def test_tick_one_restart_marker_needs_a_complete_copy():
    second = pl.concat([restart_marker(), rounds([2,3]).with_columns(winner=pl.lit(2),reason=pl.lit(9),reason_name=pl.lit('terrorists_win'))],how='diagonal_relaxed')
    r,kept,_ = _stitch_rounds([rounds([1]),second])
    assert [p['round_num'].to_list() for p in kept] == [[1],[2,3]]
    _validate_rounds(r)
    with pytest.raises(ValueError,match='no complete copy'):
        _stitch_rounds([second])
    bad = second.with_columns(pl.when(pl.col('round_num') == 1).then(2).otherwise('end_tick').alias('end_tick'))
    with pytest.raises(ValueError,match='winner'):
        _stitch_rounds([rounds([1]),bad])


def test_aliases_and_virtus_event_spelling():
    aliases=load_team_aliases()
    for a,b in [('PVISION','PARIVISION'),('BC Game Esports','BC.Game'),('Virtus.pro_','Virtus.pro'),('FUT','FUT Esports')]:
        assert canonical_team(a,aliases)==b
    raw=Path('/raw')
    p=raw/'hltv/blast-bounty-2026-season-1-virtuspro-vs-vitality-bo3-hash/virtus-pro-vs-vitality-m2-dust2.dem'
    assert demo_event_slug(p,raw)=='blast-bounty-2026-season-1'
