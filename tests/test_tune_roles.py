"""Role tuning uses sourced identities and reports player-map confusion counts."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.tune_roles import Rule, features, grid_rules, load_rows, metrics, report, search


def test_feature_rules_and_missing_values():
    player = {'T': {'avg_dist_to_team_30s': 900, 'lurk_share': .2, 'first_into_site_rate': .1},
              'CT': {'forward_share': .25, 'lanes_15s': [{'value': 'A', 'share': .6}, {'value': 'B', 'share': .3}]}}
    f = features(player)
    assert f == (900., .2, .1, .25, .6)
    assert Rule(900., .2, .1, .25, .6).predict(f)
    for rule in (Rule(901), Rule(lurk_min=.21), Rule(entry_max=.09), Rule(forward_max=.24), Rule(anchor_min=.61)):
        assert not rule.predict(f)
    assert features({}) == (None,) * 5
    assert features({'T': {'lurk_share': float('nan')}, 'CT': {'forward_share': float('inf')}}) == (None,) * 5
    assert not Rule(lurk_min=.1).predict(features({}))
    assert Rule(lurk_min=.1).predict((None, .2, None, None, None))
    assert features({'CT': {'lanes_15s': [{'value': 'MID', 'share': 1}]}})[4] == 0


def test_metrics_and_search():
    score = metrics([True, True, False, False], [True, False, True, False])
    assert (score['tp'], score['fp'], score['fn'], score['precision'], score['recall']) == (1, 1, 1, .5, .5)
    assert metrics([False], [False])['precision'] is None
    assert metrics([False], [True])['recall'] is None
    rows = [{'truth': True, 'features': (1000, .3, .1, .1, .7)},
            {'truth': False, 'features': (500, .05, .5, .6, .2)}]
    ranked = search(rows)
    assert len(ranked) == 1599
    assert ranked[0][1]['f1'] == 1
    assert ranked == search(rows)
    assert any(all(v is not None for v in vars(rule).values()) for rule in grid_rules())


def fixture_files(tmp_path):
    site = tmp_path / 'site'
    labels = tmp_path / 'roles.csv'
    with labels.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['steamid', 'maps', 'role_primary', 'role_secondary', 'sources'])
        w.writerows([['1', 'mirage inferno', 'anchor', 'lurker', 'https://example.com/1'],
                     ['2', 'mirage', 'rifler', '', 'https://example.com/2'],
                     ['3', 'mirage', 'lurker', '', '']])
    for map_name in ('de_mirage', 'de_inferno'):
        path = site / map_name / 'players.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps([{'steamid': str(i), 'name': f'p{i}',
                                    'T': {'lurk_share': .4 if i == 1 else .05}, 'CT': {},
                                    'role_hints': [{'role': 'lurker'}] if i == 2 else []}
                                   for i in (1, 2, 3, 4)]))
    return site, labels


def test_loading_report_and_cli(tmp_path):
    site, labels = fixture_files(tmp_path)
    rows, skipped = load_rows(site, labels)
    assert len(rows) == 3 and skipped == 5
    assert sum(r['truth'] for r in rows) == 2
    text = report(rows, search(rows), skipped)
    assert 'de_mirage' in text and 'de_inferno' in text and 'steamid: 1' in text
    assert '| Precision | Recall |' in text and 'In-sample' in text
    output = tmp_path / 'report.md'
    run = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/tune_roles.py'),
                          str(site), '--labels', str(labels), '--output', str(output)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert output.read_text() == text


def test_no_data_and_duplicate_rows_are_errors(tmp_path):
    site, labels = fixture_files(tmp_path)
    with pytest.raises(ValueError, match='No <map>'):
        load_rows(tmp_path / 'missing', labels)
    path = site / 'de_mirage/players.json'
    players = json.loads(path.read_text())
    path.write_text(json.dumps(players + players[:1]))
    with pytest.raises(ValueError, match='Duplicate'):
        load_rows(site, labels)
