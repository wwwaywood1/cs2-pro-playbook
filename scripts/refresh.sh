#!/usr/bin/env bash
# One command to add new HLTV demos to the site:
#   bash scripts/refresh.sh
# 1. moves HLTV match archives (*-bo1/3/5-*.rar|zip, single-map ones too) from ~/Downloads into data/raw/hltv/
# 2. extracts and imports them (duplicates and maps outside the pool are skipped)
# 3. gives planned matches their exact dates (_sync/<team>_plan.json), moves the archives to the
#    external drive and updates the download pages (_sync/<team>_queue.html)
# 4. parses new demos (a few broken demos do not stop the run)
# 5. exports the site data and refreshes the inputs for the team summaries
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
[ -x "$PY" ] || PY=python3

# data/raw may be a symlink to an external drive (config/storage.toml [raw] dir)
if [ -L data/raw ] && [ ! -d data/raw/ ]; then
  echo "data/raw -> $(readlink data/raw) is not mounted. Plug in the external drive and run again."
  exit 1
fi

mkdir -p data/raw/hltv
shopt -s nullglob
moved=0; present=0
# series archives (<event>-<a>-vs-<b>-bo3-<id>.rar) and single-map ones (<event>-<a>-vs-<b>-<map>-<id>.rar)
for f in "$HOME"/Downloads/*-bo[135]-*.rar "$HOME"/Downloads/*-bo[135]-*.zip \
         "$HOME"/Downloads/*-vs-*-{nuke,mirage,inferno,dust2,ancient,anubis,cache,overpass,train,vertigo}-*.{rar,zip}; do
  [ -e "$f" ] || continue
  mv -n "$f" data/raw/hltv/
  if [ ! -e "$f" ]; then
    moved=$((moved + 1))
  elif [ -e "data/raw/hltv/${f##*/}" ]; then  # mv -n skips a name that is already taken
    present=$((present + 1)); echo "   already in data/raw/hltv, left in ~/Downloads: ${f##*/}"
  else
    echo "   could not move ${f##*/}"
  fi
done
msg="== moved $moved archive(s) from ~/Downloads"
[ "$present" -gt 0 ] && msg="$msg; $present already present in data/raw/hltv (left in ~/Downloads, listed above)"
echo "$msg"

echo "== import"; "$PY" scripts/import_hltv.py || echo "(import reported problems, continuing)"
echo "== dates"   # exact dates for planned matches (_sync/<team>_plan.json from scripts/hltv_plan.py)
for plan in _sync/*_plan.json; do
  log="${plan%_plan.json}_download.log"  # written only by the old downloader
  if [ -f "$log" ]; then
    "$PY" scripts/register_hltv_dates.py --plan "$plan" --log "$log" --apply || echo "(date registration failed for $plan)"
  else
    "$PY" scripts/register_hltv_dates.py --plan "$plan" --apply || echo "(date registration failed for $plan)"
  fi
done
# archives registered earlier but imported only now (config/hltv_archives.json)
"$PY" scripts/register_hltv_dates.py --apply | head -1 || true
echo "== archive"; "$PY" scripts/archive_downloads.py --apply || echo "(archiving reported problems, continuing)"
for plan in _sync/*_plan.json; do  # the download pages grey out what is here now
  team="${plan##*/}"; team="${team%_plan.json}"
  "$PY" scripts/hltv_queue.py "$team" >/dev/null || echo "(could not update _sync/${team}_queue.html)"
done
echo "== parse";  "$PY" -m playbook parse 2>&1 | tail -3 || true
echo "== export"; "$PY" -m playbook export || { echo "export failed"; exit 1; }
"$PY" scripts/insight_text.py brief de_mirage de_inferno de_nuke de_dust2 de_ancient de_anubis >/dev/null
echo "== done. Tell Claude so the team summaries can be rewritten for teams whose facts changed."
