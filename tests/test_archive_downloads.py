import json
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "archive_downloads", Path(__file__).resolve().parents[1] / "scripts" / "archive_downloads.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _setup(tmp_path):
    src = tmp_path / "hltv"
    src.mkdir()
    (src / "a-bo3-x.rar").write_bytes(b"A" * 1000)
    (src / "a-bo3-x").mkdir()                      # extracted -> imported
    (src / "b-bo3-y.zip").write_bytes(b"B" * 10)   # listed in registry (all duplicates)
    (src / ".import_hltv_archives.json").write_text(json.dumps(["b-bo3-y.zip"]))
    (src / "c-bo3-z.rar").write_bytes(b"C" * 10)   # not imported yet -> stays
    (src / "._a-bo3-x.rar").write_bytes(b"\0" * 4)  # AppleDouble sidecar -> ignored
    return src


def test_dry_run_lists_only_imported(tmp_path, capsys):
    src = _setup(tmp_path)
    dest = tmp_path / "dest"
    assert mod.main(["--src", str(src), "--dest", str(dest)]) == 0
    out = capsys.readouterr().out
    assert "2 archive(s)" in out and "c-bo3-z" not in out
    assert not dest.exists()


def test_apply_moves_and_verifies(tmp_path):
    src = _setup(tmp_path)
    dest = tmp_path / "dest"
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert (dest / "a-bo3-x.rar").read_bytes() == b"A" * 1000
    assert (dest / "b-bo3-y.zip").exists()
    assert not (src / "a-bo3-x.rar").exists() and not (src / "b-bo3-y.zip").exists()
    assert (src / "c-bo3-z.rar").exists() and (src / "._a-bo3-x.rar").exists()
    lines = [json.loads(l) for l in (dest / ".archived.jsonl").read_text().splitlines()]
    assert {l["name"] for l in lines} == {"a-bo3-x.rar", "b-bo3-y.zip"}
    assert not list(dest.glob("*.part"))


def test_resume_with_existing_identical_copy(tmp_path):
    src = _setup(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a-bo3-x.rar").write_bytes(b"A" * 1000)
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 0
    assert not (src / "a-bo3-x.rar").exists()


def test_mismatched_existing_copy_keeps_source(tmp_path):
    src = _setup(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    (dest / "a-bo3-x.rar").write_bytes(b"Z" * 1000)   # same size, different bytes
    assert mod.main(["--src", str(src), "--dest", str(dest), "--apply"]) == 1
    assert (src / "a-bo3-x.rar").exists()


def test_unmounted_volume_is_skipped(tmp_path, capsys):
    src = _setup(tmp_path)
    assert mod.main(["--src", str(src), "--dest", "/Volumes/NoSuchDrive-xyz/archives", "--apply"]) == 0
    assert "not mounted" in capsys.readouterr().out
    assert (src / "a-bo3-x.rar").exists()
