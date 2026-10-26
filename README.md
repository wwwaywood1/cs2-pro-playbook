# cs2-pro-playbook

Professional CS2 demos turned into something regular players can use: how top teams set up and
attack each map, what each player does, every round replayed in 2D with win probability, and a
library of the grenades pros actually throw, each with a one-line practice command.

Data through 2026-10-24: about 740 maps from 2026 tier-1 events on the active pool (Ancient,
Anubis, Cache, Dust2, Inferno, Mirage, Nuke), 54 teams; showcase teams Falcons · Vitality ·
Spirit · MOUZ · FURIA (`config/site.toml`). Every match is dated to the day.

## 中文简介

从职业比赛 demo 中自动提炼，面向普通玩家：

- **战队中心**：轨道式战队页 → 地图 → 选手；王牌图/短板图、阵容、定场诗。
- **战术**：T 方进攻套路（路线 + 道具组合 + 胜率）、CT 防守阵型（聚类 + 经济关联）。
- **道具库**：按职业比赛使用次数排序，带投掷技巧和 `setpos/setang` 练习指令。
- **热力图**：每队每图的站位、交火和道具分布。
- **2D 回放**：展示战队每一回合，带视角、胜率曲线、击杀与道具时间线。
- **AI 实验室**：胜率模型的可解释性（Shapley）、CT 阵型的注意力示意。
- 所有结论附样本量；统计结论经过显著性检验和多重比较控制。

## What's on the site

Teams hub (orbit → team → map → player: verses, 6-axis radar, win probability added) · Tactics
(T recipes and routes, CT defence patterns) · Lineup library · Heatmaps · 2D round replay with
view cones and a per-second win-probability strip · AI Lab · match-date filters. Chinese first;
the top-bar button switches to English. Desktop first.

## Repository layout

| Path | What |
|---|---|
| `playbook/` | pipeline: `parse` (awpy + polars) → `data/parsed` parquet → `export` → `data/site` JSON; dedupe, dates, win probability, replays, CT patterns, AI Lab, HLTV page parsers |
| `scripts/` | runbook tools: `refresh.sh`, `import_hltv.py`, `hltv_plan.py`, `hltv_queue.py`, `register_hltv_dates.py`, `archive_downloads.py`, `relocate_raw.py`, `team_assets.sh`, `make_portraits.py`, `sync_web_data.py`, `insight_text.py` |
| `config/` | maps and callouts, spots, team/player aliases, events, exact dates (`match_dates.csv`, `hltv_archives.json`), `hltv.toml` (download scope), `storage.toml` (where bulky data lives), `site.toml` (showcase teams) |
| `web/` | Vite + React + TypeScript site (HashRouter, static JSON) and browser smoke tests (`web/e2e/`) |
| `tests/` | pytest suite (demo-dependent tests skip without the test demo) |
| `samples/site/` | a one-match export used by CI |
| `docs/` | `WORKFLOW.md` (runbook, Chinese), `CREDITS.md` (data sources and licences) |

## Setup

```bash
python3.11 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Python ≥ 3.11
(cd web && npm ci)                                               # Node ≥ 22
.venv/bin/python -m pytest -q
```

## Adding data

HLTV only allows downloading demos by hand, so that one step is manual and everything else is
scripted (details in [docs/WORKFLOW.md](docs/WORKFLOW.md)):

1. **Plan**: list the 2026 tier-1 matches we don't have yet (`config/hltv.toml`), most popular first:
   `_sync/<team>_plan.json` and a click-through page `_sync/<team>_queue.html`
   (`scripts/hltv_plan.py <team> --results-html <saved HLTV results page>` or from bo3.gg/Liquipedia data).
2. **Download**: open the queue page in your browser and click each "Download demo" link; archives land in `~/Downloads`.
3. **Ingest**: `bash scripts/refresh.sh` moves the archives into `data/raw/hltv/`, extracts them (duplicates and
   off-pool maps skipped), records which HLTV match each archive is and its exact date
   (`config/hltv_archives.json`, `config/match_dates.csv`), moves the original archives to the external drive
   (SHA-256 verified), parses the new demos and exports the site data.

`data/raw` can live on an external drive (`config/storage.toml [raw]`, moved with `scripts/relocate_raw.py`);
parsing and exporting then need the drive mounted and stop with a clear message otherwise.

Legacy source: the cs2povarchive dataset on Hugging Face (`python -m playbook fetch`, `scripts/download_batch.py`).

## Pipeline commands

```bash
python -m playbook parse            # new demos under data/raw -> data/parsed
python -m playbook relabel          # re-apply config/maps/*.toml to parsed tables
python -m playbook export           # data/parsed -> data/site (written fresh, then swapped in)
python -m playbook run              # parse + export
python -m playbook callouts x.dem   # list a map's callout names (for config/maps/<map>.toml)
```

## Frontend

```bash
python scripts/sync_web_data.py            # data/site -> web/public/data (+ radars)
python scripts/sync_web_data.py --samples  # the committed one-match sample instead
cd web && npm run dev                      # or: npm run build -> web/dist
```

Team logos, player portraits and map backgrounds live in `web/public/{logos,players,map-bg}`; they are
supplied locally, gitignored and never published.

## Tests and CI

`pytest -q` runs the pipeline tests. `.github/workflows/ci.yml` runs them plus the TypeScript check, a
production build on `samples/site` and the browser smoke test (`web/e2e/smoke.py --samples`). On a real
export run `smoke.py` without flags, `--orbit-only`, `--lab-only` and `node web/e2e/orbit_geometry.mjs`.

## Adding a map

1. `python -m playbook callouts path/to/demo.dem` lists the map's callout names.
2. Map each callout to a region and each region to a lane in `config/maps/<map>.toml` (see `de_mirage.toml`),
   add the Chinese/English names to `web/src/i18n/{zh,en}.json` (`callout.<map>`), then `python -m playbook relabel`.

## Data sources and licence

Statistics are derived from GOTV recordings of professional matches made by the tournament organisers,
downloaded by hand from HLTV.org, and from the cs2povarchive dataset on Hugging Face (Apache-2.0). Match
start times were cross-checked with HLTV and bo3.gg. Demo files are not redistributed. Parsing uses awpy
(MIT); radar images and transforms come from awpy-data. Counter-Strike 2 and its assets are © Valve
Corporation; team names and logos are trademarks of their owners. This is a non-commercial fan analysis
project, not affiliated with or endorsed by Valve, HLTV, bo3.gg, any tournament organiser or team. Full
list: [docs/CREDITS.md](docs/CREDITS.md).

The **code** is MIT licensed; game art, logos and photos are not covered by that licence.
