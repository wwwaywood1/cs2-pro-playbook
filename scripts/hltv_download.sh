#!/bin/bash
# Download planned HLTV demo archives into ~/Downloads, politely and resumably, then
# (unless --no-refresh) run scripts/refresh.sh to import, date, archive, parse and export.
#
#   caffeinate -i bash scripts/hltv_download.sh aurora            # uses _sync/aurora_queue.txt
#   caffeinate -i bash scripts/hltv_download.sh aurora --safari   # skip the curl attempt
#
# The queue (written by scripts/hltv_plan.py or by Claude) has one "<demo id> <match id>"
# per line, most wanted first. Progress goes to _sync/<team>_download.log with lines
#   OK <demo id> <match id> <bytes|already-present> <archive file>
# which scripts/register_hltv_dates.py reads to give every game its exact date.
#
# Downloader: curl first (fast, no windows). HLTV sits behind Cloudflare; if it answers
# curl with a challenge, the script switches to Safari: it opens each demo link in Safari
# (which has your cookies) and waits for the archive to land in ~/Downloads. The first time,
# Safari may ask "Allow downloads on www.hltv.org?" - click Allow. Run it again any time:
# finished demos are skipped.
set -u
export LC_ALL=C
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
TEAM="${1:?usage: hltv_download.sh <team> [--safari] [--no-refresh] [--delay S]}"
shift
MODE=auto; REFRESH=1; DELAY=20
while [ $# -gt 0 ]; do
  case "$1" in
    --safari) MODE=safari ;;
    --curl) MODE=curl ;;
    --no-refresh) REFRESH=0 ;;
    --delay) DELAY="$2"; shift ;;
  esac
  shift
done
QUEUE="$ROOT/_sync/${TEAM}_queue.txt"
LOG="$ROOT/_sync/${TEAM}_download.log"
DL="$HOME/Downloads"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
[ -f "$QUEUE" ] || { echo "No queue $QUEUE"; exit 1; }
touch "$LOG"
echo "== start $(date '+%F %T') team=$TEAM mode=$MODE" | tee -a "$LOG"

archives() { ls -1 "$DL" 2>/dev/null | grep -E '\.(rar|zip)$' | LC_ALL=C sort; }

fetch_curl() {  # $1 demo $2 match -> prints file name on success
  local tmp code f
  tmp="$(mktemp -d "$DL/.hltv_dl_XXXX")"
  code=$(cd "$tmp" && curl -sS -L -J -O --fail --retry 2 --retry-delay 15 -A "$UA" \
         -H "Referer: https://www.hltv.org/matches/$2/x" -w "%{http_code}" \
         "https://www.hltv.org/download/demo/$1" 2>>"$LOG")
  f="$(ls -1 "$tmp" 2>/dev/null | head -1)"
  if [ -n "$f" ] && [ "$(stat -f%z "$tmp/$f")" -gt 1000000 ] && [[ "$f" =~ \.(rar|zip)$ ]]; then
    if [ -e "$DL/$f" ]; then rm -rf "$tmp"; echo "$f"; return 0; fi
    mv "$tmp/$f" "$DL/$f" && rmdir "$tmp" && echo "$f" && return 0
  fi
  echo "curl http=$code file=${f:-none}" >> "$LOG"
  rm -rf "$tmp"
  return 1
}

fetch_safari() {  # $1 demo -> prints file name on success (waits for Safari to finish)
  local before after new waited=0 last=-1 size
  before="$(archives)"
  open -g -a Safari "https://www.hltv.org/download/demo/$1" || return 2
  while [ $waited -lt 1200 ]; do
    sleep 5; waited=$((waited + 5))
    after="$(archives)"
    new="$(comm -13 <(echo "$before") <(echo "$after") | head -1)"
    if [ -n "$new" ] && [ ! -e "$DL/$new.download" ]; then
      size=$(stat -f%z "$DL/$new" 2>/dev/null || echo 0)
      if [ "$size" -gt 1000000 ] && [ "$size" = "$last" ]; then echo "$new"; return 0; fi
      last="$size"
    fi
    if [ $waited -ge 90 ] && [ -z "$new" ] && ! ls -d "$DL"/*.download >/dev/null 2>&1; then
      return 1  # nothing started: Safari shows a check page or asks to allow downloads
    fi
  done
  return 1
}

n=0; ok=0; skip=0; fail=0
while read -r demo match _; do
  [ -z "${demo:-}" ] && continue
  n=$((n + 1))
  if grep -q "^OK $demo " "$LOG"; then skip=$((skip + 1)); continue; fi
  f=""
  if [ "$MODE" != safari ]; then
    if f="$(fetch_curl "$demo" "$match")"; then :; else
      f=""
      if [ "$MODE" = auto ]; then
        echo "== curl was refused (Cloudflare); switching to Safari" | tee -a "$LOG"; MODE=safari
      fi
    fi
  fi
  if [ -z "$f" ] && [ "$MODE" = safari ]; then
    f="$(fetch_safari "$demo")" || f=""
  fi
  if [ -n "$f" ]; then
    echo "OK $demo $match $(stat -f%z "$DL/$f") $f" | tee -a "$LOG"; ok=$((ok + 1))
  else
    echo "FAIL $demo $match mode=$MODE" | tee -a "$LOG"; fail=$((fail + 1))
    if [ "$MODE" = safari ]; then
      echo "== Safari did not start the download. Open Safari: if hltv.org shows a 'verify you are human'"
      echo "   check or asks to allow downloads, complete it once, then run this script again." | tee -a "$LOG"
      break
    fi
  fi
  sleep "$DELAY"
done < "$QUEUE"
echo "== end $(date '+%F %T'): ok=$ok skipped=$skip failed=$fail of $n" | tee -a "$LOG"

if [ "$REFRESH" = 1 ] && [ $ok -gt 0 ]; then
  echo "== running scripts/refresh.sh"
  bash "$ROOT/scripts/refresh.sh"
fi
