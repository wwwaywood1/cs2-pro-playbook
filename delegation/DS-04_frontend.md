# DS-04：网站前端 v1（交给 DeepSeek，分三个阶段）

> 用法：
> 1. 先完成 DS-03（文案），把它的两个 JSON 保存为 `web/src/i18n/zh.json` 和 `web/src/i18n/en.json`。
> 2. 新开一个 DeepSeek 对话，从分割线开始粘贴本文件，**同时上传 3 个附件**：
>    - `web/src/types.ts`（数据类型，完整文件）
>    - `samples/site/de_mirage/lineups.json`
>    - `samples/site/de_mirage/teams/vitality.json`
> 3. 先只让它做“阶段 A”。把输出的所有文件原样交回给 Claude，Claude 会落盘、编译、修错。确认通过后再发“继续阶段 B”，然后是阶段 C。

---

你是资深前端工程师。请为一个开源 CS2 数据网站实现前端。网站把职业比赛数据整理成普通玩家能用的内容：职业道具库、队伍战术、选手打法。所有数据都是预先算好的静态 JSON，网站只负责读取和展示，没有后端。

## 技术约束（必须遵守）

- Vite + React 18 + TypeScript（strict）。只允许以下依赖：`react`、`react-dom`、`react-router-dom`、`vite`、`@vitejs/plugin-react`、`typescript`、`@types/react`、`@types/react-dom`。**不要**引入 UI 库、CSS 框架、图表库或状态管理库。
- 路由用 `HashRouter`（部署在 GitHub Pages，不配服务端）。`vite.config.ts` 设 `base: "./"`。
- 数据从 `${import.meta.env.BASE_URL}data/...` 读取，雷达图从 `${import.meta.env.BASE_URL}radars/<map>.png` 读取。这两个目录由脚本生成，不需要你创建。
- 数据类型全部来自附件 `src/types.ts`。直接 import，**不要修改、不要重新定义**。
- 文案来自 `src/i18n/zh.json` 和 `src/i18n/en.json`（已经存在）。通过 `t("ui.copy_cmd")` 这样的点路径取值；键不存在时返回键名本身，不能报错。默认中文，语言选择存在 localStorage（读写都要包 try/catch）。
- 样式写在一个 `src/styles.css` 里，颜色用 CSS 变量。深色战术风：背景深灰蓝；T 方用琥珀色，CT 方用蓝色；四类道具用固定颜色（smoke 灰、flashbang 黄、molotov 橙红、he 绿）。375px 手机宽度下也要能用。
- 所有数字显示前处理 `null`，显示为 "—"。比例显示为百分比、取整。

## 数据文件（结构见 types.ts）

```
data/index.json                    SiteIndex
data/<map>/meta.json               MapMeta
data/<map>/teams.json              TeamSummary[]
data/<map>/teams/<slug>.json       TeamProfile
data/<map>/players.json            PlayerProfile[]
data/<map>/lineups.json            Lineup[]
```

- 坐标：`Lineup.throw.radar_x/radar_y` 和 `land.radar_x/radar_y` 已经换算成 1024×1024 雷达图上的像素坐标，直接画即可。
- 样本量：每个队伍画像都有 `n_matches` 和 `low_sample`。`low_sample` 为 true 时，页面顶部必须显示警告条，文案为 `ui.low_sample_warning`（把 `{n}` 替换为 `n_matches`）。
- 点位名（如 `TopofMid`）显示时用 `callout.<map>.<名称>` 翻译，找不到就显示原名。

## 阶段 A：骨架与数据层

