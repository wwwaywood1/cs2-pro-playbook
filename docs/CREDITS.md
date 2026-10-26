# 数据来源与版权 / Data sources & credits

The website shows this text at `#/about` (`web/src/pages/About.tsx`); keep both in sync.

## 数据来源与版权

### 比赛数据
- 本站的统计数据来自职业 CS2 比赛的 GOTV 录像（demo）。这些录像由各赛事主办方录制，作者从 [HLTV.org](https://www.hltv.org/) 的比赛页面手动下载；另有部分比赛来自 Hugging Face 上的 [cs2povarchive/cs2-demos](https://huggingface.co/datasets/cs2povarchive/cs2-demos) 数据集（Apache-2.0 许可）。
- 比赛的具体日期已与 HLTV 和 [bo3.gg](https://bo3.gg/) 交叉核对。
- 本站不重新分发任何 demo 文件，只发布由录像计算得到的统计结果。

### 解析与地图素材
- Demo 解析使用 [awpy](https://github.com/pnxenopoulos/awpy)（MIT 许可）；雷达图与坐标换算来自 [awpy-data](https://github.com/pnxenopoulos/awpy-data)。
- Counter-Strike 2 及其素材（包括地图、雷达图与游戏画面）© Valve Corporation。本站是非商业的爱好者分析项目，与 Valve、HLTV、bo3.gg、任何赛事主办方或战队均无关联，也未获得其认可。
- 战队名称与标志是其各自所有者的商标，仅用于标识战队。

### 方法
- 回合胜率模型与行为价值（WPA）参考 Szmida & Toka（MIT Sloan 体育分析大会，2025）与 Xenopoulos 等人（2020，Valuing Player Actions in Counter-Strike: Global Offensive）；数据处理与可视化思路参考 Xenopoulos 等人的 ggViz（2022）与 ESTA（2022）。AI 实验室页面另列出其所用文献。

### 代码
- 本站代码以 MIT 许可发布。

## Data sources & credits

### Match data
- Statistics on this site are derived from GOTV recordings (demos) of professional CS2 matches. The recordings are made by the tournament organisers; the author downloaded them by hand from [HLTV.org](https://www.hltv.org/) match pages, and some matches come from the [cs2povarchive/cs2-demos](https://huggingface.co/datasets/cs2povarchive/cs2-demos) dataset on Hugging Face (Apache-2.0).
- Exact match dates are cross-checked with HLTV and [bo3.gg](https://bo3.gg/).
- Demo files are not redistributed; only statistics computed from them are published.

### Parsing and map assets
- Demos are parsed with [awpy](https://github.com/pnxenopoulos/awpy) (MIT). Radar images and coordinate transforms come from [awpy-data](https://github.com/pnxenopoulos/awpy-data).
- Counter-Strike 2 and its assets (including maps, radar images and game imagery) © Valve Corporation. This is a non-commercial fan analysis project, not affiliated with or endorsed by Valve, HLTV, bo3.gg, any tournament organiser or team.
- Team names and logos are trademarks of their respective owners, used only to identify the teams.

### Methods
- The round win-probability model and action values (WPA) draw on Szmida & Toka (MIT Sloan Sports Analytics Conference, 2025) and Xenopoulos et al. (2020, Valuing Player Actions in Counter-Strike: Global Offensive); data processing and visualisation draw on Xenopoulos et al.'s ggViz (2022) and ESTA (2022). The AI Lab page lists the further works it uses.

### Code
- The site's code is released under the MIT licence (see `LICENSE`).
