# GPT-04：持续集成与 Pages 部署（交给 GPT / Codex）

> 用法：在 Codex 里打开 GitHub 仓库 `wwwaywood1/cs2-pro-playbook`（main 分支），从分割线开始粘贴下面的内容。
> 注意：仓库是私有的。GitHub Pages 在私有仓库上需要付费账号，所以这里只做 CI 和一个"手动触发"的 Pages 部署工作流。等仓库公开或升级后，再打开 Pages。

---

`cs2-pro-playbook` is a Python pipeline (awpy + polars, `playbook/`) that exports static JSON (`data/site/`), plus a Vite + React + TypeScript site (`web/`) that reads it. Read `README.md`, `DESIGN.md` (› Site data contract), `scripts/sync_web_data.py`, `web/package.json`, `web/e2e/smoke.py`.

The site is gaining a heatmap page (another task, DS-06, is building it now). Write the smoke-test changes so new routes can be added later: keep the existing 24 checks passing and structure the script so adding a route check is one function.

Part A — GitHub Actions CI (`.github/workflows/ci.yml`), on push and pull request:
1. Python 3.11, install the package with `pip install -e ".[dev]"`, run `pytest -q`. The end-to-end test skips itself without a demo; that is fine.
2. Web: `cd web && npm ci && npm run build` using the committed sample data (`python scripts/sync_web_data.py --samples` first; it also copies radar images from awpy's data cache — make that step work in CI or make radars optional for the build, and say which).
3. Browser smoke test: serve `web/dist` and run `python3 web/e2e/smoke.py` with Playwright's Chromium (install it in the job). Upload screenshots as an artifact on failure (`--shots DIR`).
4. Keep the workflow fast (cache pip and npm). Target: under 6 minutes.

Part B — Pages deploy workflow (`.github/workflows/pages.yml`), `workflow_dispatch` only: build the site from `samples/site` (real data is not in the repo) and deploy with `actions/deploy-pages`. Document in README.md how to switch it to real data later (an artifact or a release asset produced locally by `python -m playbook run`).

Constraints: no new runtime dependencies; do not touch `playbook/` (other work is changing it). Deliverable: one PR (or patch) with the workflows, README updates, and the CI run result in the PR description.
