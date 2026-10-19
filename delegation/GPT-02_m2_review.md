# GPT-02：热力图与战术识别代码审查（交给 GPT / Codex）

> 用法：在 Codex 里打开 GitHub 仓库 `wwwaywood1/cs2-pro-playbook`（main 分支），从分割线开始粘贴下面的内容。
> 不需要上传附件，Codex 直接读仓库。完成后把它的 PR（或 patch）和 `REVIEW-02.md` 交给 Claude。

---

You are reviewing the analysis layer of `cs2-pro-playbook`, a Python project that turns professional CS2 demos into per-round tables (awpy 3.1 + polars) and then into static JSON for a website. Read `DESIGN.md` first (sections "Tables", "Round semantics", "Heatmaps and player summaries", "Site data contract"), then:

- `playbook/heatmap.py` — cleaned event frames and per-team, per-player heatmap grids
- `playbook/zones.py` — per-player summaries (zones, holding spots, fights, utility spots)
- `playbook/tactics.py` — landing spots, T-round plans (commit, tempo, split, lurk, fake), execute recipes, CT setups
- `playbook/export.py` — how these are written to `data/site/**.json`
- `web/src/heatmap.ts` — the site's copy of the colouring math (must match `scripts/heatmap_preview.py`)
- tests: `tests/test_heatmap.py`, `tests/test_units.py`, `tests/test_robustness.py`

These modules were written quickly and checked on 65 real demos, but only through a handful of tests. Your job: find where they will produce **wrong numbers** or crash on the next few hundred demos, fix what matters, and add regression tests. Correctness and robustness only: no style refactors, no renames, no new dependencies (numpy and polars only in `playbook/`).

Check at least these, and for each say whether it is a real bug, a non-issue, or unverifiable:

1. **Gun-round filter** (`heatmap.clean_frames`): joins on `(demo_id, round_num, team)` with `team_rounds.buy_type in (full, force)`. Deaths use the victim's team, kills the attacker's. Is any event silently dropped or double counted? What if `team` is null for one row?
2. **Players who change team** between demos (a stand-in, a roster move mid-event): `roster_order` is computed per team over all maps, `build_heatmaps` restricts each player's grids to his rounds for that team. Check that a player appearing for two teams gets correct, separate grids and colours, and that `heatmap_teams.json` lists him under both.
3. **Phase precedence** (`_phase`): post-plant over early. Plants at the other site after a fake, two plants in a round (re-plant is impossible but check the data), plants after round end.
4. **Holding** (`step < HOLD_SPEED` with `gap == 1`): positions are sampled once per second; what happens at the `SPAWN_SKIP_S` cut, after a death and respawn (impossible in competitive, but check), and on two-level maps where a player moves vertically?
5. **Two-level maps** (Nuke: `lower_level_max_z`): `_cells` puts z below the threshold on level 1. Verify holding spots (`zones._holds`) and utility spots carry the right level, and that the TS function `denseLayers` and the Python `merge_phases`/`to_array` agree on cell indices for level 1.
6. **`tactics.density_clusters`**: chunked neighbour computation with `sq_i + sq_j - 2 x_i·x_j`. Can floating-point error make a point miss itself (empty neighbour list) or produce non-deterministic labels? Is the result independent of input order for ties?
7. **`tactics.average_linkage`**: compare against `scipy.cluster.hierarchy.linkage(method="average")` + `fcluster(criterion="distance")` on random Jaccard matrices (scipy only inside the test, skip the test if scipy is missing). Report any mismatch.
8. **Commit detection** (`t_plans`): the target is the plant site, else the first site where two T players stood on the `BombsiteA/B` callout. Cases: plant at B after an earlier two-man touch of A; plant with only one player ever on the core; a round that ends before any T reaches a site; overtime rounds. Are `commit_s`, `target`, `tempo` and `attempt` consistent in every case?
9. **Split** (`entry_spread` or `n_directions`): the self-join on entries per round — any quadratic blow-up or a case where a player enters, leaves and re-enters the site region and is counted twice?
10. **Recipes** (`execute_recipes`): merging clusters that share a smoke core. Can two recipes end up with the same `id`? Can a round be assigned to two recipes? Is the output deterministic across runs (export twice and diff `data/site`, or reason it through)?
11. **Determinism of the whole export**: `python -m playbook export` twice into two folders must produce identical files except `generated_at`. Find any remaining `group_by` without `maintain_order` or sorted keys that leaks into JSON order.
12. **TS/Python parity**: `web/src/heatmap.ts` `playerRgba`/`ownerRgba` vs `scripts/heatmap_preview.py` `player_rgba` and the owner panel. Same gamma, alpha floor and colour ramps? Write a small Node check if needed (`npx esbuild web/src/heatmap.ts --format=esm` then import it).

Data: real demos are not in the repo (`data/` is git-ignored). Use small synthetic polars frames, as `tests/test_heatmap.py` does; the column sets of every table are listed in `DESIGN.md` › Tables. `samples/site/` holds one real exported match if you need realistic JSON.

Deliverables, in one pass:

- `REVIEW-02.md` at the repo root: a table of the cases above (status, evidence, impact), then any other issues you found, ranked by impact.
- One patch (a PR is fine) with the fixes, and a regression test under `tests/` for each fix.
- `pytest -q` output pasted at the end of `REVIEW-02.md` (the end-to-end test is skipped without the demo; that is expected).
- Do not change JSON field names or meanings (`DESIGN.md` › Site data contract and `web/src/types.ts`) unless you list the change at the top of `REVIEW-02.md` with the reason.
