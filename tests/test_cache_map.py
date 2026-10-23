"""Cache callouts and calibration are shared by all exported map surfaces."""
import json

import pytest

from playbook.config import ROOT, load_map
from scripts.check_map_config import check


def test_cache_inventory_regions_and_translations():
    mm = load_map('de_cache')
    assert not check('de_cache')
    assert len(mm.callout_region) == 47
    assert mm.region('BombsiteA') == 'A_SITE'
    assert mm.region('BombsiteB') == 'B_SITE'
    assert mm.lane('Garage') == 'MID'
    assert mm.lane('Highway') == 'MID'
    assert mm.lane('Toxic') == 'A'
    assert mm.lane('Heaven') == 'B'
    for lang in ('zh', 'en'):
        labels = json.loads((ROOT / f'web/src/i18n/{lang}.json').read_text())
        assert set(labels['callout']['de_cache']) == set(mm.callout_region)


@pytest.mark.parametrize('world, pixel', [
    ((-2000, 3250), (0, 0)),
    ((3632, -2382), (1024, 1024)),
    ((-86.03125, 1896.633056640625), (347.9943, 246.0667)),
    ((-133.965087890625, -1495.158935546875), (339.2791, 862.7562)),
])
def test_cache_radar_corners_and_observed_plant_medians(world, pixel):
    assert load_map('de_cache').to_radar(*world) == pytest.approx(pixel, abs=.0001)
