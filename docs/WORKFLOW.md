# 工作流程手册（2026-10-26 更新）

加数据、上新战队、改网站，都按这里做。数据设计见 `DESIGN.md`，数据来源与版权见 `docs/CREDITS.md`。

---

## 0. 机器与存储

| 位置 | 内容 |
|---|---|
| Mac `~/Downloads/cs2-pro-playbook` | 代码、`data/parsed`（parquet）、`data/site`（网站 JSON）、`web/public` 里的队标/立绘/地图背景（只在本地，不提交、不公开发布） |
| 移动硬盘 `/Volumes/My PSSD/cs2-pro-playbook-data/raw` | 原始 demo（`data/raw` 是指向这里的链接，`config/storage.toml [raw]`）。**解析和导出时硬盘要插着**；没插时 `refresh.sh` / `export` 会直接提示 |
| 移动硬盘 `…/hltv-archives` | HLTV 下载的原始压缩包（导入后自动移入，SHA-256 校验，`config/storage.toml [archive]`） |
| GitHub `wwwaywood1/cs2-pro-playbook`（私有） | 代码与配置；`data/` 与图片不入库 |

搬迁原始 demo 用 `scripts/relocate_raw.py`（`--copy` 校验复制 → `--switch` 改成链接 → `--finish` 逐个文件重新校验后删除本机旧副本）。

## 1. 加数据（每批比赛）

**HLTV 只允许人工下载**（其 robots.txt 禁止自动访问 `/download/demo`，条款据报禁止抓取）。所以：下载靠你点击，其余全部自动。

1. **计划**（Claude 做）：按 `config/hltv.toml`（2026 年起、一线赛事、按 HLTV 热度星级排序）列出还没有的比赛，写成
   - `_sync/<队>_plan.json`（每场的比赛编号、demo 编号、开赛时间、赛事、地图）
   - `_sync/<队>_queue.html`（下载清单页）。
   - 比赛列表来自 bo3.gg / Liquipedia，或你在浏览器里保存的 HLTV 战绩页（`scripts/hltv_plan.py <队> --results-html 页面.html`）。不会自动请求 HLTV。
2. **下载**（你做，约 10–15 分钟/队）：在 Safari 打开 `_sync/<队>_queue.html`，从上往下逐个点「下载 demo」，压缩包进 `~/Downloads`。点过的会变灰；已有的比赛不会列出。
3. **入库**（一条命令，Claude 可以替你在 Mac 上跑）：`bash scripts/refresh.sh`
   1. 把 `~/Downloads` 里的比赛压缩包移到 `data/raw/hltv/`（硬盘上）；
   2. 解压导入（图池外地图、重复 demo 跳过；`-p1/-p2` 分段自动拼接）；
   3. **精确日期**：按「赛事-队伍-队伍」把压缩包对应到计划里的比赛（同一赛事两队打两次时用地图区分），写入 `config/hltv_archives.json` 和 `config/match_dates.csv`；
   4. 原始压缩包移到硬盘 `hltv-archives`（校验后才删原件）；
   5. 解析新 demo → 导出网站数据（导出写到新目录再整体替换，不留旧文件）→ 生成战队点评的事实输入。
4. **队名**：导出报告里出现未知写法 → 补到 `config/team_aliases.csv`。
5. **新赛事**：`register_hltv_dates.py` 会按比赛日期自动补进 `config/events.json`（标记 `"source": "hltv-plan"`），有空时核对一下起止日期。
6. **战队点评**：事实变了的队伍，点评在导出时自动作废，Claude 重写，`scripts/insight_text.py check` 校验每个数字。

## 2. 上一支新的展示战队

1. 数据：该队 2026 年一线赛事的全部比赛（第 1 节）。
2. 图片（只在本地使用）：
   - `_sync/<队>_assets.txt` 列出队标和选手图的地址（bo3.gg / HLTV 图片 CDN），`bash scripts/team_assets.sh <队>` 下载一次；
   - 立绘：`python scripts/make_portraits.py <文件夹> --transparent --map 名字=steamid …`（透明底身体照，放大、统一头宽，输出 `web/public/players/<steamid>.png`）；steamid 来自 demo 里的选手；
   - 队标 → `web/public/logos/teams/<slug>.png`。
3. 把队名加进 `config/site.toml` 的 `showcase`：该队每一回合都有 2D 回放和胜率曲线。
4. 检查清单：战队页 → 地图页 → 选手页 → 回放 → 战术 → 道具库，各点一遍；数字抽查 3 处。

## 3. 网站改动

1. 收集意见 → 先核实每条说法（看数据、画图、读代码），分成「属实要改 / 不属实附数字反驳 / 暂缓」。
2. 改代码 → `pytest -q`、`cd web && npx tsc -b && npm run build`。
3. 冒烟测试：
   - 样例数据（CI 同款）：`python scripts/sync_web_data.py --samples` → 构建 → `python3 web/e2e/smoke.py http://localhost:4173 --samples`；
   - 真实数据：`python scripts/sync_web_data.py` → 构建 → `smoke.py`、`--orbit-only`、`--lab-only`，`node web/e2e/orbit_geometry.mjs`。
4. 提交推送；CI（`.github/workflows/ci.yml`）用样例数据跑 Python 测试、类型检查、构建和冒烟。

## 4. 不变的设计决定

- 桌面端 + 中文优先；手机端、英文版暂缓。
- 出场动画和定场诗保持全亮度。
- 道具看落点而不是投掷点；现役图池 7 张（含 Cache，不含 Overpass；Overpass 只在 AI 实验室作历史对照）。
- 统计结论要过显著性检验并控制多重比较；样本小的数字标明区间或不显示徽章。
- 评审说法与数据冲突时以数据为准，在说明里给出数字。

## 5. Mac ↔ 云端同步（给 Claude）

- 推到 Mac：`git archive HEAD | gzip > /mnt/user-data/outputs/<名字>.tgz` → `device_commit_files`（每次换新文件名）→ Mac 上 `tar -xzf`（只覆盖受版本管理的文件）。
- 拉回容器：Mac 上 `tar -czf _sync/x.tgz …` → `device_stage_files`（单文件 ≤ 400 MB）→ 容器里解压。
- 长任务（解析、导出、复制）用 Codex 在 Mac 本机跑：调用 60 秒显示超时但任务继续，用 `device_bash` 看日志；Codex 沙箱不联网、不能用 `ps`、不接受 `rm -f`。
