# cs2-pro-playbook

Open-source analysis of professional CS2 demos, turned into something regular players can use:
how pro teams set up and attack each map, what role each player plays, and a library of the
grenades pros actually throw, each with a one-line practice command.

> Status: data pipeline working and tested (M0). Website v1 in [`web/`](web/) (M3);
> tactic clustering in progress. See [DESIGN.md](DESIGN.md) for the architecture,
> data contract and roadmap.

## 中文简介

从职业比赛 demo 中自动提炼三类内容，面向普通玩家：

- **队伍战术画像**：每张图的 T 方默认站位、进攻点、执行节奏，CT 方站位与回防。每个结论都附样本量。
- **选手打法画像**：狙击手、自由人、突破手、主防等角色提示，并附上判定依据的数据。
- **职业道具库**：按职业比赛中的使用次数排序。每颗道具都有投掷技巧（跳投、跑投等）和 `setpos/setang` 练习指令，复制进练习服即可站到出手点。

## Quick start

```bash
pip install -e ".[fetch,dev]"          # Python 3.11+

python -m playbook fetch --dry-run     # list demos matching config/targets.toml
python -m playbook fetch               # download them into data/raw/cs2povarchive/
# no Hugging Face access where the pipeline runs? on any machine that has it:
#   python3 -m pip install -U huggingface_hub && python3 scripts/download_batch1.py
python -m playbook run                 # parse + export -> data/site/*.json
pytest -q                              # tests (end-to-end ones need the test demo, see below)
```

## 从 HLTV 补录像

在 HLTV 比赛页面点击 **GOTV Demo**，手动下载压缩包，放到 `data/raw/hltv/`
（目录不存在时先创建）。支持直接放入 `.rar`、`.zip`、单个 demo 的 `.gz` / `.bz2`
或未压缩的 `.dem`；只读取该目录第一层的下载文件。

```bash
.venv/bin/python scripts/import_hltv.py
.venv/bin/python -m playbook parse
.venv/bin/python -m playbook export
```

导入器依次尝试 `bsdtar`、`unar`、`7z`（或 `7zz`），ZIP 最后可用 Python 自带的 `zipfile`；
若 RAR 无法打开，可运行 `brew install sevenzip`。压缩包解到
`data/raw/hltv/<压缩包主名>/`，只保留当前地图池中的新 demo；`-p1`、`-p2`
保留在同一目录，解析时自动拼接。已解析或已导入的相同 demo identity 会跳过。
原压缩包默认保留，`--delete-archives` 仅在该包没有导入失败时删除；可先用
`--dry-run` 查看计划（不解压，包内地图与重复检查留到正式导入时）。自定义下载目录可用
`--src DIR`；若目录不在 `data/raw/` 下，第二条命令须加上该目录作为输入。
散装 `.dem` 原地登记，重复或池外文件也不会删除；这些原文件仍会被 `parse`
递归发现，如需排除请自行移到 `data/raw/` 之外。统计按整场地图计数，多段录像只计一次。

## Website

The v1 frontend lives in [`web/`](web/): Vite + React + TypeScript with a `HashRouter`, no
backend. It reads precomputed JSON from `web/public/data/` and radar images from
`web/public/radars/`; both directories are generated and gitignored.

```bash
cd web
npm install
npm run dev       # local dev server
npm run build     # tsc -b && vite build -> web/dist
```

Populate the sample data (Mirage, one match) before the first run:

```bash
python scripts/sync_web_data.py --samples
```

Radars are included in CI and Pages builds. The sync script uses awpy to download
`images.zip` from the pinned awpy-data release `2000933` on the first run, then
copies the needed images from `~/.awpy/`. Both workflows cache that directory;
no demos, navigation meshes, or geometry downloads are needed for the web build.

### CI and browser smoke tests

[`ci.yml`](.github/workflows/ci.yml) runs on pushes and pull requests. Its Python
and web jobs run in parallel with pip and npm caches and six-minute timeouts.
Python uses 3.11, `pip install -e ".[dev]"` and `pytest -q`; tests requiring the
uncommitted demo skip when it is absent. The web job syncs `samples/site`, runs
`npm ci` and `npm run build`, then serves `web/dist` to Playwright's Chromium
headless shell. Failure screenshots and the static server log are uploaded as
the `smoke-screenshots` artifact (retained for seven days).

To run the browser checks locally, from the repository root:

