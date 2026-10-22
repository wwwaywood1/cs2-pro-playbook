# GPT-26 v3.1 前端逐项报告

范围：仅修改 `web/` 和本报告；未修改 `playbook/`、`data/`、`config/` 或后端测试。没有新增 npm 依赖，也没有运行数据同步/导出。

1. **分段控件折行 — 已实现，浏览器尺寸验收待运行。**
   - `web/src/hud.css`：共享轨道改为 `inline-flex`、`width: max-content`；按钮 `white-space: nowrap`、`flex: 0 0 auto`、`padding: 6px 12px`。极窄容器允许轨道内横向滚动。
   - `web/src/styles.css`：筛选组保持内容宽度，由外层 flex 行在组之间换行。
   - 保留 `Segmented.tsx` 的方向键/Home/End 导航和 reduced-motion 高亮行为。
   - `web/e2e/smoke.py::check_segmented_layout` 对路由操作前后可见的所有分段按钮增加 1440×900、1280×800 的单行、无收缩、无截字检查；原有 375px 溢出检查保留。

2. **TeamsHub 选手布局 — 已实现，首屏几何验收待运行。**
   - `web/src/pages/TeamsHub.tsx`：地图图层/阶段放入 `.hub-map-main`，紧接地图正上方；六维图移至地图和 WPA 面板之后。
   - `web/src/teams-hub.css`：地图面板改为单列，紧凑的阵营切换和地图筛选组减少首屏高度；立绘栏在桌面滚动时 sticky。保留完整诗词及其现有全强度样式。
   - 地图继续使用 `HubRadar` 的剩余视口高度测量。烟测新增两种桌面尺寸下控件与完整地图同时位于首屏、六维图仍可键盘聚焦和切换阵营的检查。

3. **战术意图标签与进点时间差 — 已实现。**
   - `web/src/pages/Tactics.tsx`：`round6.badge_fake` / `badge_sync_pinch` / `badge_rush` 在卡片标题旁渲染，折叠后仍在；时间差改用 `round6.entry_gap`。
   - `web/src/tactics.css`：标题/标签可在元素之间换行，标签内部不折字。
   - 烟测覆盖三个标签的准确文案及折叠状态。

4. **悬停 KPR 口径 — 已实现。**
   - GPT-25 报告在本次交接时尚未出现，采用任务明确允许的 fallback：悬停与选手页都通过 `TeamsHub.tsx::summaryRate` 读取该图、该队、该选手的热力图摘要 `T.fights.kills_pr`。
   - 悬停明确写出 `T 方每回合`，与点击后默认 T 方的选手页一致；CT 页继续使用对应 CT 摘要。
   - 移除旧悬停对 profile `kpr` 的依赖。烟测增加悬停数值与进入选手页 KPR 的一致性断言。

5. **回放弹窗 — 已实现。**
   - `web/src/components/RoundReplay.tsx`：在实际屏幕像素下检测存活点距离 `<18px`，短名按 0、+10、−10、+20、−20…px 排列，避免出生点堆叠；选中/悬停全名沿用该错位。
   - 事件文本使用 `round6.event_kill` / `event_util` / `event_util_noplace` / `event_plant`，时间统一调用 `replayMath.ts::roundClock`，下包后采用 40 秒炸弹倒计时。显示阵营、名字、落点、爆头、WPA；击杀还保留武器。
   - 默认隐藏闪光，勾选 `round6.event_filter_all` 后显示；标题显示当前关键/全部事件模式。
   - `web/src/types.ts` 的 side/place/plant.by 为可选：旧数据优先从 actor 推导阵营，无落点时使用 noplace 文案，无名字时显示 `—`。
   - 删除 scrubber 下的独立标记轨；在 T 胜率曲线对应秒数的插值高度绘制 `× / ☁ / 💣`，使用 `round6.wp_marker_legend`。保留点击及 Enter/Space 跳转。
   - 未添加朝向视锥；当前数据没有 yaw，按任务要求保持范围外。
   - 烟测新增出生点重叠、曲线上标记位置、关键/全部事件、倒计时及旧字段 fallback 检查。

6. **道具地图选点清除 — 已实现。**
   - `web/src/components/Radar.tsx`：选点激活时在雷达标题旁显示 `round6.map_pick_clear`；雷达上方显示 `round6.map_pick_active` 与当前筛选数量，移除底部旧清除入口。
   - 原有 `Lineups.tsx` 的 Esc 清除与 landing URL 状态逻辑保留。
   - 烟测覆盖按钮位于地图上方、状态、按钮清除、Esc 清除及结果恢复。

7. **文案 — 已完成。**
   - `delegation/inputs/copy_round6.json` 完整复制到 `web/src/i18n/zh.json` 的 `round6`；`en.json` 同步复制。
   - JSON 精确相等检查通过。

8. **验证与交接。**
   - 生产构建通过：`PATH='/Users/stephen/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:'"$PATH" node /private/tmp/npmcli/package/bin/npm-cli.js --prefix web run build`。等价项目脚本为 `cd web && npm run build`；包含 TypeScript 检查和 Vite 打包。
   - 最终全量 `.venv/bin/python -m pytest -q`：**234 passed, 2 skipped, 1 warning**（24.95s）。日志：`/private/tmp/gpt26-pytest.log`。warning 为 joblib 无法识别物理核数而使用逻辑核数。
   - `.venv/bin/python -m pytest -q tests/test_smoke_routes.py`：**15 passed**；`python -m py_compile web/e2e/smoke.py` 通过。
   - 真实 ReplayViewer 的 React 静态渲染断言通过：10 个同坐标标签错位、分数秒 WP 插值位置、击杀/烟/下包/HE 文案、旧字段缺省、闪光过滤和死亡移除。临时检查脚本：`/private/tmp/gpt26-render-check.cjs`。
   - **浏览器烟测未完成，不能据此声称视觉验收通过。** 本环境 `http.server` 绑定端口返回 `PermissionError: [Errno 1] Operation not permitted`，Chromium 启动返回 `bootstrap_check_in ... MachPortRendezvousServer ... Permission denied (1100)`；日志 `/private/tmp/gpt26-smoke.log`。未改变任何系统安全设置。
   - 下一步在允许监听 localhost、启动 Chromium 的 CLI 环境执行 `python3 -m http.server 4173 --directory web/dist`，另一个终端执行 `python3 web/e2e/smoke.py http://localhost:4173 --shots /tmp/gpt26-shots`，完成 1440×900、1280×800 和移动端回归。烟测默认按项目文档使用 sample 数据；本次没有覆盖并行导出的数据。
