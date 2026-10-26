#!/bin/bash
# Download planned HLTV demo archives into ~/Downloads at a human pace, resumably, then
# (unless --no-refresh) run scripts/refresh.sh to import, date, archive, parse and export.
#
#   caffeinate -i bash scripts/hltv_download.sh aurora          # uses _sync/aurora_queue.txt
#
# The queue (written by scripts/hltv_plan.py or by Claude) has one "<demo id> <match id>"
# per line, most wanted first. Progress goes to _sync/<team>_download.log with lines
#   OK <demo id> <match id> <bytes|already-present> <archive file>
# which scripts/register_hltv_dates.py reads to give every game its exact date.
#
# How it downloads: it opens each demo link in your own Safari, exactly as if you clicked
# "GOTV Demo" on the match page, waits until the archive has finished downloading, rests,
# and goes on with the next one. The first time, Safari may ask "Allow downloads on
# www.hltv.org?" - click Allow. If HLTV shows a check page, or nothing starts, the script
# stops and tells you; it never tries to get around a check. Run it again any time:
# finished demos are skipped.
#
# --curl downloads with curl instead (identifies itself as this tool). HLTV may refuse
# non-browser clients; a refusal stops the run.
set -u
export LC_ALL=C
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
TEAM="${1:?usage: hltv_download.sh <team> [--curl] [--no-refresh] [--delay seconds]}"
shift
MODE=safari; REFRESH=1; DELAY=30
while [ $# -gt 0 ]; do
  case "$1" in
    --curl) MODE=curl ;;
    --safari) MODE=safari ;;
    --no-refresh) REFRESH=0 ;;
    --delay) DELAY="$2"; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
QUEUE="$ROOT/_sync/${TEAM}_queue.txt"
LOG="$ROOT/_sync/${TEAM}_download.log"
DL="$HOME/Downloads"
UA="cs2-pro-playbook/0.1 (personal non-commercial CS2 demo analysis; one download at a time)"
[ -f "$QUEUE" ] || { echo "No queue $QUEUE (run scripts/hltv_plan.py $TEAM first)"; exit 1; }
touch "$LOG"
echo "== start $(date '+%F %T') team=$TEAM mode=$MODE" | tee -a "$LOG"
[ "$MODE" = safari ] && echo "   (Safari: if it asks to allow downloads from www.hltv.org, click Allow)"

archives() { ls -1 "$DL" 2>/dev/null | grep -E '\.(rar|zip)$' | sort; }

fetch_curl() {  # $1 demo -> prints the archive name on success
  local tmp code f
  tmp="$(mktemp -d "$DL/.hltv_dl_XXXX")"
  code=$(cd "$tmp" && curl -sS -L -J -O --fail -A "$UA" -w "%{http_code}" \
         "https://www.hltv.org/download/demo/$1" 2>>"$LOG")
  f="$(ls -1 "$tmp" 2>/dev/null | head -1)"
  if [ -n "$f" ] && [[ "$f" =~ \.(rar|zip)$ ]] && [ "$(stat -f%z "$tmp/$f")" -gt 1000000 ]; then
    if [ -e "$DL/$f" ]; then rm -rf "$tmp"; echo "$f"; return 0; fi
    mv "$tmp/$f" "$DL/$f" && rmdir "$tmp" && echo "$f" && return 0
  fi
  echo "   curl http=$code file=${f:-none}" >> "$LOG"
  rm -rf "$tmp"
  return 1
}

fetch_safari() {  # $1 demo -> prints the archive name once Safari has finished it
  local before after new waited=0 last=-1 size
  before="$(archives)"
  open -g -a Safari "https://www.hltv.org/download/demo/$1" || return 1
  while [ $waited -lt 1800 ]; do
    sleep 5; waited=$((waited + 5))
    after="$(archives)"
    new="$(comm -13 <(echo "$before") <(echo "$after") | head -1)"
    if [ -n "$new" ] && [ ! -e "$DL/$new.download" ]; then
      size=$(stat -f%z "$DL/$new" 2>/dev/null || echo 0)
      if [ "$size" -gt 1000000 ] && [ "$size" = "$last" ]; then echo "$new"; return 0; fi
      last="$size"
    fi
    if [ $waited -ge 90 ] && [ -z "$new" ] && ! ls -d "$DL"/*.download >/dev/null 2>&1; then
      return 1  # nothing started: Safari shows a check page or asks whether to allow downloads
    fi
  done
  return 1
}

# team images listed in _sync/<team>_assets.txt ("<file name> <url>" per line): logo and player
# photos for the portraits; small files, fetched once with curl (identifies itself as this tool)
ASSETS="$ROOT/_sync/${TEAM}_assets.txt"
if [ -f "$ASSETS" ]; then
  mkdir -p "$ROOT/_sync/${TEAM}_assets"
  while read -r name url; do
    [ -z "${name:-}" ] || [ -s "$ROOT/_sync/${TEAM}_assets/$name" ] && continue
    if curl -sS -L --fail -A "$UA" -o "$ROOT/_sync/${TEAM}_assets/$name" "$url" 2>>"$LOG"; then
      echo "ASSET $name" | tee -a "$LOG"
    else
      rm -f "$ROOT/_sync/${TEAM}_assets/$name"; echo "ASSET-FAIL $name" | tee -a "$LOG"
    fi
    sleep 2
  done < "$ASSETS"
fi

n=0; ok=0; skip=0; fail=0
while read -r demo match _; do
  [ -z "${demo:-}" ] && continue
  n=$((n + 1))
  if grep -q "^OK $demo " "$LOG"; then skip=$((skip + 1)); continue; fi
  if [ "$MODE" = curl ]; then f="$(fetch_curl "$demo")" || f=""; else f="$(fetch_safari "$demo")" || f=""; fi
  if [ -n "$f" ]; then
    echo "OK $demo $match $(stat -f%z "$DL/$f") $f" | tee -a "$LOG"; ok=$((ok + 1))
  else
    echo "FAIL $demo $match mode=$MODE" | tee -a "$LOG"; fail=$((fail + 1))
    if [ "$MODE" = safari ]; then
      echo "== Nothing was downloaded. Look at Safari: if hltv.org shows a check or asks to allow"
      echo "   downloads, deal with it there, then run this script again." | tee -a "$LOG"
    else
      echo "== HLTV refused the download. Stopping (use the default Safari mode instead)." | tee -a "$LOG"
    fi
    break
  fi
  sleep "$DELAY"
done < "$QUEUE"
echo "== end $(date '+%F %T'): ok=$ok skipped=$skip failed=$fail of $n" | tee -a "$LOG"

if [ "$REFRESH" = 1 ] && [ $ok -gt 0 ]; then
  echo "== running scripts/refresh.sh"
  bash "$ROOT/scripts/refresh.sh"
fi