```bash
python -m pip install -r web/e2e/requirements.txt
python -m playwright install --with-deps --only-shell chromium
python scripts/sync_web_data.py --samples
(cd web && npm ci && npm run build)
python3 -m http.server 4173 --bind 127.0.0.1 --directory web/dist
# In a second terminal:
python3 web/e2e/smoke.py http://127.0.0.1:4173 --shots work/smoke-shots
```

Add a route to [`web/e2e/smoke.py`](web/e2e/smoke.py) by writing one function
decorated with `@route("#/path", "ready-selector")`, taking `(smoke, page)` and
using `smoke.check(condition, description)` for assertions. The runner navigates
to it, waits for its ready selector, runs its desktop checks, checks for horizontal
overflow at 375px, and collects browser errors and screenshots in both viewports.
The DS-06 heatmap route can use the same registration once it is available.

### Manual GitHub Pages deployment

In repository **Settings → Pages**, select **GitHub Actions** as the build source.
Then run **Actions → Deploy Pages → Run workflow** on the desired branch.
[`pages.yml`](.github/workflows/pages.yml) is `workflow_dispatch` only: it builds
the committed one-match `samples/site` export plus radars, uploads `web/dist`, and
deploys with `actions/deploy-pages`. The deploy job uses the `github-pages`
environment and is the only job granted `pages: write` and `id-token: write`.
Private repositories need a GitHub plan that supports Pages, or must become public.
Vite's relative base and the HashRouter support the repository subpath without
server rewrites.

To deploy real data later, produce an export locally and package the **contents**
of `data/site` (including `index.json`, map directories and heatmap JSON):

```bash
python -m playbook run
tar -czf site-data.tar.gz -C data/site .
```

Publish that archive as a release asset, or upload the same directory as a workflow
artifact named `site-data` through a separate data-producing workflow. In the
Pages build, add a download step **before** the sync step, placing the complete
export at `data/site/`, and change the sync command to
`python scripts/sync_web_data.py` (remove `--samples`). Keep CI on sample data.
For a release asset, pin its tag and download/extract it, for example:

```yaml
- name: Download real site export
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    gh release download site-data-2026-10-19 --pattern site-data.tar.gz --dir "$RUNNER_TEMP"
    mkdir -p data/site
    tar -xzf "$RUNNER_TEMP/site-data.tar.gz" -C data/site
```

For a workflow artifact, use `actions/download-artifact@v4` with `name: site-data`,
`path: data/site`, the producer's `run-id`, and `github-token: ${{ github.token }}`;
add `actions: read` to the build job's permissions alongside `contents: read` for
cross-run downloads. Keep the producer run ID or release tag explicit so deployments
are reproducible. Demos and intermediate parsed tables stay outside the deployment.

The pages are the map index, the lineup library (radar plus copyable practice commands),
team profiles (T/CT setups, executes, economy) and player profiles (roles, lanes). Chinese
is the default language; the top-bar button switches to English and remembers the choice in
`localStorage`.

Demos you download yourself (for example from HLTV) can go straight into `data/raw/`.

Test demo for the end-to-end tests (B8 vs Vitality, Mirage, 347 MB):

```bash
curl -L -o data/raw/hltv-de_mirage-2394170.dem \
  https://github.com/pnxenopoulos/awpy-fixtures/releases/download/hltv-de_mirage-2394170/hltv-de_mirage-2394170.dem
```

## What the pipeline produces

From one demo (about 15 to 30 seconds to parse), per round and per player:
teams and sides, economy, positions every second with callouts, kills with opening-duel
flags, plants with site, and every grenade with its thrower, release spot, view angles and
landing callout. On top of that, per round: setup "shapes" (for example `A2 M2 B1`), execute
timing and lane, and per player: distance to teammates, site-entry order, opening duels.

Across demos, `export` writes static JSON for the site (team profiles, player profiles,
lineup library). A real one-match example is in [`samples/site/`](samples/site/).

## Adding a map

1. `python -m playbook callouts path/to/demo.dem` lists the map's callout names.
2. Map each callout to a region and each region to a lane in `config/maps/<map>.toml`
   (see `de_mirage.toml`).

## Data and credits

- Demos: [cs2povarchive/cs2-demos](https://huggingface.co/datasets/cs2povarchive/cs2-demos) on Hugging Face (Apache-2.0): IEM Cologne Major 2026 and CAC 2026 GOTV demos.
- Parsing: [awpy](https://github.com/pnxenopoulos/awpy) (MIT). Radar images and transforms: awpy-data.
- Method inspiration: Xenopoulos et al., *ggViz* (2022), *Valuing Player Actions in CSGO* (2020), *ESTA* (2022).

Not affiliated with Valve, HLTV, or any team. MIT licensed.

