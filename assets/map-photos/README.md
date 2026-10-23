# Owner-supplied map screenshots

Place your own in-game screenshots here, named `<map>.png`, `.jpg`, `.jpeg`, or `.webp`.
Use landscape shots at least 1920 px wide, with the landmark near the centre (the
build centre-crops to a 4:5 portrait). Hide HUD and weapon with `cl_drawhud 0`
and `r_drawviewmodel 0` before capturing.

| Filename stem | Landmark to capture |
| --- | --- |
| dust2 | A doors / mid |
| mirage | Arches / palace tower |
| ancient | Ruins temple |
| anubis | Canal / jackal statue |
| inferno | Church tower |
| nuke | Cooling towers |
| cache | Red building / silo |

Run `.venv/bin/python scripts/build_map_backgrounds.py` from the repository root,
or add `--map mirage` to rebuild one map. Outputs are 480×600 RGB WebP files at
quality 85 in `web/public/map-bg/`, plus a manifest used by the frontend. Rebuild
the frontend after generating photos for a static deployment. Missing sources
are listed; their cards retain radar/biome glow (Cache retains its stripe grid).
The script never downloads images. Only supply images you have permission to use.
