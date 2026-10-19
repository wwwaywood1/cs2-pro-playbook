# DS-06：战队热力图页面（交给 DeepSeek，一次做完）

> 用法：
> 1. 新开一个 DeepSeek 对话，从分割线开始整段粘贴本文件。
> 2. **同时上传 11 个附件**（都在仓库里，路径如下）：
>    - `web/src/types.ts`：数据类型，末尾"heatmaps"一节是本任务用的
>    - `web/src/heatmap.ts`：热力图计算和着色函数，Claude 已写好并验证过
>    - `web/src/data.ts`：数据加载函数，已包含 `getHeatmapTeams`、`getTeamHeatmap`
>    - `web/src/App.tsx`
>    - `web/src/components/Layout.tsx`
>    - `web/src/components/Radar.tsx`：参考它的 SVG 写法
>    - `web/src/pages/Team.tsx`
>    - `web/src/pages/Players.tsx`
>    - `web/src/pages/Lineups.tsx`
>    - `samples/site/heatmap_teams.json`：真实数据样例
>    - `samples/site/de_mirage/heatmaps/teams/vitality.json`：真实数据样例
> 3. 把 DeepSeek 的回复原样交回给 Claude。Claude 负责落盘、编译、浏览器测试和合并。

---

你是资深前端工程师。这个开源 CS2 数据网站已经有道具库、队伍页、选手页（Vite + React 18 + TypeScript strict，HashRouter，静态 JSON，无后端）。现在要加一个**战队热力图**页面。

用户的操作顺序是：**选战队 → 用左右箭头切换地图 → 选 T/CT → 勾选选手**。

每名选手有一个固定颜色，按顺序是红、蓝、紫、绿、橙。颜色越浅表示该选手在这里出现得越少，越深表示越多。用户能直接看出这支队每个人在每张图、每个阵营各打哪里，在哪里交火，道具落在哪里。

## 硬性约束

- 不新增任何依赖。不要引入图表库、UI 库或 canvas 库。
- **不要修改** `src/types.ts`、`src/heatmap.ts`、`src/data.ts`。类型、计算函数和颜色直接 import 使用，不要重新实现。颜色一律取 `PLAYER_COLORS` / `playerColor()`，不要写死。
- 新样式写在新文件 `src/heatmap.css`，由热力图页面 `import "../heatmap.css";` 引入。**不要改 `src/styles.css`**，可以复用其中已有的 CSS 变量和类名。
- 文案统一通过 `t("heatmap.xxx")` 取值。新增的键不要直接写进 i18n 文件，而是在交付末尾单独给 zh、en 两个 JSON 片段，由 Claude 合并。键名见下文"文案键"。
- 所有数字遇到 `null` 显示为 "—"。375px 手机宽度下不能出现横向滚动条。

## 数据（结构见 types.ts 的 heatmaps 一节）

```
data/heatmap_teams.json                 HeatmapTeamIndexEntry[]：入口，列出每个战队有数据的地图（已按出场次数排好，就是箭头的顺序）和固定颜色的选手名单
data/<map>/heatmaps/teams/<slug>.json   TeamHeatmap：该队在这张图上每名选手的网格数据和总结
data/<map>/heatmaps/baseline.json       HeatmapBaseline：网格参数（grid、levels），本页只用它的 grid 和 levels
```

用 `data.ts` 里的 `getHeatmapTeams()`、`getTeamHeatmap(map, slug)`、`getHeatmapBaseline(map)` 加载。

数据是清洗过的：
- 只统计双方的枪局（full/force 购买）。
- 只统计活着的时间，并去掉开局前 5 秒和回合结束后的时间。
- 每个数值都是"每回合"的。

**网格：** 一共 `grid × grid`（64×64），覆盖 1024×1024 的雷达图。`levels` 为 2 时（Nuke），第二层对应下层雷达图 `radars/<map>_lower.png`。

**图层（HeatLayer）：**
- `presence`：站位时间
- `holding`：驻守时间，即几乎不动的时间
- `shots`：开枪
- `kills`：击杀
- `deaths`：阵亡
- `smoke`、`flash`、`molotov`、`he`：四类道具的**落点**

**阶段（HeatPhase）：**
- `early`：开局 20 秒内
- `mid`：中期
- `post`：下包后

**选手颜色：** `TeamHeatmap.roster[i].color` 和 `HeatmapTeamIndexEntry.roster[i].color` 是同一个编号，0 到 4 对应红、蓝、紫、绿、橙，5 及以上是替补，用灰色。每名选手在所有地图、两个阵营下都保持同一个颜色。

## 页面与路由

