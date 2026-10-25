"""Record a ~4 min captioned walkthrough (v4: 5 teams, orbit, CT defence, AI Lab) with Playwright.

    cd web && npx vite preview --port 4173   # build with real data first
    python scripts/record_walkthrough.py     # -> /tmp/claude-0/walk4/raw/*.webm, then ffmpeg to mp4
"""
import time
from playwright.sync_api import sync_playwright
BASE = "http://localhost:4173/"
CAP = """
window.__cap = (title, sub) => {
  let el = document.getElementById('__cap');
  if (!el) { el = document.createElement('div'); el.id='__cap';
    el.style.cssText='position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;pointer-events:none;'
      +'background:rgba(6,10,16,.88);border:1px solid rgba(255,255,255,.18);border-radius:14px;padding:12px 22px;'
      +'font:600 20px/1.4 "PingFang SC","Noto Sans CJK SC",sans-serif;color:#fff;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.5);max-width:1100px';
    document.body.appendChild(el); }
  el.innerHTML = '<div>'+title+'</div>' + (sub ? '<div style="font-weight:400;font-size:15px;color:#b8c4d0;margin-top:4px">'+sub+'</div>' : '');
};
window.__cur = null;
document.addEventListener('mousemove', (e) => {
  let c = document.getElementById('__cur');
  if (!c) { c = document.createElement('div'); c.id='__cur'; c.style.cssText='position:fixed;z-index:100000;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;border:2px solid #fff;background:rgba(255,255,255,.25);pointer-events:none;transition:transform .08s'; document.body.appendChild(c); }
  c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
}, true);
"""
def run():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir="/tmp/claude-0/walk4/raw",
                            record_video_size={"width": 1440, "height": 900})
        ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE.rstrip("/"))
        ctx.add_init_script(CAP)
        pg = ctx.new_page(); pg.set_default_timeout(6000)
        def cap(t, s=""): pg.evaluate("([t,s]) => window.__cap(t,s)", [t, s])
        def glide(x, y, steps=25): pg.mouse.move(x, y, steps=steps)
        def to(loc, steps=25):
            loc.scroll_into_view_if_needed(); bb = loc.bounding_box(); glide(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, steps); return loc
        def wait(s): pg.wait_for_timeout(int(s * 1000))
        def safe(label, fn):
            try: fn()
            except Exception as e: print("SKIP", label, repr(e)[:160])

        def scroll(px, steps=8):
            for _ in range(steps): pg.mouse.wheel(0, px/steps); wait(0.12)
        def hub(team, title, sub):
            pg.goto(BASE + f"#/teams-hub?team={team}"); wait(2.5); cap(title, sub); wait(4.5)
            glide(700, 450); wait(1)

        pg.goto(BASE + "#/"); wait(2.5)
        cap("CS2 职业战术手册 · 预览 v4（2026-10-25）", "7 张图池 · 5 支样板战队（Falcons / Vitality / Spirit / MOUZ / FURIA）· 新增 AI 实验室"); wait(4)
        glide(400, 450); wait(1); glide(1000, 450); wait(1.5)

        pg.goto(BASE + "#/teams-hub"); wait(2.5)
        cap("战队目录", "选择一支战队进入星轨沙盘"); wait(3)

        hub("falcons", "星轨沙盘 · Falcons", "中心是由队标像素采样生成的粒子队标；7 张地图卡绕轨道公转（约 52 秒一圈）")
        cap("地图卡：上半部分是游戏内实景截图（原色），下半部分是地图胜率与场次", "胜率着色按绝对值：≥60% 绿、50–60% 白、<50% 红；样本足够时标出「王牌图 / 短板图」"); wait(5)
        safe("hover", lambda: (lambda bb: (glide(bb["x"]+bb["width"]/2, bb["y"]+bb["height"]/2, 20), wait(3)))(pg.locator(".hub-orbit-node").nth(1).bounding_box()))
        cap("悬停一张卡片：轨道减速停下，显示 T/CT 回合胜率和代表战术预览"); wait(3.5)
        safe("enter", lambda: (pg.mouse.down(), pg.mouse.up(), wait(3.5)))
        cap("进入该地图：阵容、选手出场动画与定场诗、回合记录与 2D 回放"); wait(4); scroll(700); wait(2.5); scroll(700); wait(2.5)
        pg.keyboard.press("Escape"); wait(2)

        hub("vitality", "Vitality（138 张地图）", "每支战队的立绘统一抠图、按头宽缩放；队标重新着色为队伍主色")
        hub("spirit", "Spirit（129 张地图）", "")
        hub("mouz", "新增：MOUZ（146 张地图）", "最近三个月阵容 torzsi / Spinx / xertioN / xelex / PR 与立绘一一核对")
        hub("furia", "新增：FURIA（171 张地图）", "FalleN / yuurih / YEKINDAR / KSCERATO / molodoy；PGL Bucharest 2026（进行中）的比赛已收录")
        safe("fp", lambda: (pg.goto(BASE + "#/teams-hub?team=furia&map=de_mirage"), wait(3), cap("战队地图页新增「CT 站位指纹」", "该队在本图 6 类 CT 站位的使用比例 vs 全体职业队平均"), wait(3), scroll(900), wait(3), scroll(900), wait(3)))

        pg.goto(BASE + "#/de_mirage/tactics"); wait(3)
        cap("战术页 · T 进攻：套路道具、进点路线与核心落点", "悬停任意一行，地图上同步高亮"); wait(4); scroll(600); wait(3)
        pg.goto(BASE + "#/de_mirage/tactics"); wait(2)
        safe("ct", lambda: (pg.get_by_role("button", name="CT 防守").first.click(), wait(2.5)))
        cap("新增 · CT 防守：动态阵型聚类", "每张图把 CT 前 20 秒站位聚成 6 类（PCA + K-means），按人数分布命名，如「A2·中2·B1 均衡」"); wait(4.5)
        scroll(500); wait(1.5)
        cap("每一类：占比、CT 胜率及 95% 置信区间、在全起 / 经济局 / 比分落后等局面下的使用率", "左侧雷达图画出代表回合（实线）和样本轨迹（点线）"); wait(5); scroll(700); wait(3); scroll(700); wait(3)

        pg.goto(BASE + "#/lab"); wait(3)
        cap("新增 · 🧪 AI 实验室", "四个面板：阵型沙盘 · 胜率归因 · 空间控制反事实 · 模型验证与引用"); wait(4)
        safe("slider", lambda: (to(pg.locator("input[type=range]").first), wait(1)))
        cap("01 时空距离核：拖动时间轴看 CT 五人关系图变化；右侧是本图全部回合的 PCA 投影，点击散点切换", "注意：这是距离核加权，不是学习得到的注意力"); wait(5)
        scroll(300); wait(1)
        cap("02 精确分组 Shapley：把胜率预测拆成 6 组因素的贡献", "加性检验：基准 + 各组贡献 = 预测，残差为 0"); wait(5)
        scroll(800); wait(1.5)
        cap("03 空间控制场：橙 T / 蓝 CT；点「烟雾反事实」看一颗烟改变多少控图率", "直线距离近似，不含导航网格，不是因果推断"); wait(5)
        safe("smoke", lambda: (pg.get_by_role("button", name="烟雾反事实").first.click(), wait(3)))
        cap("04 模型验证：5 折按比赛留出，615 场比赛；校准模型准确率约 75%，人数/时间基线 69.5%", "引用 6 篇已核实文献；TAGNet 论文结论只在黄框「论文结论（Dust2）」中出现"); wait(5); scroll(900); wait(4)

        pg.goto(BASE + "#/de_mirage/lineups"); wait(4)
        cap("道具库：按落点筛选职业道具，复制控制台指令即可复现"); wait(4); scroll(600); wait(3)
        pg.goto(BASE + "#/heatmaps"); wait(3)
        cap("战队热力图"); wait(3)
        pg.goto(BASE + "#/teams-hub?team=furia"); wait(3)
        cap("预览结束 · 请标出时间点给出意见", "已知暂缓：手机端、英文版"); wait(4)
        ctx.close(); b.close()

if __name__ == "__main__":
    run()
