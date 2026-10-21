#!/usr/bin/env bash
# One command to add new HLTV demos to the site:
#   bash scripts/refresh.sh
# 1. moves HLTV match archives (*-bo1/3/5-*.rar|zip) from ~/Downloads into data/raw/hltv/
# 2. extracts and imports them (duplicates and maps outside the pool are skipped)
# 3. parses new demos (a few broken demos do not stop the run)
# 4. exports the site data and refreshes the inputs for the team summaries
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

mkdir -p data/raw/hltv
shopt -s nullglob
moved=0
for f in "$HOME"/Downloads/*-bo[135]-*.rar "$HOME"/Downloads/*-bo[135]-*.zip; do
  mv -n "$f" data/raw/hltv/ && moved=$((moved + 1))
done
echo "== moved $moved archive(s) from ~/Downloads"

echo "== import"; "$PY" scripts/import_hltv.py || echo "(import reported problems, continuing)"
echo "== parse";  "$PY" -m playbook parse 2>&1 | tail -3 || true
echo "== export"; "$PY" -m playbook export || { echo "export failed"; exit 1; }
"$PY" scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis >/dev/null
echo "== done. Tell Claude so the team summaries can be rewritten for teams whose facts changed."
