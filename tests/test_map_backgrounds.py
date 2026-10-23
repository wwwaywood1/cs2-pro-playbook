import json

import numpy as np
import pytest
from PIL import Image

from scripts.build_map_backgrounds import MAP_COLORS, build_backgrounds, darkroom


@pytest.mark.parametrize("map_id", MAP_COLORS)
def test_darkroom_synthetic_image(tmp_path, map_id):
    source_dir, output_dir = tmp_path / "photos", tmp_path / "backgrounds"
    source_dir.mkdir()
    # Wide synthetic shot: the white centre must survive the portrait crop.
    pixels = np.zeros((240, 640, 3), dtype=np.uint8)
    pixels[:, 224:416] = 255
    source = source_dir / f"{map_id}.png"
    Image.fromarray(pixels).save(source)
    image = darkroom(source, map_id)
    assert image.size == (480, 600)
    assert image.mode == "RGB"
    assert 20 < np.asarray(image).mean() < 85
    assert np.asarray(image).max() <= 120
    assert build_backgrounds(source_dir, output_dir, map_id) == []
    destination = output_dir / f"{map_id}.webp"
    assert destination.is_file()
    with Image.open(destination) as result:
        assert result.size == (480, 600)
        assert result.mode == "RGB"
        assert np.asarray(result).max() <= 125
    before = destination.read_bytes()
    build_backgrounds(source_dir, output_dir, map_id)
    assert destination.read_bytes() == before
    assert json.loads((output_dir / "manifest.json").read_text()) == [map_id]


def test_missing_sources_and_single_map_manifest(tmp_path, capsys):
    source_dir, output_dir = tmp_path / "photos", tmp_path / "backgrounds"
    source_dir.mkdir()
    Image.new("RGB", (800, 450), "white").save(source_dir / "mirage.jpg")
    missing = build_backgrounds(source_dir, output_dir)
    assert missing == [name for name in MAP_COLORS if name != "mirage"]
    assert "Missing source photos: dust2" in capsys.readouterr().out
    original = (output_dir / "mirage.webp").read_bytes()
    Image.new("RGBA", (800, 450), (64, 128, 255, 255)).save(source_dir / "nuke.png")
    build_backgrounds(source_dir, output_dir, "nuke")
    assert json.loads((output_dir / "manifest.json").read_text()) == ["mirage", "nuke"]
    assert (output_dir / "mirage.webp").read_bytes() == original
