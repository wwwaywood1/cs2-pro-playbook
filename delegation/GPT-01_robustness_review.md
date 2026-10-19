# GPT-01：解析层健壮性审查（交给 GPT / Codex，只此一次）

> 用法：把仓库推到 GitHub，在 Codex 里打开这个仓库，从分割线开始粘贴下面的内容。
> 这是唯一交给 GPT 的任务。它需要读代码、自己构造边界情况、跑测试，DeepSeek 不适合做。为了省额度，要求它一次完成、不做风格重构。

---

You are reviewing the data pipeline of `cs2-pro-playbook`, a Python project that turns professional CS2 demos into per-round tables using awpy 3.1 and polars. Read `DESIGN.md` first, then `playbook/parse.py`, `playbook/semantics.py`, `playbook/utility.py`.

The pipeline is verified on two clean pro demos (see `tests/test_pipeline.py`). Your job is to find the cases where it will silently produce **wrong** data on the next few hundred demos, and fix the ones that matter. Correctness only: no style refactors, no renames, no new dependencies.

Check at least these, and say for each whether it is a real bug, a non-issue, or unverifiable:

1. **Technical pause with backup restore** (`mp_backup_restore_load_file`): can a round appear twice in `demo.rounds`, or round numbers go backwards? What happens to `score_*_before`, `_assign_round` (join_asof on start_tick) and positions sampling?
2. **Overtime** (MR3 halves after round 24): `half_of`, side detection per round, and the score loop.
3. **Mid-match substitution or reconnect**: a player whose steamid appears only in some rounds; a player listed in `demo.players` with the wrong last side or a missing clan name.
4. **Bots or steamid 0** (a disconnect replaced by a bot): `team_of` is keyed by steamid, so several bots would collide on key 0.
5. **Demos without clan names**: the fallback labels teams `"T-start team"` / `"CT-start team"`. Is that stable after the side switch? Can both teams end up with the same label?
6. **Demo starting mid-match** (GOTV joined late): first round is not round 1; `first_fe` is used for the fallback.
7. **128-tick or non-64 tick rate**: anything that assumes 64 (sampling step, grenade match window `MATCH_WINDOW_TICKS = 32`).
8. **Grenade attribution**: can the greedy matcher assign a grenade to the wrong thrower when two teammates throw the same grenade type within 0.5s from close positions (a common execute pattern)? Propose a tighter rule only if you can show a case.
9. **Opening kill** with a teamkill or world/bomb death first; and `is_opening` when two kills share the same tick.
10. **pivot in `side_by_round`**: what if a round has players of only one side at freeze end (e.g. a demo starting mid-round)?

Deliverables, in one pass:

- `REVIEW.md` at the repo root: a table of the cases above (status, evidence, impact), then any other issues you found, ranked by impact.
- A single patch fixing the real bugs, with a regression test for each fix under `tests/`. Use small synthetic polars frames where a demo is not needed (the semantics functions are pure functions of the parse tables).
- Run `pytest -q` and paste the result into `REVIEW.md`. End-to-end tests need `data/raw/hltv-de_mirage-2394170.dem` (download command in README.md); if you cannot download it, say so and rely on unit tests.
- Do not change the column names or meanings of any table, or the site JSON contract (`DESIGN.md` › Site data contract), without listing the change explicitly at the top of `REVIEW.md`.