文件：
- `package.json`（scripts: `dev`, `build` = `tsc -b && vite build`, `preview`）、`vite.config.ts`、`tsconfig.json`、`index.html`
- `src/main.tsx`、`src/App.tsx`（路由：`/` 首页，`/:map/lineups` 道具库，`/:map/teams` 队伍列表，`/:map/teams/:slug` 队伍页，`/:map/players` 选手页）
- `src/data.ts`：`getIndex()`、`getMeta(map)`、`getTeams(map)`、`getTeam(map, slug)`、`getPlayers(map)`、`getLineups(map)`。带内存缓存，返回 Promise，类型来自 types.ts。再提供一个 `useData(fn, deps)` hook，返回 `{data, error, loading}`。
- `src/i18n.ts`：`t(key, vars?)`、`calloutLabel(map, name)`、`useLang()`。
- `src/components/Layout.tsx`：顶栏（站名、当前地图下的导航：道具库、队伍、选手；语言切换），底部显示 `generated_at` 和数据来源。
- `src/components/LowSampleBanner.tsx`
- `src/pages/Home.tsx`：地图卡片，显示 display_name、n_matches、n_lineups，点击进入该图的道具库。
- 阶段 B、C 的页面先放占位组件，保证能编译。
- `src/styles.css`

## 阶段 B：职业道具库（最重要的页面）

- `src/components/Radar.tsx`：props 为 `map`、`lineups`、`selectedId`、`onSelect`。渲染 `<svg viewBox="0 0 1024 1024">`，底图用 `<image href=radar>`。每条道具画一条出手点→落点的箭头，颜色按道具类型；出手点画小圆点；被选中的加粗高亮，其余变淡。点击箭头选中。SVG 宽度自适应容器，保持正方形。
- `src/pages/Lineups.tsx`：
  - 筛选：阵营（T/CT/全部）、道具类型（多选）、落点路线（A/MID/B/全部）、最少使用次数（数字，默认 2）、投掷技巧。
  - 布局：桌面端左侧雷达、右侧卡片列表；手机端上下排列。
  - 卡片内容：出手点 → 落点（中文点位名）、道具类型标签、投掷技巧、被职业选手用过 `n_throws` 次（`n_matches` 场）、使用者（`throwers`）、所在回合胜率、通常第几秒生效。还要有“复制练习指令”按钮：用 `navigator.clipboard.writeText(practice_cmd)` 复制，失败时退回到选中文本；复制后按钮显示 `ui.copied`，持续 1.5 秒。按钮旁边小字显示 `ui.practice_hint`。
  - 卡片和雷达联动：点卡片高亮雷达上对应的箭头，点箭头时把对应卡片滚动到可见位置并高亮。
  - 列表默认按 `n_throws` 降序。

## 阶段 C：队伍与选手

- `src/pages/Teams.tsx`：队伍列表，显示 T/CT 胜率、样本场数，`low_sample` 的队伍加标记。
- `src/pages/Team.tsx`：
  - 头部：队名、比赛列表（对手和比分）、低样本警告。
  - T/CT 两个标签页：
    - 共有：胜率、首杀胜率、平均首杀时间；“常用站位”表，列出 `setups_15s`、`setups_30s`，每行包含站位指纹、次数、占比、胜率，表头附 `ui.setup_shape_help` 的问号提示。
    - T 方：下包点分布（横向条形，用纯 CSS/SVG 画）、执行节奏 `execute_timing`、执行方向 `execute_lane`、平均下包时间。
    - CT 方：被下包次数、回防胜率、堆点率。
  - 经济表：side × buy_type 的回合数和胜率。
- `src/pages/Players.tsx`：按队伍分组的选手卡片。显示 kpr、首杀成功率、狙使用率、每回合道具数；角色标签用 `role.<role>` 翻译，鼠标悬停显示 `role_desc` 加判定依据（`metric` 翻译 + `value`）。T 方和 CT 方常站位置取 `lanes_15s` 的前两项。

## 交付格式（严格遵守）

- 每个文件单独一个代码块，代码块上一行写 `### 文件: web/路径`。
- 每个阶段只输出该阶段新增或改动的文件，并且每个文件都是**完整内容**，不要写“其余不变”。
- 阶段末尾用不超过 5 行说明：做了哪些取舍、有哪些已知问题。

## 验收标准（Claude 会逐条检查）

- [ ] `npm install && npm run build` 零 TypeScript 错误
- [ ] 用示例数据（Mirage，1 场比赛）能打开全部页面，控制台没有报错
- [ ] 低样本警告在队伍页正确显示（示例数据都是低样本）
- [ ] 复制按钮复制的内容与 `practice_cmd` 完全一致
- [ ] 375px 宽度下没有横向滚动条
- [ ] 没有引入约束之外的依赖；没有修改 types.ts
