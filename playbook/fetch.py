"""Select and download professional demos from the CounterQuant dataset on Hugging Face.

Dataset: https://huggingface.co/datasets/KEDevO/CounterQuant-CS2-Demos (CC BY 4.0)
Layout:  data/{year}/{tier}/{hltv_match_id}/{team1}-vs-{team2}-{map}.dem

Only the files that match ``config/targets.toml`` are downloaded, one by one, so a
first run stays small. Requires ``pip install huggingface_hub``.

Demos you download by hand (e.g. from HLTV, which ships .rar archives) can skip this
step: extract the .dem files into ``data/raw/`` and run ``parse`` directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from playbook.config import RAW_DIR, load_targets

REPO_ID = "KEDevO/CounterQuant-CS2-Demos"
PATH_RE = re.compile(
    r"^data/(?P<year>\d{4})/(?P<tier>[^/]+)/(?P<match_id>[^/]+)/(?P<stem>.+)\.dem$",
    re.IGNORECASE,
)


@dataclass
class RemoteDemo:
    path: str
    year: int
    tier: str
    match_id: str
    team1: str
    team2: str
    map: str

    @property
    def local_name(self) -> str:
        return f"{self.match_id}_{Path(self.path).stem}.dem"


def parse_remote_path(path: str, known_maps: list[str]) -> RemoteDemo | None:
    """Split a dataset path into its parts. Returns None for anything that isn't a demo."""
    m = PATH_RE.match(path)
    if not m:
        return None
    stem = m["stem"].lower()
    # The map is the last dash-separated token(s); match against known map names so
    # multi-word maps (none today, but e.g. "dust2") are handled.
    map_name = next((mp for mp in sorted(known_maps, key=len, reverse=True) if stem.endswith("-" + mp)), None)
    if map_name is None:
        map_name = stem.rsplit("-", 1)[-1]
    teams = stem[: -(len(map_name) + 1)]
    if "-vs-" not in teams:
        return None
    team1, team2 = teams.split("-vs-", 1)
    return RemoteDemo(path, int(m["year"]), m["tier"], m["match_id"], team1, team2, map_name)


def select(remote: list[RemoteDemo], targets: dict) -> list[RemoteDemo]:
    years = set(targets.get("years", []))
    tiers = set(targets.get("tiers", []))
    maps = set(targets.get("maps", []))
    teams = {t.lower() for t in targets.get("teams", [])}
    both = targets.get("require_both_teams", False)
    out = []
    for d in remote:
        if years and d.year not in years:
            continue
        if tiers and d.tier not in tiers:
            continue
        if maps and d.map not in maps:
            continue
        if teams:
            hits = (d.team1 in teams) + (d.team2 in teams)
            if hits < (2 if both else 1):
                continue
        out.append(d)
    out.sort(key=lambda d: (d.year, d.match_id), reverse=True)  # newest first
    return out[: targets.get("max_demos", len(out))]


def list_remote(years: list[int] | None = None) -> list[str]:
    from huggingface_hub import HfApi

    api = HfApi()
    if not years:
        return api.list_repo_files(REPO_ID, repo_type="dataset")
    files: list[str] = []
    for year in years:
        for entry in api.list_repo_tree(REPO_ID, repo_type="dataset", path_in_repo=f"data/{year}", recursive=True):
            if getattr(entry, "path", "").endswith(".dem"):
                files.append(entry.path)
    return files


def fetch(dry_run: bool = False, out_dir: Path = RAW_DIR, targets_path: Path | None = None) -> list[Path]:
    targets = load_targets(targets_path)
    known_maps = targets.get("maps", []) + ["mirage", "inferno", "nuke", "ancient", "anubis", "dust2", "train", "overpass", "vertigo"]
    remote = [d for p in list_remote(targets.get("years")) if (d := parse_remote_path(p, known_maps))]
    chosen = select(remote, targets)
    print(f"{len(remote)} demos in the dataset for the selected years; {len(chosen)} match targets.toml")
    for d in chosen:
        print(f"  {d.year} {d.tier} {d.match_id:>9}  {d.team1} vs {d.team2}  [{d.map}]")
    if dry_run:
        return []

    from huggingface_hub import hf_hub_download

    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / ".hf_staging"
    done: list[Path] = []
    for i, d in enumerate(chosen, 1):
        dest = out_dir / d.local_name
        if dest.exists():
            done.append(dest)
            continue
        print(f"[{i}/{len(chosen)}] downloading {d.path}")
        # Download into a staging dir (no second copy in the global HF cache), then
        # move it to a flat, self-describing name: <match_id>_<team1>-vs-<team2>-<map>.dem
        got = Path(hf_hub_download(REPO_ID, d.path, repo_type="dataset", local_dir=staging))
        got.replace(dest)
        done.append(dest)
    return done
