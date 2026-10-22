/** Focused replay browser regression. Serve web/dist, then:
 * node web/e2e/view_cones.mjs http://localhost:4173
 * Requires Playwright and its Chromium browser (NODE_PATH may point at a shared install).
 */
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
const { chromium, expect } = createRequire(import.meta.url)("playwright");
const base = process.argv[2] ?? "http://localhost:4173";
// Optional dist directory: fulfill HTTP from disk when binding a server is restricted.
const localDist = process.argv[3] && resolve(process.argv[3]);
const fixture = {
  demo_id: "cone-test", round_num: 1, map: "de_mirage", duration: 2,
  teams: { T: "Falcons", CT: "Vitality" }, winner: "T",
  players: [{ name: "T player", side: "T", team: "Falcons" }, { name: "CT player", side: "CT", team: "Vitality" }],
  frames: [[[800, 300], [600, 400]], [[790, 310], [600, 400]], [[780, 320], null]],
  yaw: [[350, 90], [10, null], [30, null]],
  events: [{ t: 2, kind: "kill", by: 0, victim: 1, at: [600, 400], weapon: "ak47" }],
  wp_t: [],
};
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH });
const errors = [];
let checks = 0;
try {
  for (const reducedMotion of ["reduce", "no-preference"]) {
    for (const viewport of [{ width: 1440, height: 900 }, { width: 375, height: 812 }]) {
      const context = await browser.newContext({ reducedMotion, viewport });
      const page = await context.newPage();
      page.on("pageerror", (error) => errors.push(String(error)));
      if (localDist) await page.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (url.origin !== new URL(base).origin) return route.abort();
        const path = resolve(localDist, `.${decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname)}`);
        if (!path.startsWith(localDist + sep)) return route.fulfill({ status: 403 });
        const contentType = path.endsWith(".js") ? "text/javascript" : path.endsWith(".css") ? "text/css"
          : path.endsWith(".json") ? "application/json" : path.endsWith(".html") ? "text/html"
          : path.endsWith(".png") ? "image/png" : path.endsWith(".svg") ? "image/svg+xml" : "application/octet-stream";
        try { return await route.fulfill({ body: await readFile(path), contentType }); }
        catch { return route.fulfill({ status: 404 }); }
      });
      let legacy = false;
      await page.route("**/data/de_mirage/replay/cone-test/1.json", (route) => {
        const data = structuredClone(fixture);
        if (legacy) delete data.yaw;
        return route.fulfill({ json: data });
      });
      const open = async () => {
        await page.goto(`${base}/#/de_mirage/tactics?replay=cone-test:1`);
        await expect(page.locator(".replay-player")).toHaveCount(2);
        if (reducedMotion === "no-preference") await page.locator(".replay-controls > button").click();
        await page.locator(".replay-scrubber").fill("0");
      };
      await open();
      const cones = page.locator(".replay-view-cone");
      await expect(cones).toHaveCount(2); checks++;
      assert.equal(await cones.first().getAttribute("fill"), "#efad55");
      assert.equal(await cones.nth(1).getAttribute("fill"), "#62b5ff"); checks++;
      const radius = await cones.first().evaluate((el) => {
        const [, x, y] = el.getAttribute("d").match(/L ([\d.e+-]+) ([\d.e+-]+)/);
        return Math.hypot(Number(x), Number(y)) * Math.hypot(el.getScreenCTM().a, el.getScreenCTM().b);
      });
      assert.ok(Math.abs(radius - 30) < .1, `radius ${radius}px`); checks++;
      await page.locator(".replay-scrubber").fill("0.5");
      await expect(cones.first()).toHaveAttribute("transform", new RegExp(`rotate\\(${reducedMotion === "reduce" ? 350 : 0}\\)`)); checks++;
      await page.locator(".replay-scrubber").fill("1");
      await expect(cones).toHaveCount(1); // unknown CT angle stays hidden
      await page.locator(".replay-scrubber").fill("2");
      await expect(page.locator(".replay-player")).toHaveCount(1);
      await expect(cones).toHaveCount(1); checks++;
      if (reducedMotion === "reduce" && viewport.width === 1440) {
        await page.locator(".replay-scrubber").fill("0");
        if (process.env.VIEW_CONES_SCREENSHOT) await page.locator("dialog").screenshot({ path: process.env.VIEW_CONES_SCREENSHOT });
      }
      legacy = true;
      await page.reload();
      await expect(page.locator(".replay-player")).toHaveCount(2);
      await expect(cones).toHaveCount(0); checks++;
      await context.close();
    }
  }
  assert.deepEqual(errors, []); checks++;
  console.log(`PASS: ${checks} view-cone browser checks (desktop/mobile, motion/reduced, legacy).`);
} finally {
  await browser.close();
}
