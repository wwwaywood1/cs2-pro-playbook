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
        ctx.add_init_script(CAP)
        pg = ctx.new_page()
        def cap(t, s=""): pg.evaluate("([t,s]) => window.__cap(t,s)", [t, s])
        def glide(x, y, steps=25): pg.mouse.move(x, y, steps=steps)
        def to(loc, steps=25):
            bb = loc.bounding_box(); glide(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2, steps); return loc
        def wait(s): pg.wait_for_timeout(int(s * 1000))

        pg.goto(BASE + "#/"); wait(2.5)
        cap("首页：7 张图池地图", "每张卡片显示 T / CT 回合胜率和最常用的进攻套路；Cache 暂无比赛数据"); wait(2)
        glide(300, 400); wait(1); glide(700, 420); wait(1.5)
        pg.mouse.wheel(0, 350); wait(2)
        cap("点击导航「战队」，进入战队总览"); to(pg.get_by_role("link", name="战队").first); wait(1); pg.get_by_role("link", name="战队").first.click(); wait(2.5)
        cap("选择样板战队 Falcons")
        card = pg.locator(".hub-team-card", has_text="Falcons").first; card.scroll_into_view_if_needed(); to(card); wait(1); card.click(); wait(3.5)
        cap("战队页：队标从模糊到清晰进场，各图胜率依次飞入", "颜色区分强弱图，并标出「王牌图 / 短板图」"); wait(2)
        for name in ["Dust II", "Anubis", "Ancient"]:
            m = pg.locator(".hub-map-card", has_text=name).first; to(m, 15); wait(0.9)
        cap("点击 Mirage，查看这支队在这张图上的打法")
        m = pg.locator(".hub-map-card", has_text="Mirage").first; to(m); wait(0.8); m.click(); wait(3.5)
        cap("地图页：回合胜率、T / CT 胜率、平均进点时间（数字滚动出现）", "下面是 AI 点评（数字全部来自数据并经过校验），道具名可以点击"); wait(3.5)
        pg.mouse.wheel(0, 380); wait(2)
        cap("5 名选手：悬停时人物前移变亮，其余人变暗")
        cards = pg.locator(".hub-player-card")
        for i in [0, 2, 4, 3]:
            to(cards.nth(i), 15); wait(0.9)
        cap("点击 NiKo：选手出场动画", "灯光扫入 → 人像由模糊推近 → 定场诗竖排逐字显现 → 数据面板滑入")
        cards.nth(3).click(); wait(5.5)
        cap("选手页：每回合胜率贡献 = 每场约多赢几个回合，并给出同图同阵营排名", "右侧热力图默认显示 T 方开局站位"); wait(4)
        for label, txt in [("中期控图", "切换阶段：中期控图"), ("下包后/残局", "切换阶段：下包后 / 残局")]:
            btn = pg.get_by_role("button", name=label).first; cap(txt); to(btn, 15); btn.click(); wait(2.2)
        btn = pg.get_by_role("button", name="道具落点").first; cap("切换图层：道具落点（图标即道具类型）"); to(btn, 15); btn.click(); wait(2.5)
        btn = pg.get_by_role("button", name="CT").first; cap("切换到 CT 方：颜色、数据、热力图同步切换"); to(btn, 15); btn.click(); wait(3)
        cap("按 Esc 回到上一层"); pg.keyboard.press("Escape"); wait(3)
        summ = pg.locator("summary", has_text="比赛").first
        summ.scroll_into_view_if_needed(); wait(0.8)
        cap("展开「本图比赛记录」：每场比赛按回合画出胜率涨跌", "绿 = 这回合胜率上升，红 = 下降；虚线是半场")
        to(summ); summ.click(); wait(1.2); pg.mouse.wheel(0, 500); wait(3)
        bars = pg.locator(".match-winprob rect, [class*=winprob] rect").nth(6)
        try: to(bars, 15); wait(2)
        except Exception: pass
        pg.mouse.wheel(0, 500); wait(2)
        cap("进入「战术」页：Mirage 的 T 方进攻套路"); pg.goto(BASE + "#/de_mirage/tactics"); wait(3.5)
        cap("选中的套路：道具编号 = 投掷顺序，标注常由谁投；橙色线是 T 方进点路线", "胜率变化：这套爆弹前后 T 方回合胜率的变化"); wait(4)
        rows = pg.locator(".tactics-route-row")
        for i in range(min(3, rows.count())):
            cap(f"悬停路线 {'abc'[i]}：只高亮这一条"); to(rows.nth(i), 15); wait(1.6)
        links = pg.locator(".tactics-recipe-details [data-map-link]")
        for i in range(min(3, links.count())):
            cap("悬停道具行：地图上对应道具同步高亮"); to(links.nth(i), 15); wait(1.4)
        toggles = pg.locator(".tactics-recipe-toggle")
        if toggles.count() > 3:
            t3 = toggles.nth(3); t3.scroll_into_view_if_needed(); cap("换一套爆弹：地图和路线跟着切换"); to(t3); t3.click(); wait(3.5)
        cap("进入「道具库」：所有职业选手用过的道具"); pg.goto(BASE + "#/de_mirage/lineups"); wait(3.5)
        must = pg.get_by_role("button", name="必学 ≥50次").first; cap("只看「必学」：职业比赛里用过 50 次以上的道具"); to(must); must.click(); wait(2.5)
        arts = pg.locator("article[data-map-link]")
        for i in range(min(3, arts.count())):
            cap("悬停卡片：地图画出站位、朝向和落点；可一键复制练习指令"); to(arts.nth(i), 20); wait(2)
        cap("演示结束", "CS2 职业战术手册 · 样板战队 Falcons"); wait(3)
        ctx.close(); b.close()
run()
