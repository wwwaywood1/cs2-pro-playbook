#!/usr/bin/env python3
"""Move imported HLTV download archives (.rar/.zip/...) off the internal disk.

    python scripts/archive_downloads.py            # dry run: list what would move
    python scripts/archive_downloads.py --apply    # copy, verify (SHA-256), then delete the original

After `scripts/import_hltv.py` has extracted an archive into ``data/raw/hltv/<stem>/``,
the archive itself is only a backup. This script moves such archives to the
directory configured in ``config/storage.toml`` (``[archive] dir``), e.g. an external
SSD. Demo identities come from the extracted folder names, never from the archive
files, so moving archives does not change any parsed data.

Safety: every file is copied to ``<name>.part``, flushed, re-read and compared by
SHA-256 against the source before the source is deleted. Interrupted runs resume.
A manifest ``.archived.jsonl`` in the destination records name, size and hash.
If the destination volume is not mounted the script does nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVES = (".rar", ".zip", ".gz", ".bz2", ".7z")
CHUNK = 8 << 20


def load_dest(config: Path) -> Path | None:
    if not config.exists():
        return None
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    value = (data.get("archive") or {}).get("dir")
    return Path(value).expanduser() if value else None


def volume_root(path: Path) -> Path:
    """`/Volumes/<name>` for external volumes, else the path's first existing parent."""
    parts = path.parts
    if len(parts) >= 3 and parts[1] == "Volumes":
        return Path(*parts[:3])
    return Path(path.anchor or ".")


def candidates(src: Path, imported_only: bool) -> list[Path]:
    """Archives that import_hltv.py already handled: extracted folder exists or the
    archive is listed in ``.import_hltv_archives.json`` (e.g. all maps were duplicates)."""
    registry = src / ".import_hltv_archives.json"
    processed = set(json.loads(registry.read_text(encoding="utf-8"))) if registry.exists() else set()
    out = []
    for p in sorted(src.iterdir()):
        if not p.is_file() or p.name.startswith(("._", ".")):
            continue
        if p.suffix.lower() not in ARCHIVES:
            continue
        if imported_only and not (src / p.stem).is_dir() and p.name not in processed:
            continue
        out.append(p)
    return out


def sha256_copy(src: Path, dst: Path) -> str:
    h = hashlib.sha256()
    with src.open("rb") as fi, dst.open("wb") as fo:
        while chunk := fi.read(CHUNK):
            h.update(chunk)
            fo.write(chunk)
        fo.flush()
        os.fsync(fo.fileno())
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def move_one(src: Path, dest_dir: Path, manifest: Path) -> tuple[str, int]:
    final = dest_dir / src.name
    size = src.stat().st_size
    if final.exists() and final.stat().st_size == size:
        digest = sha256_file(src)
        if sha256_file(final) != digest:
            raise RuntimeError(f"existing copy differs: {final}")
        status = "verified-existing"
    else:
        part = dest_dir / (src.name + ".part")
        digest = sha256_copy(src, part)
        if part.stat().st_size != size or sha256_file(part) != digest:
            raise RuntimeError(f"verification failed for {src.name}")
        part.replace(final)
        status = "copied"
    with manifest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"name": src.name, "size": size, "sha256": digest,
                             "moved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}) + "\n")
    src.unlink()
    return status, size


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ROOT / "data" / "raw" / "hltv")
    ap.add_argument("--dest", type=Path, default=None, help="override [archive] dir from config/storage.toml")
    ap.add_argument("--config", type=Path, default=ROOT / "config" / "storage.toml")
    ap.add_argument("--all", action="store_true", help="also move archives that have no extracted folder")
    ap.add_argument("--apply", action="store_true", help="actually move (default: dry run)")
    args = ap.parse_args(argv)

    dest = args.dest or load_dest(args.config)
    if dest is None:
        print("No archive destination configured (config/storage.toml [archive] dir); nothing to do.")
        return 0
    if not volume_root(dest).exists():
        print(f"Archive volume not mounted ({volume_root(dest)}); skipping.")
        return 0
    if not args.src.is_dir():
        print(f"No source directory {args.src}; nothing to do.")
        return 0
    files = candidates(args.src, imported_only=not args.all)
    total = sum(p.stat().st_size for p in files)
    print(f"{len(files)} archive(s), {total / 1e9:.1f} GB -> {dest}")
    if not args.apply:
        for p in files[:20]:
            print(f"  would move {p.name} ({p.stat().st_size / 1e6:.0f} MB)")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    manifest = dest / ".archived.jsonl"
    done = moved_bytes = 0
    failures = []
    started = time.time()
    for i, p in enumerate(files, 1):
        try:
            status, size = move_one(p, dest, manifest)
            done += 1
            moved_bytes += size
            rate = moved_bytes / 1e6 / max(time.time() - started, 1e-6)
            print(f"[{i}/{len(files)}] {status} {p.name} ({size / 1e6:.0f} MB, {rate:.0f} MB/s avg)", flush=True)
        except Exception as exc:  # keep going; the original stays in place
            failures.append((p.name, str(exc)))
            print(f"[{i}/{len(files)}] FAILED {p.name}: {exc}", flush=True)
    print(f"done: {done} moved ({moved_bytes / 1e9:.1f} GB), {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
