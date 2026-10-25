# GPT-44 FURIA 比赛入库（派给 Codex，经 PAL clink）

Repo `~/Downloads/cs2-pro-playbook`. Same procedure as GPT-41 (`delegation/GPT-41_mouz_ingest.md`, report format `delegation/GPT-41_report.md`), now for **FURIA** (archives `*-bo1/3/5-*.rar|zip` in `~/Downloads` or a subfolder; touch nothing else there; preserve unrelated downloads). Logs in `_sync/gpt44/`. Wrap long runs in `caffeinate -i`.

1. `bash scripts/refresh.sh` with stage timings; scope the import to the FURIA archives (as GPT-41 did); broken demos don't stop the run. No other job is running — export immediately after parse (no GPT-39 gate this time).
2. Missing events in `config/events.json` → write `delegation/GPT-44_missing_events.txt` and wait up to 10 min before the export (the lead fills dates). No invented dates.
3. Apply only obvious team-name spelling variants; list new names. Player identity splits → `config/player_aliases.csv` only after the same-round check.
4. Report `delegation/GPT-44_report.md`: archives / imported / skipped, FURIA maps per map before → after, date precision, parse failures, duplicates, **FURIA roster (name → steamid → rounds, last 3 months vs whole period)**. Portraits already placed for: FalleN 76561197960690195, yuurih 76561198164970560, YEKINDAR 76561198134401925, KSCERATO 76561198058500492, molodoy 76561198200982290 — confirm against the recent roster.
5. `cp -R data/site/. site-preview/data/`; pytest. Do not touch `web/`.
