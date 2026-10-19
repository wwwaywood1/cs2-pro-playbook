# DS-06：热力图页面（交给 DeepSeek，一次做完）

> 用法：
> 1. 新开一个 DeepSeek 对话，从分割线开始整段粘贴本文件。
> 2. **同时上传 8 个附件**（都在仓库里，路径如下）：
>    - `web/src/types.ts`（数据类型，末尾"heatmaps"一节是本任务用的）
>    - `web/src/heatmap.ts`（热力图计算函数，Claude 已写好并验证过）
>    - `web/src/data.ts`（数据加载函数，已包含热力图的三个加载函数）
>    - `web/src/App.tsx`
>    - `web/src/components/Layout.tsx`
>    - `web/src/components/Radar.tsx`（参考它的 SVG 写法）
>    - `web/src/pages/Players.tsx`
>    - `samples/site/de_mirage/heatmaps/teams/vitality.json`（真实数据样例）
> 3. 把 DeepSeek 的回复原样交回给 Claude。Claude 负责落盘、编译、浏览器测试和合并。

---

你是资深前端工程师。这个开源 CS2 数据网站已经有道具库、队伍页、选手页（Vite + React 18 + TypeScript strict，HashRouter，静态 JSON，无后端）。现在要加一个**热力图页面**：展示某个职业选手或队伍在地图上的活动分布，包括站位时间、驻守时间、开枪、投掷道具、击杀和阵亡。

## 硬性约束

- 不新增任何依赖。不要引入图表库、UI 库或 canvas 库。
- **不要修改** `src/types.ts`、`src/heatmap.ts`、`src/data.ts`。类型和计算函数直接 import 使用，不要重新实现。
- 新样式写在新文件 `src/heatmap.css`，由 `src/pages/Heatmaps.tsx` 用 `import "../heatmap.css";` 引入。**不要改 `src/styles.css`**，可以复用其中已有的 CSS 变量和类名（例如 `nav-link`、`stat-row`、`muted`）。
- 文案统一通过 `t("heatmap.xxx")` 取值。新增的文案键不要直接写进 i18n 文件，而是在交付末尾单独给两个 JSON 片段（中文、英文各一份），由 Claude 合并。键名见下文"文案键"。
- 所有数字遇到 `null` 显示为 "—"。375px 手机宽度下不能出现横向滚动条。

## 数据（结构见 types.ts 的 heatmaps 一节）

```
data/<map>/heatmaps/baseline.json          HeatmapBaseline：网格参数 + 全部队伍的平均分布（基线）
data/<map>/heatmaps/teams/<slug>.json      TeamHeatmap
data/<map>/heatmaps/players/<steamid>.json PlayerHeatmap
```

- 加载函数已经写在 `data.ts` 里：`getHeatmapBaseline(map)`、`getTeamHeatmap(map, slug)`、`getPlayerHeatmap(map, steamid)`。队伍和选手列表沿用 `getTeams(map)`、`getPlayers(map)`。
- 网格是 `grid × grid`（64×64），覆盖 1024×1024 的雷达图。`levels` 为 2 时（Nuke），第二层对应下层雷达图 `radars/<map>_lower.png`。
- 7 个图层（HeatLayer）：
  - `presence`：站位时间
  - `holding`：驻守时间，即每秒移动距离小于 40 单位的时间
  - `shots`：开枪
  - `util_throw`：道具出手位置
  - `util_land`：道具落点
  - `kills`：击杀位置
  - `deaths`：阵亡位置
- 3 个阶段（HeatPhase）：
  - `early`：开局 0–20 秒
  - `mid`：中期
  - `post`：下包后（对 CT 方来说是回防）
- 每个值都是"每回合"的数值。各图层单位不同，所以合成时先把每层换算成占自身总量的比例，再按权重相加。这一步 `heatmap.ts` 的 `combine` 已经实现，直接调用即可。

## 计算流程（全部用 heatmap.ts 里的函数）

```ts
const shape = { grid: baseline.grid, levels: baseline.levels };
const w = normalisedWeights(weights);
const subjectLayers = denseLayers(subject, side, phases, shape);
let values = combine(subjectLayers, w, shape);
if (mode === "vs_baseline") {
  const base = combine(denseLayers(baseline, side, phases, shape), w, shape);
  values = difference(values, base);
}
values = blur(values, shape, sigma);
const url = toDataUrl(values, shape, level, mode === "vs_baseline" ? "diverging" : "sequential");
```

用 `useMemo` 缓存计算结果，依赖为 subject、side、phases、weights、mode、sigma、level。拖动滑块时必须保持流畅（64×64 网格，计算量很小）。

## 要做的文件

### 1. `src/components/HeatmapCanvas.tsx`

- props：`map`、`dataUrl`、`level`、`label?`
- 渲染 `<svg viewBox="0 0 1024 1024">`：
  - 底图：`level === 1` 时用 `${BASE_URL}radars/${map}_lower.png`，否则用 `${map}.png`。图片加载失败时显示纯色背景，参考 Radar.tsx 的写法。
  - 叠加层：`<image href={dataUrl} x=0 y=0 width=1024 height=1024 preserveAspectRatio="none">`，加上 `style={{ imageRendering: "auto" }}`，让浏览器做平滑放大。
  - `label` 显示在左上角，例如"NAVI · T · 全阶段"。
- 宽度自适应容器，保持正方形。

### 2. `src/components/HeatmapControls.tsx`

受控组件，状态由页面持有。控件依次为：

