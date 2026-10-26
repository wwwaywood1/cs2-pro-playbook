"""scripts/team_assets.sh with curl and sleep replaced by stand-ins: image CDNs only, never www.hltv.org."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="needs bash")
UA = "cs2-pro-playbook/0.1 (personal non-commercial CS2 demo analysis; one download at a time)"
SEP = "\x1f"

FAKE_CURL = r"""#!/bin/bash
# curl stand-in: logs its arguments (unit-separated), "downloads" a tiny image to the -o path
( IFS=$'\x1f'; printf '%s\n' "$*" ) >> "$FAKE_LOG"
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o|-A|-w|--proto|--max-time) [ "$1" = -o ] && out="$2"; shift ;;
    -*) ;;
    *) url="$1" ;;
  esac
  shift
done
case "$url" in
  *broken*) echo "curl: (22) The requested URL returned error: 404" >&2; exit 22 ;;
  *checkpage*) printf '<html>check</html>' > "$out"; printf '200 text/html'; exit 0 ;;
esac
printf 'PNG' > "$out"
printf '200 image/png'
"""

ASSETS = """# Aurora: logo and player photos
logo.svg https://img-cdn.hltv.org/teamlogo/abc.svg?ixlib=java-2.1.0&s=x
xantares.png https://img-cdn.hltv.org/playerbodyshot/x.png?ixlib=java-2.1.0&w=400&s=y
woxic.webp https://files.bo3.gg/uploads/image/1/woxic.webp\r

page.png https://www.hltv.org/team/11861/aurora
caps.png https://WWW.HLTV.ORG./img/x.png
bare.png https://hltv.org/x.png
trick.png https://img-cdn.hltv.org@www.hltv.org/x.png
plain.png http://img-cdn.hltv.org/x.png
../escape.png https://img-cdn.hltv.org/x.png
have.png https://img-cdn.hltv.org/have.png
broken.png https://img-cdn.hltv.org/broken.png
checkpage.png https://img-cdn.hltv.org/checkpage.png
"""


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "team_assets.sh", root / "scripts" / "team_assets.sh")
    (root / "_sync" / "aurora_assets").mkdir(parents=True)
    (root / "_sync" / "aurora_assets.txt").write_text(ASSETS)
    (root / "_sync" / "aurora_assets" / "have.png").write_bytes(b"old")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "curl").write_text(FAKE_CURL)
    (bin_dir / "sleep").write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$FAKE_SLEEP_LOG"\n')
    for tool in ("curl", "sleep"):
        (bin_dir / tool).chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
           "FAKE_LOG": str(tmp_path / "curl.log"), "FAKE_SLEEP_LOG": str(tmp_path / "sleep.log")}
    return root, env, tmp_path


def _run(root, env):
    return subprocess.run([BASH, str(root / "scripts" / "team_assets.sh"), "aurora"], env=env,
                          capture_output=True, text=True, timeout=60)


def _calls(tmp_path):
    log = tmp_path / "curl.log"
    return [line.split(SEP) for line in log.read_text().splitlines()] if log.exists() else []


def test_fetches_cdn_images_once_and_refuses_hltv_pages(repo):
    root, env, tmp_path = repo
    proc = _run(root, env)
    assert proc.returncode == 1, proc.stdout + proc.stderr          # refusals and failures are reported
    out = root / "_sync" / "aurora_assets"
    assert sorted(p.name for p in out.iterdir()) == ["have.png", "logo.svg", "woxic.webp", "xantares.png"]
    assert (out / "have.png").read_bytes() == b"old"                 # existing files are not fetched again
    assert "== assets for aurora: 3 new, 1 already there, 6 refused, 2 failed" in proc.stdout
    for name in ("page.png", "caps.png", "bare.png", "trick.png", "plain.png", "../escape.png"):
        assert f"REFUSED {name}" in proc.stdout
    calls = _calls(tmp_path)
    urls = [c[-1] for c in calls]
    assert urls == ["https://img-cdn.hltv.org/teamlogo/abc.svg?ixlib=java-2.1.0&s=x",
                    "https://img-cdn.hltv.org/playerbodyshot/x.png?ixlib=java-2.1.0&w=400&s=y",
                    "https://files.bo3.gg/uploads/image/1/woxic.webp",
                    "https://img-cdn.hltv.org/broken.png", "https://img-cdn.hltv.org/checkpage.png"]
    for args in calls:
        assert args[args.index("-A") + 1] == UA                      # says who it is
        assert args[args.index("--proto") + 1] == "=https"
        assert "-L" not in args and "--location" not in args         # never follows a redirect
    assert (tmp_path / "sleep.log").read_text().split() == ["2"] * 4  # 2 s between the 5 requests
    assert not list(out.glob(".*.part"))


def test_second_run_only_retries_what_failed(repo):
    root, env, tmp_path = repo
    _run(root, env)
    (tmp_path / "curl.log").unlink()
    proc = _run(root, env)
    assert [c[-1] for c in _calls(tmp_path)] == ["https://img-cdn.hltv.org/broken.png",
                                                 "https://img-cdn.hltv.org/checkpage.png"]
    assert "0 new, 4 already there" in proc.stdout


def test_shell_scripts_parse():
    for script in ("team_assets.sh", "refresh.sh"):
        proc = subprocess.run([BASH, "-n", str(REPO / "scripts" / script)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
