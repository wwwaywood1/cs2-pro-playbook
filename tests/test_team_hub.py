"""Team hub sample denominators and owner-supplied quote export."""
import json

import pytest

from playbook.export import export_player_quotes, team_hub_map_stats


def test_map_wins_are_not_round_win_rates():
    profile = {
        'low_sample': True,
        'sides': {'T': {'rounds': 10, 'won': 8, 'win_rate': .8},
                  'CT': {'rounds': 30, 'won': 12, 'win_rate': .4}},
        'matches': [
            {'demo_id': 'old', 'hltv_match_id': 10, 'score_for': 13, 'score_against': 2},
            {'demo_id': 'new', 'hltv_match_id': 20, 'score_for': 7, 'score_against': 13},
            {'demo_id': 'draw', 'hltv_match_id': None, 'score_for': 10, 'score_against': 10},
        ],
    }
    stats = team_hub_map_stats(profile)
    assert stats['map_win_rate'] == .333
    assert stats['round_win_rate'] == .5  # weighted by rounds, not mean of .8 and .4
    assert stats['all_rounds'] == 40
    assert (stats['win_rate_T'], stats['win_rate_CT']) == (.8, .4)
    assert [m['demo_id'] for m in stats['results']] == ['new', 'old', 'draw']
    assert stats['low_sample'] is True
    assert profile['matches'][0]['demo_id'] == 'old'  # no mutation


def test_no_rounds_or_matches_is_unknown_not_zero():
    profile = {'low_sample': True, 'matches': [],
               'sides': {s: {'rounds': 0, 'won': 0, 'win_rate': None} for s in ('T', 'CT')}}
    stats = team_hub_map_stats(profile)
    assert stats['map_win_rate'] is None and stats['round_win_rate'] is None


def test_quote_export_preserves_owner_text_and_clears_removed_entries(tmp_path):
    source, output = tmp_path / 'quotes.json', tmp_path / 'site'
    entry = {'76561198000000001': {'name': 'Player', 'zh': '一剑定乾坤。', 'en': 'One decisive shot.'}}
    source.write_text(json.dumps(entry, ensure_ascii=False), encoding='utf-8')
    export_player_quotes(source, output)
    assert json.loads((output / 'player_quotes.json').read_text()) == entry
    source.unlink()
    export_player_quotes(source, output)
    assert json.loads((output / 'player_quotes.json').read_text()) == {}


@pytest.mark.parametrize('value', [[], {'1': 'verse'}, {'1': {'zh': 42}}])
def test_invalid_quote_registry_is_reported(tmp_path, value):
    source = tmp_path / 'quotes.json'
    source.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='expected steamid'):
        export_player_quotes(source, tmp_path / 'site')


def test_asset_slots_only_index_supplied_pngs(tmp_path):
    from playbook.export import export_asset_slots
    public, output = tmp_path / 'public', tmp_path / 'site'
    (public / 'logos/teams').mkdir(parents=True)
    (public / 'players').mkdir()
    (public / 'logos/teams/falcons.png').write_bytes(b'placeholder')
    (public / 'players/76561198000000001.png').write_bytes(b'placeholder')
    (public / 'players/notes.txt').write_text('not an asset')
    export_asset_slots(public, output)
    assert json.loads((output / 'asset_slots.json').read_text()) == {
        'teams': ['falcons'], 'players': ['76561198000000001']}
