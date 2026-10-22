"""Record a ~3 min captioned walkthrough of the site (Falcons showcase) with Playwright.

    cd web && npx vite preview --port 4173   # build with real data first
    python scripts/record_walkthrough.py     # -> /tmp/claude-0/walk/raw/*.webm, then ffmpeg to mp4
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
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir="/tmp/claude-0/walk/raw",
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

        # 1 home + command palette
        pg.goto(BASE + "#/"); wait(2.5)
        cap("首页：7 张图池地图", "每张卡片显示 T / CT 回合胜率和最常用的进攻套路；Cache 暂无数据（即将上线）"); wait(2)
        glide(300, 400); wait(1); glide(700, 420); wait(1.5)
        def palette():
            cap("新：Ctrl+K 全站搜索", "地图、套路（按点位名）、道具（起点 → 落点）、战队、选手，回车直达")
            pg.keyboard.press("Control+k"); wait(1.2)
            pg.keyboard.type("NiKo", delay=140); wait(1.8)
            pg.keyboard.press("Control+a"); pg.keyboard.type("Window", delay=120); wait(2.2)
            pg.keyboard.press("Escape"); wait(1)
        safe("palette", palette)
        # 2 team page + dates
        cap("点击导航「战队」，进入战队总览"); to(pg.get_by_role("link", name="战队").first); wait(0.8); pg.get_by_role("link", name="战队").first.click(); wait(2.5)
        cap("选择样板战队 Falcons")
        card = pg.locator(".hub-team-card", has_text="Falcons").first; to(card); wait(1); card.click(); wait(3.5)
        cap("战队页：队标进场，各图胜率依次飞入", "颜色区分强弱图，并标出「王牌图 / 短板图」"); wait(2)
        for name in ["Dust II", "Anubis", "Ancient"]:
            safe(name, lambda: (to(pg.locator(".hub-map-card", has_text=name).first, 15), wait(0.8)))
        def dates():
            sm = pg.locator(".hub-team-results > summary").first; to(sm); wait(0.6); sm.click(); wait(1)
            res = pg.locator(".hub-results").first; wait(0.5)
            cap("新：每场比赛都带时间标签，按时间从新到旧排序", "精确到日 / 只知道赛事（标注 ≈）；数据截至 2026-10-14"); wait(3)
            btn = res.locator("button", has_text="近 3 个月").first; to(btn, 15); btn.click(); wait(2.2)
            cap("时间筛选：近 3 个月 / 近 1 个月，看新阵容最近的状态")
            btn = res.locator("button", has_text="近 1 个月").first; to(btn, 15); btn.click(); wait(2.2)
            btn = res.locator("button", has_text="全部").first; to(btn, 15); btn.click(); wait(1)
            pg.mouse.wheel(0, -2000); wait(1.2)
        safe("dates", dates)
        cap("点击 Mirage，查看这支队在这张图上的打法")
        m = pg.locator(".hub-map-card", has_text="Mirage").first; to(m); wait(0.8); m.click(); wait(3.5)
        cap("地图页：回合胜率、T / CT 胜率、平均进点时间", "AI 点评中的数字全部来自数据并经过校验；道具名可点击"); wait(3)
        pg.mouse.wheel(0, 380); wait(2)
        cards = pg.locator(".hub-player-card")
        cap("5 名选手：悬停时人物前移变亮，下方显示 T 开局最常站的点位")
        for i in [0, 2, 4, 3]:
            safe("card", lambda: (to(cards.nth(i), 15), wait(0.9)))
        cap("点击 NiKo：出场动画 + 定场诗", "定场诗自上而下逐列展开，全亮度保留")
        cards.nth(3).click(); wait(6)
        cap("v3.1：图层 / 阶段按钮移到地图正上方，一屏内就能切换并看到完整地图", "悬停与选手页的每回合击杀统一为同一口径"); wait(3.5)
        def radar6():
            fig = pg.locator(".player-radar6").first; to(fig); wait(1)
            cap("新：6 维风格画像", "首杀倾向、道具投入、补枪、残局、站位深度等；悬停看百分位和定义")
            dots = fig.locator(".radar6-dot")
            for i in range(min(4, dots.count())):
                to(dots.nth(i), 12); wait(1.1)
        safe("radar6", radar6)
        def ghost():
            g = pg.locator("label.ghost-toggle").first; to(g); wait(0.6)
            cap("新：对比本图同阵营职业平均", "琥珀色 = 比平均多站，青色 = 比平均少站"); g.click(); wait(3)
        safe("ghost", ghost)
        for label, txt in [("中期控图", "切换阶段：中期控图"), ("下包后/残局", "切换阶段：下包后 / 残局")]:
            safe(label, lambda: (cap(txt), to(pg.get_by_role("button", name=label).first, 15), pg.get_by_role("button", name=label).first.click(), wait(2)))
        safe("ct", lambda: (cap("切换到 CT 方：颜色、数据、热力图同步切换"), to(pg.get_by_role("button", name="CT").first, 15), pg.get_by_role("button", name="CT").first.click(), wait(2.5)))
        cap("回到 Falcons 的 Mirage 页"); pg.keyboard.press("Escape"); wait(1.5); pg.goto(BASE + "#/teams-hub?team=falcons&map=de_mirage&side=T"); wait(3)
        # 3 archive + replay
        def replay_from_archive():
            if "map=de_mirage" not in pg.url or "player=" in pg.url:
                pg.goto(BASE + "#/teams-hub?team=falcons&map=de_mirage&side=T"); wait(3)
            summ = pg.locator("summary", has_text="本图比赛记录").first
            summ.scroll_into_view_if_needed(); wait(0.8)
            cap("本图比赛记录：每场标注日期，按回合画出胜率涨跌", "绿 = 胜率上升，红 = 下降；虚线是半场")
            to(summ); summ.click(); wait(1.2); pg.mouse.wheel(0, 500); wait(3)
            bar = pg.locator("g.winprob-round[role=button]").nth(8)
            cap("点击任意一根柱子：打开这一回合的 2D 回放"); to(bar, 20); wait(1); bar.click(); wait(2)
            cap("v3.1 回放：出生点名字自动错开，事件列表改为倒计时 + 阵营 + 谁 → 做了什么 → 在哪", "例：1:31 [CT] NiKo 投掷 警家火；击杀附胜率变化；闪光默认隐藏")
            play = pg.locator("button", has_text="播放").first
            if play.count(): to(play); play.click()
            wait(6)
            sp = pg.locator("button", has_text="4×").first
            if sp.count(): cap("4 倍速；× 击杀 / ☁ 烟雾 / 💣 下包 直接标在 T 方胜率曲线上"); to(sp, 15); sp.click()
            wait(5)
            cap("快捷键：K 跳到下一次击杀，P 跳到下包，空格暂停"); pg.keyboard.press("Space"); wait(0.6)
            ev = pg.locator("label", has_text="全部事件").first
            if ev.count(): cap("勾选「全部事件（含闪光）」显示完整流水"); to(ev, 15); ev.click(); wait(2); ev.click(); wait(0.5)
            pg.keyboard.press("k"); wait(2); pg.keyboard.press("k"); wait(2); pg.keyboard.press("p"); wait(2.5)
            cap("按 Esc 关闭回放"); pg.keyboard.press("Escape"); wait(2)
        safe("replay", replay_from_archive)
        # 4 tactics
        cap("进入「战术」页：Mirage 的 T 方进攻套路"); pg.goto(BASE + "#/de_mirage/tactics"); wait(3.5)
        cap("选中的套路：道具按投掷顺序排列，注明投掷位置", "v3.1：意图标签（⚡ 一波流 / ✂️ 多向夹击）显示在卡片标题旁，折叠时也可见"); wait(4)
        def intent():
            b_ = pg.locator(".recipe-intent").first; to(b_); wait(2)
        safe("intent", intent)
        rows = pg.locator(".tactics-route-row")
        for i in range(min(3, rows.count())):
            safe("route", lambda: (cap("v3.1：路线名按实际画出的路径命名 —— a = A1 斜坡主攻线，b = A二楼线", "悬停只高亮这一条"), to(rows.nth(i), 15), wait(1.8)))
        links = pg.locator(".tactics-recipe-details [data-map-link]")
        for i in range(min(3, links.count())):
            safe("link", lambda: (cap("悬停道具行：地图上对应道具同步高亮"), to(links.nth(i), 15), wait(1.3)))
        def recipe_bind():
            btn = pg.locator("button", has_text="复制整套爆弹练习脚本").first; to(btn); wait(0.6)
            cap("新：一键复制整套爆弹练习脚本", "粘贴到控制台，每按一次小键盘回车，依次传送到下一颗道具的投掷位置"); btn.click(); wait(3)
        safe("recipe_bind", recipe_bind)
        def example():
            ex = pg.locator("details summary", has_text="示例").first
            cap("示例回合：每套爆弹都能直接看真实比赛回放"); to(ex); ex.click(); wait(1.2)
            rb = pg.locator("button", has_text="回放").first; to(rb); rb.click(); wait(1.5)
            play = pg.locator("button", has_text="播放").first
            if play.count(): play.click()
            cap("按 G 跳到进点时刻"); wait(3); pg.keyboard.press("g"); wait(6)
            pg.keyboard.press("Escape"); wait(1.5)
        safe("example", example)
        def other():
            toggles = pg.locator(".tactics-recipe-toggle")
            t3 = toggles.nth(3); cap("换一套爆弹：左侧地图、标题、路线同步切换"); to(t3); t3.click(); wait(3.5)
        safe("other", other)
        # 5 lineups
        cap("进入「道具库」：分段按钮不再竖排折行；列表每次加载 60 颗，Mirage 共 2,443 颗"); pg.keyboard.press("Escape"); pg.keyboard.press("Escape"); pg.goto(BASE + "#/de_mirage/lineups"); wait(6); pg.set_default_timeout(15000)
        safe("must", lambda: (cap("只看「必学」：职业比赛里用过 50 次以上的道具"), to(pg.locator("button", has_text="必学").first), pg.locator("button", has_text="必学").first.click(), wait(2.5)))
        def pick():
            cl = pg.locator("g.landing-cluster").first
            cap("新：直接在地图上点选", "先点落点，地图随即显示扔到这里的所有投掷位置"); to(cl); wait(0.8); cl.click(); wait(2.5)
            cand = pg.locator("g.arrow-group").nth(2)
            cap("再点一个投掷位置，直接选中；地图上方出现「× 清除地图选点」"); to(cand); wait(0.8); cand.click(force=True); wait(2.5)
        safe("pick", pick)
        def bind():
            btn = pg.locator("button", has_text="复制练习绑定").first; to(btn); wait(0.6)
            cap("一键复制练习绑定（setpos + setang）", "粘贴到控制台，按小键盘回车即可回到投掷位置重练"); btn.click(); wait(3)
        safe("bind", bind)
        def clear():
            c = pg.locator("button", has_text="清除地图选点").first; cap("点「× 清除地图选点」回到全部道具"); to(c); wait(0.6); c.click(); wait(2)
        safe("clear", clear)
        arts = pg.locator("article[data-map-link]")
        for i in range(min(2, arts.count())):
            safe("art", lambda: (cap("悬停卡片：地图画出站位、朝向和落点"), to(arts.nth(i), 20), wait(1.8)))
        cap("演示结束", "CS2 职业战术手册 v3.1 · 样板战队 Falcons"); wait(3)
        ctx.close(); b.close()
run()