1. **`/heatmaps`：选战队。** 用卡片网格列出 `heatmap_teams.json` 里的所有战队，每张卡片显示队名、总场数、有数据的地图数、五名主力选手的名字（名字前加对应颜色的色点）。顶部有一个搜索框，可以按队名过滤。点击卡片进入 2。
2. **`/heatmaps/:slug`：战队热力图主页面。** 所有状态都写进 query string，刷新或分享链接后能还原。使用 `useSearchParams`，参数如下：
   - `map`：默认为该队 `maps[0]`
   - `side`：T 或 CT，默认 CT
   - `players`：逗号分隔的 steamid，默认是这张图上 `color < 5` 且该阵营 `rounds > 0` 的全部选手
   - `view`：presence、holding、fights 或 utility，默认 presence
   - `util`：all、smoke、flash、molotov 或 he，只在 view=utility 时有效，默认 all
   - `phases`：early、mid、post 的组合，默认三个都选
   - `mode`：stack 或 owner，默认 stack
   - `sigma`：默认 1.0
   - `level`：0 或 1
   - 参数缺失或非法时用默认值，不能报错。slug 不存在时显示 `heatmap.team_not_found`，并给出返回 `/heatmaps` 的链接。

## 主页面布局（`/heatmaps/:slug`）

从上到下（桌面端把热力图和控件左右排列，手机端上下排列）：

1. **标题行：** 队名，以及返回战队列表的链接。
2. **地图切换器：** `←  [地图名 · N 场 · T x / CT y 枪局]  →`。
   - 左右箭头按 `maps` 数组的顺序循环切换，到头后回到另一端。
   - 键盘的 ArrowLeft / ArrowRight 也能切换，但焦点在输入框或滑块上时不响应。
   - 只有一张图时，两个箭头都禁用。
   - 切换地图时，保留阵营、视图、阶段和模式；选手勾选重置为这张图的默认值。
3. **阵营：** T / CT 两个切换按钮。
4. **选手：** 每名选手一个可勾选的标签（chip），左侧是颜色块，用 `playerColor(color).deep`。标签上显示名字和该阵营的回合数；`low_sample[side]` 为 true 时加一个"样本少"小标记。另有"全选"和"全不选"两个按钮。只列出这张图上该阵营 `rounds > 0` 的选手。
5. **视图：** 四个标签页，分别是站位（presence）、驻守（holding）、交火（fights）、道具落点（utility）。选中道具落点时，下方再出一排子筛选：全部 / 烟 / 闪 / 火 / 雷。
6. **阶段：** 开局 / 中期 / 下包后三个多选框，至少保留一个勾选。
7. **模式：**
   - 叠加（stack）：每名选手单独一层，按自己的颜色从浅到深着色。
   - 区域归属（owner）：每个格子只显示在这里数值最高的那名选手的颜色。
8. **平滑：** sigma 滑块，范围 0–2.5，步长 0.1，默认 1.0。
9. **楼层：** 只在 `levels === 2` 时显示，选项为上层 / 下层。
10. **热力图本体**（见下文"计算与绘制"）。图下方为每名已勾选的选手显示一行说明，格式例如"🟥 donk · 站位 72 秒/回合"。数值用 `perRound(players[steamid], side, phases, 当前视图的图层)` 取得。presence 和 holding 的单位是秒，其余是次数。
11. **默认站位：** 显示 `setup[side].early` 的内容，按路线列出选手名，名字用各自的颜色。例如"A：donk、tN1R ｜ 中路：zont1x ｜ B：magixx ｜ 警家：sh1ro"。路线名用已有的 `t("lane.<LANE>")`。
12. **选手卡片：** 每名已勾选的选手一张卡片，边框用他的颜色。内容取自 `summary[steamid][side]`，没有数据时显示 `heatmap.no_data`：
    - **主要位置：** 当前所选阶段里每个阶段的 `zones[phase]` 前 3 项，显示点位名和占比。点位名用已有的 `calloutLabel(map, place)` 翻译。
    - **常驻守点：** `holds` 前 3 项，显示点位、每回合秒数、驻守过的回合数。勾选"在图上标出驻守点"后，在雷达上用该选手颜色的空心圆标出这些点（`radar_x`、`radar_y`；`level` 必须与当前楼层一致）。
    - **交火：** 每回合击杀和阵亡数、首杀和首死次数、交火最多的 3 个点位（击杀/阵亡）。
    - **道具：** 每回合烟、闪、火、雷的数量；常用落点 `utility.spots` 前 5 项，显示类型、点位、次数。若 `lineups` 不为空，加一个"去道具库看怎么扔"链接，跳到 `/<map>/lineups?id=<lineups[0].lineup_id>`。

## 计算与绘制（全部用 heatmap.ts 里的函数）

```ts
const shape = { grid: baseline.grid, levels: baseline.levels };
const weights = view === "utility" && util !== "all" ? { [util]: 1 } : VIEW_WEIGHTS[view];
// 每名已勾选的选手：
const values = blur(combine(denseLayers(team.players[steamid], side, phases, shape), weights, shape), shape, sigma);
// stack：每人一张图，颜色编号越小越靠上（先画编号大的）
const url = toDataUrl(playerRgba(values, shape, level, playerColor(color)), shape.grid);
// owner：所有已勾选的选手合成一张
const url = toDataUrl(ownerRgba(selected.map(p => ({ values: p.values, color: playerColor(p.color) })), shape, level), shape.grid);
```

