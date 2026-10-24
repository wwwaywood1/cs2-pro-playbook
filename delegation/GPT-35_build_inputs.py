"""Rebuild Cache naming inputs: .venv/bin/python delegation/GPT-35_build_inputs.py."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import polars as pl

from playbook.config import load_map
from scripts.spot_briefs import OUT, main


def build() -> None:
    main(['de_cache'])
    (OUT / 'spots_to_name_cache.csv').replace(OUT / 'de_cache_spots.csv')
    with (OUT / 'de_cache_spots.csv').open() as fh:
        rows = list(csv.DictReader(fh))
    pos = pl.read_parquet(str(ROOT / 'data/parsed/positions/*cache*.parquet'))
    centers = (pos.filter(pl.col('alive')).group_by('place')
               .agg(pl.col('x').median(), pl.col('y').median()))
    mm = load_map('de_cache')
    for side in ('T', 'CT'):
        fig, ax = plt.subplots(figsize=(18, 18), dpi=120)
        ax.imshow(plt.imread(ROOT / 'web/public/radars/de_cache.png'), extent=(0, 1024, 1024, 0))
        ax.set(xlim=(0, 1024), ylim=(1024, 0))
        ax.axis('off')
        ax.set_title(f'Cache / {side} / grey circle: smoke; orange triangle: molotov\n'
                     'Yellow: CSV short_id (leader lines to landing); cyan: parsed callout medians', fontsize=14)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
        occupied = []

        def label(x, y, value, *, spot=False):
            # Place dense labels in the closest available rectangle; exact landing stays marked.
            color = '#fff024' if spot else '#00e5ff'
            candidates = [(dx, dy) for r in range(12, 193, 18)
                          for dx, dy in ((r, r), (-r, r), (r, -r), (-r, -r),
                                         (0, r), (0, -r), (r, 0), (-r, 0))]
            for i, (dx, dy) in enumerate(candidates):
                text = ax.annotate(value, (x, y), xytext=(dx, dy), textcoords='offset pixels',
                                   color=color, fontsize=11 if spot else 8, weight='bold',
                                   ha='center', va='center', zorder=5 if spot else 2,
                                   bbox=dict(facecolor='black', alpha=.85 if spot else .55, pad=2, edgecolor='none'),
                                   arrowprops=dict(arrowstyle='-', color=color, lw=.9 if spot else .4))
                text.get_window_extent(renderer)
                text.update_bbox_position_size(renderer)
                # Annotation extents include the arrow; use only the text box for collision detection.
                box = text.get_bbox_patch().get_window_extent(renderer).expanded(1.1, 1.3)
                if (not any(box.overlaps(old) for old in occupied) and ax.bbox.contains(box.x0, box.y0)
                        and ax.bbox.contains(box.x1, box.y1)) or i == len(candidates) - 1:
                    occupied.append(box)
                    break
                text.remove()

        selected = [r for r in rows if r['side'] == side]
        for r in selected:
            x, y = float(r['radar_x']), float(r['radar_y'])
            smoke = r['type'] == 'smoke'
            ax.scatter([x], [y], s=160 if smoke else 120, marker='o' if smoke else '^',
                       c='#dedede' if smoke else '#ff7900', edgecolors='black', zorder=4)
            label(x, y, r['short_id'], spot=True)
        for place, x, y in sorted(centers.iter_rows()):
            if place not in mm.callout_region:
                continue
            rx, ry = mm.to_radar(x, y)
            label(rx, ry, place)
        fig.savefig(OUT / f'de_cache_{side}.png', bbox_inches='tight')
        plt.close(fig)
    print(f'Wrote {len(rows)} rows and both labelled radars')


if __name__ == '__main__':
    build()
