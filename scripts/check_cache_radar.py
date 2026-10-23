"""Reproduce Cache calibration from stored live positions (no demo reparse).

    .venv/bin/python scripts/check_cache_radar.py

Writes the radar overlay, the map-config inventory, and early T/CT / plant-site
supporting evidence under delegation/inputs. Requires the local awpy radar.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import polars as pl
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from playbook.config import load_map
from scripts.make_map_briefs import table


def main() -> None:
    mm = load_map('de_cache')
    parsed = ROOT / 'data/parsed'
    files = sorted(f for f in (parsed / 'matches').glob('*.parquet')
                   if pl.read_parquet(f)['map'][0] == mm.name)
    if not files:
        raise SystemExit('No parsed Cache demos')
    data = {k: [pl.read_parquet(parsed / k / f.name) for f in files]
            for k in ('positions', 'plants')}
    pos = pl.concat(data['positions']).filter(pl.col('alive'))
    plants = pl.concat(data['plants'])
    inventory = table(mm.name, data)
    inputs = ROOT / 'delegation/inputs'
    inputs.mkdir(parents=True, exist_ok=True)
    inventory.write_csv(inputs / 'de_cache_callouts.csv')
    early = pos.filter(pl.col('t_s') <= 20).group_by('place').agg(
        t_first_20s=(pl.col('side') == 'T').sum())
    inventory.join(early, left_on='callout', right_on='place').write_csv(
        inputs / 'de_cache_callout_evidence.csv')
    base = Image.open(Path.home() / '.awpy/2000933/radars/de_cache.png').convert('RGBA')
    # The nonblack overview footprint is supporting evidence, not a nav mesh:
    # walls, upper floors, props and overhanging edges are included in it.
    footprint = Image.fromarray((np.array(base.convert('RGB')).max(axis=2) > 15).astype('uint8') * 255)
    footprint = np.array(footprint.filter(ImageFilter.MaxFilter(13))) > 0
    layer = Image.new('RGBA', base.size)
    draw = ImageDraw.Draw(layer)
    pixels = np.array([mm.to_radar(x, y) for x, y in pos.select('x', 'y').iter_rows()])
    in_bounds = ((pixels >= 0) & (pixels < 1024)).all(axis=1)
    rounded = np.clip(np.rint(pixels), 0, 1023).astype(int)
    on_footprint = in_bounds & footprint[rounded[:, 1], rounded[:, 0]]
    for (x, y), side in zip(pixels, pos['side']):
        color = (255, 165, 45, 28) if side == 'T' else (40, 160, 255, 28)
        draw.ellipse((x-1, y-1, x+1, y+1), fill=color)
    base = Image.alpha_composite(base, layer)
    draw = ImageDraw.Draw(base)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
    except OSError:
        font = ImageFont.load_default()
    for x, y in plants.select('x', 'y').iter_rows():
        x, y = mm.to_radar(x, y)
        draw.ellipse((x-3, y-3, x+3, y+3), outline='magenta', width=1)
    for row in inventory.iter_rows(named=True):
        draw.text((row['radar_x']+3, row['radar_y']-7), row['callout'],
                  font=font, fill='white', stroke_width=2, stroke_fill='black')
    draw.rectangle((0, 0, 1024, 38), fill='#0b1116')
    draw.text((10, 5), f'Cache: {len(files)} demos | {pos.height:,} live player-seconds | T orange / CT blue / plants magenta', font=font, fill='white')
    draw.text((10, 21), f'pos_x={mm.radar["pos_x"]}, pos_y={mm.radar["pos_y"]}, scale={mm.radar["scale"]}', font=font, fill='white')
    base.convert('RGB').save(inputs / 'cache_radar_check.png')
    result = {'radar': mm.radar, 'demos': pos.group_by('demo_id').len().sort('demo_id').to_dicts(),
              'live_samples': pos.height, 'inside_image': int(in_bounds.sum()),
              'within_6px_of_overview_footprint': int(on_footprint.sum()),
              'plants': plants.group_by('site').agg(pl.len(), pl.col('x').median(), pl.col('y').median()).sort('site').to_dicts(),
              'places': inventory.height}
    (inputs / 'cache_radar_check.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
