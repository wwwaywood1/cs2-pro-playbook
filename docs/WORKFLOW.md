# 工作流程手册（2026-10 定稿）

这份手册把 Falcons 样板做下来的全部流程固定下来。之后加数据、上新战队、改网站，都按这里做。
分工规则见 `delegation/README.md`；数据设计见 `DESIGN.md`。

---

## 0. 角色和机器

| 谁 | 做什么 |
|---|---|
| 你（Mac） | 在 HLTV 下载比赛压缩包；提供队标、选手照片、定场诗；拍板设计取舍 |
| Claude（云端容器） | 总指挥：写任务书、核实数据、合并、浏览器冒烟测试、录演示视频 |
| Codex（经 PAL `clink`，在 Mac 上跑） | 多文件改动、解析/导出/pytest、长时间修改 |
| DeepSeek-flash（在家）/ MiniMax-M3.1-Flash（VT 校园网） | 文案、命名、数据核查、第二意见（PAL `chat`，约 60 秒内返回） |

数据和原始 demo 只在 Mac 上：`~/Downloads/cs2-pro-playbook/data/raw`（压缩包和 demo）、`data/parsed`（parquet）、`data/site`（网站 JSON）。

## 1. 加数据（每批比赛）

1. **下载**：在 HLTV 比赛页下载 demo 压缩包（`*-bo1/3/5-*.rar|zip`），放在 `~/Downloads` 即可。
2. **一条命令入库**：`bash scripts/refresh.sh`
   - 移动压缩包到 `data/raw/hltv/` → 解压导入（图池外的地图、重复文件跳过）→ 解析新 demo（含每秒朝向 yaw）→ 导出网站数据 → 生成战队点评的事实输入。
   - 跨来源重复（同一场从 HLTV 和别处各来一份）在导出时按「地图 + 双方 + 每回合胜方序列」去重，不会算两次。
3. **比赛日期**：导出时自动按 `config/events.json`（赛事起止日期）+ HLTV 比赛编号插值打标签。
   - 新赛事要先在 `config/events.json` 补一行（名称、起止日期）。
   - 需要精确日期的比赛写进 `config/match_dates.csv`（优先级最高）。
4. **队名**：导出报告里出现未知写法（如 `FLC`、`9z Globant`）→ 补到 `config/team_aliases.csv`。
5. **导出后核查**（Claude 派给 MiniMax/DeepSeek，读导出 JSON 找矛盾）：
   - 日期为空的比赛、未归并的队名、样本 < 5 场的队伍；
   - 同一队同一图的胜率/回合数是否和比赛记录一致；
   - 路线名是否与画出的路径一致（`tests/` 已有自动检查）。
6. **战队点评**：事实变了的队伍，点评会在导出时自动作废 → Claude 派 Codex/MiniMax 重写，`scripts/insight_text.py check` 校验每个数字。
7. **同步预览**：`cp -R data/site/. site-preview/data/`，然后 `python3 -m http.server -d site-preview 8000` 打开看。

## 2. 上一支新的「样板级」战队

1. 数据量：近 6 个月该队全部比赛，目标每张常打图 ≥ 8 场、总计 ≥ 40 张地图。
2. 素材（你提供）：
   - 队标 → `web/public/logos/teams/<slug>.png`（没有时显示中性盾牌）；
   - 选手照片 → Claude 统一抠图、补全半身、对齐身高与清晰度；
   - 定场诗（可选）→ `config/player_quotes.json`。
3. 检查清单：战队页 → 地图页 → 选手页 → 回放 → 战术 → 道具库，各点一遍；数字抽查 3 处对照比赛记录。

## 3. 网站改动（每一轮）

1. 收集意见（你转发其他 AI 的评审）→ Claude **先核实**每条说法（看数据、画图、读代码），分成「属实要改 / 不属实附数字反驳 / 暂缓」。
2. 写任务书 `delegation/GPT-xx_*.md`：后端（`playbook/`）和前端（`web/`）分开，可以并行派给两个 Codex；文案先让 MiniMax 写成 `delegation/inputs/copy_roundN.json`。
3. Codex 完成后交 `GPT-xx_report.md` + pytest 结果；它在 Mac 上开不了浏览器。
4. Claude 拉回代码，**两套数据各跑一遍冒烟测试**：
   - 样例数据：`python scripts/sync_web_data.py --samples` → 构建 → `python3 web/e2e/smoke.py http://localhost:4173`（应只剩已知的手机端失败）；
   - 真实数据：拷入 `data/site` → 构建 → 同一脚本（只看非样例断言的失败）。
   - 失败日志写回 `delegation/GPT-xx_smoke_failures.txt`，Codex 修，直到干净。
5. 提交推送 GitHub → 更新 Mac 的 `site-preview/`（`dist` + 数据）。
6. 录演示视频给评审：`scripts/record_walkthrough.py`（1440×900，带字幕）→ ffmpeg 转 mp4 → 每 12 秒一张关键帧 → `说明.txt`（本轮改动 + 逐条回应上轮意见 + 请评审标时间点）→ 打包 zip。

## 4. 不变的设计决定

- 桌面端 + 中文优先；手机端、英文版暂缓。
- 出场动画和定场诗保持全亮度（自上而下逐列展开），不因评审意见调暗。
- 道具看落点而不是投掷点；地图图池现役 7 张（Cache 暂无数据显示「即将上线」，不含 Overpass）。
- 评审说法与数据冲突时以数据为准，在说明里给出数字。

## 5. Mac ↔ 云端同步方式（给 Claude）

- 推到 Mac：容器里放到 `/mnt/user-data/outputs/<新目录>/` → `device_commit_files` → Mac 上 `tar --overwrite -xzf`。Mac 文件夹不允许删除，旧文件移到 `_to_delete/`。
- 拉回容器：Mac 上 `tar -czf _sync/x.tgz …` → `device_stage_files` → 容器里解压；> 25 MB 分卷。
- Mac 上解压中文名 zip：Python `zipfile`，文件名按 cp437 → utf-8 转换。
- PAL 调用超过 60 秒会显示超时，但任务仍在 Mac 上运行；用 `device_bash` 看报告文件是否出现，不要重复派发。
