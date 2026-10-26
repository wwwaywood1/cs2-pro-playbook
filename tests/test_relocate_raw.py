import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "relocate_raw", Path(__file__).resolve().parents[1] / "scripts" / "relocate_raw.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _setup(tmp_path):
    src = tmp_path / "repo" / "data" / "raw"
    (src / "hltv" / "event-a-vs-b-bo3-X").mkdir(parents=True)
    (src / "hltv" / "event-a-vs-b-bo3-X" / "a-vs-b-m1-mirage.dem").write_bytes(b"m" * 1000)
    (src / "hltv" / "event-a-vs-b-bo3-X" / "._a-vs-b-m1-mirage.dem").write_bytes(b"junk")
    (src / "hltv" / ".import_hltv_archives.json").write_text("[]")
    dest = tmp_path / "ssd" / "raw"
    (tmp_path / "ssd").mkdir()
    return src, dest


def _args(src, dest, *extra):
    return ["--src", str(src), "--dest", str(dest), *extra]


def test_plan_only_copies_nothing(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    assert mod.main(_args(src, dest)) == 0
    assert "2 left to copy" in capsys.readouterr().out
    assert not (dest / "hltv").exists()


def test_copy_switch_finish(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    assert mod.main(_args(src, dest, "--switch")) == 1  # copy incomplete
    assert mod.main(_args(src, dest, "--copy")) == 0
    rel = "hltv/event-a-vs-b-bo3-X/a-vs-b-m1-mirage.dem"
    assert (dest / rel).read_bytes() == b"m" * 1000
    assert not (dest / "hltv/event-a-vs-b-bo3-X/._a-vs-b-m1-mirage.dem").exists()
    man = [json.loads(line) for line in (dest / ".relocated.jsonl").read_text().splitlines()]
    assert {m["rel"] for m in man} == {rel, "hltv/.import_hltv_archives.json"}
    # resumable: a second copy run has nothing left
    capsys.readouterr()
    assert mod.main(_args(src, dest, "--copy")) == 0
    assert "0 left to copy" in capsys.readouterr().out
    assert mod.main(_args(src, dest, "--switch")) == 0
    assert src.is_symlink() and (src / rel).read_bytes() == b"m" * 1000
    locals_ = list(src.parent.glob("raw.local-*"))
    assert len(locals_) == 1
    assert mod.main(_args(src, dest, "--finish")) == 0
    assert not locals_[0].exists() and (src / rel).exists()


def test_finish_keeps_local_copy_when_destination_lost_a_file(tmp_path, capsys):
    src, dest = _setup(tmp_path)
    mod.main(_args(src, dest, "--copy"))
    mod.main(_args(src, dest, "--switch"))
    (dest / "hltv/event-a-vs-b-bo3-X/a-vs-b-m1-mirage.dem").unlink()
    assert mod.main(_args(src, dest, "--finish")) == 1
    assert list(src.parent.glob("raw.local-*"))


def test_unmounted_destination(tmp_path, capsys):
    src, _ = _setup(tmp_path)
    assert mod.main(_args(src, tmp_path / "nowhere" / "raw", "--copy")) == 1
    assert "not mounted" in capsys.readouterr().out
