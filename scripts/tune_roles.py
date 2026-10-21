#!/usr/bin/env python3
"""Explore lurker rules without changing production hints.

Usage: python scripts/tune_roles.py data/site --labels validation/pro_roles.csv
Scores use one equally weighted player-map row. Grid selection maximizes in-sample
F1, then precision, recall and simplicity; these are not held-out estimates.
Only sourced labels on the CSV's listed maps are evaluated. Missing features fail
an enabled condition (disabled conditions do not require the feature).
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    distance_min: float | None = None
    lurk_min: float | None = None
    entry_max: float | None = None
    forward_max: float | None = None
    anchor_min: float | None = None

    def predict(self, features):
        limits = (self.distance_min, self.lurk_min, self.entry_max, self.forward_max, self.anchor_min)
        for index, (value, limit) in enumerate(zip(features, limits)):
            if limit is None:
                continue
            if value is None or (value > limit if index in (2, 3) else value < limit):
                return False
        return True

    def __str__(self):
        names = ('T.avg_dist_to_team_30s >=', 'T.lurk_share >=', 'T.first_into_site_rate <=',
                 'CT.forward_share <=', 'max CT A/B lane share >=')
        return ' AND '.join(f'{name} {value:g}' for name, value in zip(names, vars(self).values())
                            if value is not None) or 'all players'


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def features(player):
    t, ct = player.get('T') or {}, player.get('CT') or {}
    lanes = ct.get('lanes_15s') or []
    # A/B concentration is a CT anchor proxy, not a ground-truth lurker label.
    shares = [number(l.get('share')) for l in lanes if l.get('value') in ('A', 'B')]
    valid = [s for s in shares if s is not None]
    anchor = max(valid) if valid else (0.0 if lanes and all(number(l.get('share')) is not None for l in lanes) else None)
    return (number(t.get('avg_dist_to_team_30s')), number(t.get('lurk_share')),
            number(t.get('first_into_site_rate')), number(ct.get('forward_share')), anchor)


def load_rows(site: Path, labels: Path):
    truth = {}
    with labels.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        required = {'steamid', 'maps', 'role_primary', 'role_secondary', 'sources'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f'CSV is missing columns: {sorted(required - set(reader.fieldnames or []))}')
        for label in reader:
            roles = set(re.split(r'[,;/\s]+', (label['role_primary'] + ' ' + label['role_secondary']).strip().lower())) - {''}
            if not label['sources'].strip() or not roles or not label['steamid'].strip():
                continue
            for map_name in label['maps'].split():
                key = (label['steamid'].strip(), map_name if map_name.startswith('de_') else 'de_' + map_name)
                value = 'lurker' in roles
                if key in truth and truth[key] != value:
                    raise ValueError(f'Conflicting labels for {key}')
                truth[key] = value
    rows, seen, skipped = [], set(), 0
    files = sorted(site.glob('*/players.json'))
    if not files:
        raise ValueError(f'No <map>/players.json files under {site}')
    for path in files:
        for player in json.loads(path.read_text(encoding='utf-8')):
            key = (str(player['steamid']), path.parent.name)
            if key in seen:
                raise ValueError(f'Duplicate player-map row: {key}')
            seen.add(key)
            if key not in truth:
                skipped += 1
                continue
            rows.append({'steamid': key[0], 'map': key[1], 'player': player.get('name') or key[0],
                         'truth': truth[key], 'features': features(player),
                         'baseline': any(h.get('role') == 'lurker' for h in player.get('role_hints', []))})
    if not rows:
        raise ValueError('No exported player-map rows match sourced CSV labels')
    return rows, skipped


def metrics(truth, predictions):
    tp = sum(y and p for y, p in zip(truth, predictions))
    fp = sum(not y and p for y, p in zip(truth, predictions))
    fn = sum(y and not p for y, p in zip(truth, predictions))
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {'n': len(truth), 'tp': tp, 'fp': fp, 'fn': fn, 'precision': precision, 'recall': recall,
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0}


def grid_rules():
    for values in itertools.product((None, 600., 900., 1200., 1500.), (None, .1, .2, .3, .4),
                                    (None, .1, .2, .3), (None, .1, .25, .5), (None, .5, .6, .75)):
        if any(v is not None for v in values):
            yield Rule(*values)


def search(rows, rules=None):
    truth = [r['truth'] for r in rows]
    scored = []
    for rule in grid_rules() if rules is None else rules:
        score = metrics(truth, [rule.predict(r['features']) for r in rows])
        scored.append((rule, score))
    return sorted(scored, key=lambda item: (-item[1]['f1'], -(item[1]['precision'] or 0),
                                          -(item[1]['recall'] or 0),
                                          sum(v is not None for v in vars(item[0]).values()), str(item[0])))


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])


def pct(value):
    return '—' if value is None else f'{value:.1%}'


def report(rows, ranked, skipped, top=10):
    best = ranked[0][0]
    lines = [f'Evaluated {len(rows)} labeled player-map rows; skipped {skipped} unlabeled/unsourced rows.',
             f'Grid: {len(ranked)} rules. Ranking: F1, precision, recall, fewer conditions, rule text.',
             'In-sample tuning scores; validate on held-out players/maps before adopting a rule.',
             'CT.lanes_15s is represented by the maximum A/B share. All enabled conditions are ANDed.',
             'Missing features fail enabled conditions. — means an undefined denominator.', '',
             table(['Rule', 'Precision', 'Recall', 'F1'],
                   [(str(rule), pct(s['precision']), pct(s['recall']), pct(s['f1'])) for rule, s in ranked[:top]]), '',
             f'Selected rule: {best}', '']
    groups = [('All player-map rows', rows)]
    for field in ('map', 'steamid'):
        grouped = defaultdict(list)
        for row in rows:
            grouped[row[field]].append(row)
        groups.extend((f'{field}: {key}', group) for key, group in sorted(grouped.items()))
    scores = []
    for name, group in groups:
        for model in ('exported baseline', 'selected grid rule'):
            s = metrics([r['truth'] for r in group],
                        [r['baseline'] if model == 'exported baseline' else best.predict(r['features']) for r in group])
            scores.append((name, model, s['n'], s['tp'], s['fp'], s['fn'], pct(s['precision']), pct(s['recall'])))
    lines.append(table(['Group', 'Rule', 'Rows', 'TP', 'FP', 'FN', 'Precision', 'Recall'], scores))
    lines.extend(['', table(['Player', 'Steam ID', 'Map', 'Lurker label', 'Baseline', 'Selected'],
                           [(r['player'], r['steamid'], r['map'], r['truth'], r['baseline'], best.predict(r['features']))
                            for r in rows])])
    return '\n\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('site', type=Path, help='Export root containing <map>/players.json')
    parser.add_argument('--labels', type=Path, default=Path(__file__).resolve().parents[1] / 'validation/pro_roles.csv')
    parser.add_argument('--top', type=int, default=10, help='Number of grid rules to show')
    parser.add_argument('--output', type=Path, help='Write Markdown report instead of stdout')
    args = parser.parse_args()
    if args.top < 1:
        parser.error('--top must be positive')
    try:
        rows, skipped = load_rows(args.site, args.labels)
        result = report(rows, search(rows), skipped, args.top)
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    else:
        print(result, end='')


if __name__ == '__main__':
    main()
