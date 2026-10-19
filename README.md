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
python -m playbook fetch               # download them into data/raw/
python -m playbook run                 # parse + export -> data/site/*.json
pytest -q                              # tests (end-to-end ones need the test demo, see below)
```

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

- Demos: [CounterQuant CS2 Demos](https://huggingface.co/datasets/KEDevO/CounterQuant-CS2-Demos) (CC BY 4.0), originally from HLTV.org.
- Parsing: [awpy](https://github.com/pnxenopoulos/awpy) (MIT). Radar images and transforms: awpy-data.
- Method inspiration: Xenopoulos et al., *ggViz* (2022), *Valuing Player Actions in CSGO* (2020), *ESTA* (2022).

Not affiliated with Valve, HLTV, or any team. MIT licensed.
