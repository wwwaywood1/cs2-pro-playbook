# GPT-03：支持分段录制的 demo（交给 GPT / Codex）

> 用法：在 Codex 里打开 GitHub 仓库 `wwwaywood1/cs2-pro-playbook`（main 分支），从分割线开始粘贴下面的内容。
> Codex 环境如果能联网，可以直接从 Hugging Face 下载测试 demo；不能联网也没关系，它写代码和合成测试，Claude 再在你 Mac 上用真实 demo 验证。

---

`cs2-pro-playbook` parses professional CS2 demos with awpy 3.1 (`playbook/parse.py`). Our demo source (Hugging Face dataset `cs2povarchive/cs2-demos`, Apache-2.0, layout described in `playbook/fetch.py` and `DESIGN.md` › Data sources) sometimes records one map in several files: `<team1>-vs-<team2>[-mN]-<map>-p1.dem`, `-p2.dem`, ... About 19 of 262 games are split like this, usually after a server crash or a technical pause. Today they are skipped (`playbook/fetch.py` `Game.multipart`, `playbook/cli.py` `MULTIPART_RE`). Make them parse into one game.

Read `DESIGN.md`, `playbook/parse.py` (especially `parse_demo`, `_validate_rounds`, `_resolve_teams`, `_live_ticks`, `_playing`, `shots_table`), `playbook/fetch.py`, `playbook/cli.py`, and `tests/test_robustness.py` (GPT-01's rules for rejecting malformed demos).

What to build:

1. **Find out how awpy 3.1 handles parts.** Does `awpy.Demo` accept several files? If not, parse each part separately. Ticks restart in every part, so every table needs a per-part tick offset or a `part` column before rounds are stitched. Document what you found in the PR description.
2. **Stitching rules** (put them in `DESIGN.md` › Known limitations or a new short section):
   - Round numbers must continue across parts. A round that appears at the end of part 1 and again at the start of part 2 (restored from a backup) keeps the later, complete copy.
   - Scores before each round must still add up (the existing validation in `_validate_rounds` must pass on the stitched rounds, or explain why it cannot).
   - Teams and sides are resolved once for the whole game: the same steamids across parts.
   - `demo_id` stays `<hltv_match_id>_<stem without -pK>`; record the parts in `matches.demo_file` (for example `a-p1.dem+a-p2.dem`).
3. **Plumbing:** `fetch.select` should stop skipping multipart games and download all parts of the game; `cli._demo_paths` should group parts of one game and hand them to the parser together; files named `(1)` remain ignored duplicates.
4. **Tests:** unit tests for grouping file names into games (`tests/test_units.py` already has real path examples) and for the stitching logic on small synthetic polars frames (two parts with overlapping round numbers, a restored round, a part that starts mid-round). If you can download a real multipart game, add an optional end-to-end test that is skipped when the files are absent, like `tests/test_pipeline.py`.

Constraints: no new dependencies; do not change table columns or the site JSON contract (`DESIGN.md` › Tables and › Site data contract) except adding what parts need, and list any such change at the top of the PR description. Keep GPT-01's strictness: a game that cannot be stitched consistently is rejected with a clear error, not silently repaired.

Deliverable: one PR (or patch) with code, tests, the DESIGN.md note, and `pytest -q` output in the PR description. Say which multipart games you tested on, if any.