- 用 `useMemo` 缓存每名选手的 `values` 和生成的图片，依赖为地图、阵营、阶段、视图、子筛选、sigma、楼层。勾选或取消一名选手时，不要重算其他人。
- `src/components/HeatmapCanvas.tsx`：
  - props 为 `map`、`level`、`overlays: { key: string; url: string }[]`、`markers?: { x: number; y: number; color: string; title: string }[]`。
  - 渲染 `<svg viewBox="0 0 1024 1024">`。底图在 level 1 时用 `${BASE_URL}radars/${map}_lower.png`，否则用 `${map}.png`，加载失败时显示纯色背景。
  - 每个 overlay 渲染为 `<image href={url} width=1024 height=1024 preserveAspectRatio="none" style={{imageRendering: "auto"}}>`，依次叠放。markers 用空心圆加 `<title>`。

## 入口（改动现有文件，每个都输出完整文件）

- `src/App.tsx`：新增路由 `heatmaps` 和 `heatmaps/:slug`。它们不属于某张地图，与 `/:map/...` 平级，放在 `*` 路由之前。
- `src/components/Layout.tsx`：顶部主导航（"地图"旁边）新增全局入口"战队热力图"（`ui.nav_heatmaps`），指向 `/heatmaps`。
- `src/pages/Team.tsx`：页头加一个按钮"热力图"，指向 `/heatmaps/<slug>?map=<当前地图>`。
- `src/pages/Players.tsx`：每张选手卡片加一个链接"热力图"，指向 `/heatmaps/<该选手队伍的 slug>?map=<map>&players=<steamid>`。队伍 slug 的生成规则与后端一致：小写，非字母数字的字符替换成 `-`，去掉首尾的 `-`。
- `src/pages/Lineups.tsx`：支持 `?id=<lineup_id>`。打开页面时预先选中这条道具，并把它的卡片滚动到可见位置。如果当前筛选条件会把它隐藏，就放宽筛选：阵营和类型设为"全部"，最少使用次数设为 1。

## 新文件

- `src/pages/HeatmapTeams.tsx`：战队选择页
- `src/pages/TeamHeatmap.tsx`：主页面
- `src/components/HeatmapCanvas.tsx`
- `src/components/MapSwitcher.tsx`：箭头切换器，键盘支持也写在这里
- `src/components/PlayerChips.tsx`
- `src/heatmap.css`

## 文案键（交付末尾给出 zh、en 两个 JSON 片段，保持下面的嵌套结构）

```
ui.nav_heatmaps
heatmap.title, heatmap.pick_team, heatmap.search, heatmap.maps_count, heatmap.matches, heatmap.team_not_found, heatmap.back
heatmap.prev_map, heatmap.next_map, heatmap.map_caption（用 {matches}、{t}、{ct} 占位）
heatmap.side, heatmap.players, heatmap.select_all, heatmap.select_none, heatmap.low_sample, heatmap.rounds（用 {n} 占位）
heatmap.view.presence, heatmap.view.holding, heatmap.view.fights, heatmap.view.utility
heatmap.util.all, heatmap.util.smoke, heatmap.util.flash, heatmap.util.molotov, heatmap.util.he
heatmap.phases, heatmap.phase.early, heatmap.phase.mid, heatmap.phase.post
heatmap.mode.stack, heatmap.mode.owner, heatmap.sigma, heatmap.level.upper, heatmap.level.lower
heatmap.unit.seconds, heatmap.unit.count, heatmap.per_round
heatmap.setup, heatmap.zones, heatmap.holds, heatmap.show_holds, heatmap.hold_line（用 {place}、{sec}、{rounds} 占位）
heatmap.fights, heatmap.kpr, heatmap.dpr, heatmap.openings, heatmap.utility, heatmap.util_spots, heatmap.to_lineup
heatmap.no_data, heatmap.help
```

`heatmap.help` 用 3 到 5 句说明以下几点：
- 颜色代表选手，颜色越深表示越常出现；
- 数据只统计枪局，并去掉开局 5 秒；
- 四个视图各自的含义；
- 道具只看落点，想学怎么扔可以去道具库。

## 交付格式

- 每个文件单独一个代码块，代码块上一行写 `### 文件: web/路径`，内容必须完整，不要写"其余不变"。
- 最后给出 zh、en 两个文案 JSON 片段，以及不超过 5 行的取舍说明。

## 验收标准（Claude 会逐条检查）

- [ ] `npm run build` 零 TypeScript 错误；没有新增依赖；types.ts、heatmap.ts、data.ts、styles.css 没有改动
- [ ] 示例数据下，能从 `#/heatmaps` 选到 Vitality，并看到五名选手五种颜色的热力图，控制台没有报错
- [ ] 真实数据下（多张图），左右箭头和键盘方向键都能切换地图，URL 同步变化，刷新后状态不丢
- [ ] 勾选或取消选手、切换阵营、视图、阶段、模式后，图像立即更新
- [ ] 选手卡片里的"去道具库看怎么扔"能打开道具库，并选中对应的道具
- [ ] 375px 宽度下没有横向滚动条
