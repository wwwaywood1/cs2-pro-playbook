#!/usr/bin/env python3
"""Build tactical WebP backgrounds from owner-supplied screenshots; never uses the network."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MAP_COLORS = {
    "dust2": "#D99B43", "mirage": "#E15F41", "ancient": "#22C55E",
    "anubis": "#EAB308", "inferno": "#F97316", "nuke": "#38BDF8",
    "cache": "#94A3B8",
}
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def rgb(hex_color: str) -> np.ndarray:
    return np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32)


def darkroom(source: Path, map_id: str) -> Image.Image:
    with Image.open(source) as original:
        image = ImageOps.fit(ImageOps.exif_transpose(original).convert("RGB"), (480, 600),
                             method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    # Natural colours: no tint or colour overlay, only a light contrast/brightness pass
    # so white card text stays readable on top.
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = image.filter(ImageFilter.SHARPEN)
    return ImageEnhance.Brightness(image).enhance(0.88)


def build_backgrounds(source_dir: Path, output_dir: Path, map_id: str | None = None) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in ([map_id] if map_id else MAP_COLORS):
        source = next((source_dir / f"{name}{ext}" for ext in EXTENSIONS
                       if (source_dir / f"{name}{ext}").is_file()), None)
        if source is None:
            missing.append(name)
            continue
        destination = output_dir / f"{name}.webp"
        darkroom(source, name).save(destination, "WEBP", quality=85)
        print(f"Built {destination}")
    # The frontend probes only declared files, avoiding expected 404 console errors.
    # Include existing outputs so --map never removes other maps from the manifest.
    manifest = json.dumps([name for name in MAP_COLORS if (output_dir / f"{name}.webp").is_file()], indent=2) + "\n"
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists() or manifest_path.read_text() != manifest:
        manifest_path.write_text(manifest)
    print("Missing source photos: " + (", ".join(missing) if missing else "none"))
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", choices=MAP_COLORS, help="rebuild one map only")
    args = parser.parse_args()
    try:
        build_backgrounds(ROOT / "assets/map-photos", ROOT / "web/public/map-bg", args.map)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Background build failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
