"""Verify Cache names and export copies; run after export and data synchronization."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playbook.config import load_spot_names


def verify() -> dict:
    inputs = ROOT / 'delegation/inputs/spots'
    with (inputs / 'de_cache_spots.csv').open() as fh:
        rows = list(csv.DictReader(fh))
    configured = load_spot_names('de_cache')
    by_id = {r['spot_id']: r for r in rows}
    assert len(configured) == len(by_id) == len(rows) == 46
    assert {n['id'] for n in configured} == set(by_id)
    for n in configured:
        r = by_id[n['id']]
        assert (n['side'], n['type'], n['x'], n['y']) == (
            r['side'], r['type'], float(r['x']), float(r['y']))
        assert n['radius'] == (200 if n['type'] == 'smoke' else 150)
        assert n['en'] and n['zh'] and n['confidence'] in ('high', 'medium', 'low')
    names = {n['id']: {k: n[k] for k in ('en', 'zh')} for n in configured}
    site = ROOT / 'data/site'
    tactics = json.loads((site / 'de_cache/tactics.json').read_text())
    spots = [s for s in tactics['spots'] if s['type'] in ('smoke', 'molotov')]
    assert len(spots) == 46
    assert {s['spot_id'] for s in spots} == set(names)
    for spot in spots:
        assert spot['name'] == names[spot['spot_id']]
    recipes = tactics['recipes']
    assert len(recipes) == 4
    references = [s for r in recipes for s in r['core'] + r['options']]
    for spot in references:
        assert spot['name'] == names[spot['spot_id']]
    lineups = json.loads((site / 'de_cache/lineups.json').read_text())
    named = []
    for lineup in lineups:
        candidates = [n for n in configured if n['side'] == lineup['side'] and n['type'] == lineup['type']
                      and (n['x'] - lineup['land']['x'])**2 + (n['y'] - lineup['land']['y'])**2 <= n['radius']**2]
        if not candidates:
            assert not lineup.get('name')
            continue
        closest = min(candidates, key=lambda n: (n['x'] - lineup['land']['x'])**2 + (n['y'] - lineup['land']['y'])**2)
        assert lineup['name'] == names[closest['id']]
        named.append(lineup)
    copies = {}
    for destination in ('site-preview/data', 'web/public/data', 'web/dist/data'):
        mismatches = []
        files = [p for p in site.rglob('*') if p.is_file()]
        for src in files:
            dst = ROOT / destination / src.relative_to(site)
            if not dst.is_file() or hashlib.sha256(src.read_bytes()).digest() != hashlib.sha256(dst.read_bytes()).digest():
                mismatches.append(str(src.relative_to(site)))
        assert not mismatches, (destination, mismatches[:10])
        copies[destination] = {'source_files_checked': len(files), 'mismatches': 0}
    assert (ROOT / 'web/dist/index.html').read_bytes() == (ROOT / 'site-preview/index.html').read_bytes()
    assets = [p for p in (ROOT / 'web/dist/assets').rglob('*') if p.is_file()]
    for src in assets:
        assert src.read_bytes() == (ROOT / 'site-preview/assets' / src.relative_to(ROOT / 'web/dist/assets')).read_bytes()
    result = {
        'spots': len(configured), 'confidence': dict(Counter(n['confidence'] for n in configured)),
        'recipes': len(recipes), 'named_recipe_references': len(references),
        'lineups': len(lineups), 'named_lineups': len(named),
        'lineup_names_by_side_type': dict(Counter(f"{l['side']}/{l['type']}" for l in named)),
        'data_copies': copies,
        'preview_html_matches_build': True, 'build_assets_checked': len(assets),
    }
    (inputs / 'de_cache_verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    verify()
