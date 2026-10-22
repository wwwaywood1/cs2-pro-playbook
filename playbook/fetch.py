"""Select and download professional demos from Hugging Face.

Source: https://huggingface.co/datasets/cs2povarchive/cs2-demos (Apache-2.0)
Layout: <event>/<hltv_match_id>-<slug>/<team1>-vs-<team2>[-m<N>]-<map>[-p<K>].dem
        e.g. iem_cologne_major_2026/2394983-vitality-vs-mouz-iem-cologne-major/vitality-vs-mouz-m1-mirage.dem

One map of one match is a "game". A game recorded in several files has -p1, -p2, ...
parts; all parts are downloaded and parsed together. A trailing
"(1)" marks a duplicate upload and is ignored.

(The CounterQuant dataset used before was taken down in October 2026.)

Downloads keep the dataset's own tree under data/raw/<source>/, so the parser finds
the match id in the folder name. Demos you get elsewhere (HLTV .rar archives) can go
straight into data/raw/ as <hltv_match_id>_<team1>-vs-<team2>-<map>.dem.

Requires `pip install huggingface_hub`. If Hugging Face is not reachable from the
machine running the pipeline, use scripts/download_batch1.py on any machine that can
reach it (it needs only huggingface_hub) and copy data/raw over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from playbook.config import RAW_DIR, load_targets
from playbook.multipart import PART_RE, ordered_paths

SOURCES = {
    "cs2povarchive": "cs2povarchive/cs2-demos",
}
KNOWN_MAPS = ("mirage", "inferno", "nuke", "dust2", "ancient", "anubis", "overpass", "train", "vertigo")
PATH_RE = re.compile(
    r"^(?P<event>[^/]+)/(?P<match_id>\d+)-[^/]+/"
    r"(?P<team1>.+?)-vs-(?P<team2>.+?)(?:-m(?P<map_no>\d+))?-(?P<map>" + "|".join(KNOWN_MAPS) + r")"
    r"(?:-p(?P<part>\d+))?(?P<dup>\(\d+\))?\.dem$"
)


@dataclass
class Game:
    event: str
    match_id: int
    team1: str
    team2: str
    map_no: int
    map: str
    parts: list[str] = field(default_factory=list)
    bytes: int = 0

    @property
    def key(self) -> str:
        return f"{self.match_id}-m{self.map_no}-{self.map}"

    @property
    def multipart(self) -> bool:
        return any(PART_RE.search(Path(p).stem) for p in self.parts)


def group_games(files: list[tuple[str, int]]) -> tuple[list[Game], list[str]]:
    """Group dataset files into games. Returns (games, paths that did not match the layout)."""
    games: dict[str, Game] = {}
    unmatched: list[str] = []
    for path, size in files:
        m = PATH_RE.match(path)
        if not m:
            if path.endswith(".dem"):
                unmatched.append(path)
            continue
        if m["dup"]:
            continue
        g = Game(m["event"], int(m["match_id"]), m["team1"], m["team2"], int(m["map_no"] or 1), m["map"])
        g = games.setdefault(g.key, g)
        g.parts.append(path)
        g.bytes += size or 0
    for g in games.values():
        g.parts = [str(p) for p in ordered_paths([Path(p) for p in g.parts])]
    return list(games.values()), unmatched


def select(games: list[Game], targets: dict) -> tuple[list[Game], list[Game]]:
    """(main batch, extra one-per-map games) according to targets.toml."""
    events = set(targets.get("events", []))
    maps = list(targets.get("maps", []))
    teams = {t.lower() for t in targets.get("teams", [])}
    both = targets.get("require_both_teams", False)

    def ok(g: Game) -> bool:
        if events and g.event not in events:
            return False
        if teams:
            hits = (g.team1 in teams) + (g.team2 in teams)
            if hits < (2 if both else 1):
                return False
        return True

    newest = lambda g: (-g.match_id, g.map_no)  # noqa: E731
    pool = sorted((g for g in games if ok(g)), key=newest)
    main = [g for g in pool if not maps or g.map in maps][: targets.get("max_demos", len(pool))]
    extra = []
    for mp in targets.get("extra_one_per_map", []):
        cand = [g for g in pool if g.map == mp]
        if cand:
            extra.append(cand[0])
    return main, extra


def list_remote(repo_id: str) -> list[tuple[str, int]]:
    from huggingface_hub import HfApi

    api = HfApi()
    return [
        (e.path, getattr(e, "size", 0) or 0)
        for e in api.list_repo_tree(repo_id, repo_type="dataset", recursive=True)
        if getattr(e, "path", "").endswith(".dem")
    ]


def fetch(dry_run: bool = False, out_dir: Path = RAW_DIR, targets_path: Path | None = None) -> list[Path]:
    targets = load_targets(targets_path)
    source = targets.get("source", "cs2povarchive")
    repo_id = SOURCES[source]
    games, unmatched = group_games(list_remote(repo_id))
    main, extra = select(games, targets)
    n_multi = sum(g.multipart for g in games)
    print(f"{repo_id}: {len(games)} games ({n_multi} multipart), {len(unmatched)} unrecognised files")
    for label, batch in (("batch", main), ("one per extra map", extra)):
        gb = sum(g.bytes for g in batch) / 1e9
        print(f"{label}: {len(batch)} games, {gb:.1f} GB")
        for g in batch:
            print(f"  {g.match_id} m{g.map_no} {g.map:<8} {g.team1} vs {g.team2}  [{g.event}]")
    if dry_run:
        return []

    from huggingface_hub import hf_hub_download

    dest_root = out_dir / source
    done: list[Path] = []
    todo = list(dict.fromkeys(p for g in main + extra for p in g.parts))
    for i, path in enumerate(todo, 1):
        dest = dest_root / path
        if dest.exists():
            done.append(dest)
            continue
        print(f"[{i}/{len(todo)}] {path}")
        done.append(Path(hf_hub_download(repo_id, path, repo_type="dataset", local_dir=dest_root)))
    return done