- **阵营**：T / CT 两个切换按钮。
- **阶段**：early / mid / post 三个多选框，至少保留一个勾选。
- **预设**：四个按钮，点击后整组设置权重。
  - 默认：presence 1、shots 1、util_throw 1，等于 `DEFAULT_WEIGHTS`
  - 卡点：holding 1
  - 交火：shots 1、kills 1、deaths 1
  - 道具：util_throw 1、util_land 1
- **权重**：7 个图层各一个滑块，范围 0–3，步长 0.5。每个滑块旁显示当前数值，下方小字显示 `heatmap.layer_desc.<layer>`。另有一个"重置"按钮，恢复 `DEFAULT_WEIGHTS`。
- **模式**："绝对分布"或"与全部队伍对比"。对比模式下，在图例里说明红色表示"比平均多"、蓝色表示"比平均少"。
- **平滑**：sigma 滑块，范围 0–3，步长 0.2，默认 1.2。
- **楼层**：只在 `levels === 2` 时显示，选项为上层 / 下层。

### 3. `src/pages/Heatmaps.tsx`（路由 `/:map/heatmaps`）

- **选择对象**：一个下拉框，用 `<optgroup>` 分成"队伍"和按队伍分组的"选手"两组。选项值为 `team:<slug>` 或 `player:<steamid>`。没有选择时默认选第一个队伍。
- **URL 状态**：所有状态写进 query string，刷新或分享链接后能还原。使用 `useSearchParams`，参数如下：
  - `team=<slug>` 或 `player=<steamid>`
  - `side=T|CT`
  - `phases=early,mid,post`
  - `w=presence:1,shots:1,util_throw:1`
  - `mode=abs|vs`
  - `sigma=1.2`
  - `level=0|1`
  - `cmp=team:<slug>|player:<steamid>`（可选，并排对比的第二个对象）
  - 参数缺失或非法时用默认值，不能报错。
- **并排对比**：可选。选择第二个对象后，两张热力图并排显示，桌面端左右排列、手机端上下排列，共用同一套控件。
- **说明行**：每张图下方显示样本量和每回合数值。
  - 样本量用对象的 `n_matches` 和 `rounds[side]` 拼成"N 场 · M 回合"。
  - `n_matches < index.min_matches_reliable` 时，显示现有的 `LowSampleBanner` 组件。
  - 每回合数值用 `perRound(data, side, phases, layer)` 取值，只列出权重大于 0 的图层，格式例如"站位 72.1 秒/回合 · 开枪 11.2 发/回合 · 道具 2.5 颗/回合"。presence 和 holding 的单位是秒，其余是次数。
- **帮助**：页面底部有一段可折叠的说明，文案为 `heatmap.help`，解释图层含义、"每回合"的含义和权重的作用。
- **出错与空数据**：数据加载失败时显示现有的 `ErrorNotice`。所选阵营和阶段没有数据时，显示 `heatmap.no_data`。

### 4. 入口（改动现有文件，输出完整文件）

- `src/App.tsx`：新增路由 `:map/heatmaps`。
- `src/components/Layout.tsx`：地图导航里新增"热力图"（`ui.nav_heatmaps`），放在"选手"之后。
- `src/pages/Players.tsx`：每张选手卡片加一个链接"热力图"，跳到 `/<map>/heatmaps?player=<steamid>`。

### 5. `src/heatmap.css`

控件区和图并排的布局。热力图面板最大宽度 720px。

## 文案键（交付末尾给出 zh / en 两个 JSON 片段，保持下面的嵌套结构）

```
ui.nav_heatmaps
heatmap.title, heatmap.subject, heatmap.group_teams, heatmap.group_players
heatmap.side, heatmap.phases, heatmap.phase.early, heatmap.phase.mid, heatmap.phase.post
heatmap.weights, heatmap.reset
heatmap.preset.default, heatmap.preset.holding, heatmap.preset.fights, heatmap.preset.utility
heatmap.layer.<7 个图层名>, heatmap.layer_desc.<7 个图层名>
heatmap.unit.seconds, heatmap.unit.count, heatmap.per_round
heatmap.mode.abs, heatmap.mode.vs, heatmap.legend.more, heatmap.legend.less
heatmap.sigma, heatmap.level.upper, heatmap.level.lower
heatmap.compare, heatmap.compare_none, heatmap.sample, heatmap.no_data, heatmap.help
```

`heatmap.sample` 用 `{matches}`、`{rounds}` 占位。`heatmap.help` 用中文写 3 到 5 句，要讲清楚：每个图层的含义；数值是"每回合"的；合成前先把每层换算成比例，所以权重 1:1:1 表示三类信息各占同等分量。

## 交付格式

- 每个文件单独一个代码块，代码块上一行写 `### 文件: web/路径`，内容必须完整，不要写"其余不变"。
- 最后给出两个文案 JSON 片段（zh、en），以及不超过 5 行的取舍说明。

## 验收标准（Claude 会逐条检查）

- [ ] `npm run build` 零 TypeScript 错误；没有新增依赖；types.ts、heatmap.ts、data.ts、styles.css 没有改动
- [ ] 用示例数据打开 `#/de_mirage/heatmaps?team=vitality`，能看到热力图，控制台没有报错
- [ ] 拖动权重滑块、切换阵营或阶段后，图像实时更新；URL 同步变化，刷新后状态不丢
- [ ] "与全部队伍对比"模式下颜色为红蓝两色，图例正确
- [ ] 选手卡片上的热力图链接能跳到对应选手
- [ ] 375px 宽度下没有横向滚动条
