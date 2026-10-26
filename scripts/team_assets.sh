#!/bin/bash
# Fetch a team's logo and player photos for the portraits, once each:
#   bash scripts/team_assets.sh aurora
# _sync/<team>_assets.txt has one "<file name> <url>" per line (blank lines and lines starting
# with # are ignored). Files go to _sync/<team>_assets/; files already there are skipped.
# Only https image-CDN URLs are fetched (img-cdn.hltv.org, files.bo3.gg, ...). URLs on
# www.hltv.org are refused: demos and pages from HLTV are downloaded by hand (see
# scripts/hltv_queue.py). curl says who it is, fetches one file at a time with 2 s between
# requests, and does not follow redirects.
set -u
export LC_ALL=C
cd "$(dirname "$0")/.." || exit 1
TEAM="${1:?usage: team_assets.sh <team>}"
LIST="_sync/${TEAM}_assets.txt"
OUT="_sync/${TEAM}_assets"
UA="cs2-pro-playbook/0.1 (personal non-commercial CS2 demo analysis; one download at a time)"
[ -f "$LIST" ] || { echo "No list $LIST (one \"<file name> <url>\" per line)"; exit 1; }
mkdir -p "$OUT" || exit 1

host_of() {  # $1 URL -> its lower-case host name if it is an https URL, else nothing
  case "$1" in https://*) ;; *) return 0 ;; esac
  local h="${1#https://}"
  h="${h%%[/?#]*}"; h="${h##*@}"; h="${h%%:*}"; h="${h%.}"
  printf '%s\n' "$h" | tr '[:upper:]' '[:lower:]'
}

got=0; have=0; refused=0; failed=0; requests=0
while read -r name url _; do
  case "${name:-}" in ''|'#'*) continue ;; esac
  url="${url:-}"; url="${url%$'\r'}"
  host="$(host_of "$url")"
  if [ -z "$host" ]; then
    echo "REFUSED $name $url (https URLs only)"; refused=$((refused + 1)); continue
  fi
  case "$host" in
    hltv.org|www.hltv.org)
      echo "REFUSED $name $url (www.hltv.org: download by hand only)"; refused=$((refused + 1)); continue ;;
  esac
  case "$name" in
    */*|.*) echo "REFUSED $name (not a plain file name)"; refused=$((refused + 1)); continue ;;
  esac
  if [ -s "$OUT/$name" ]; then have=$((have + 1)); continue; fi
  [ "$requests" -gt 0 ] && sleep 2
  requests=$((requests + 1))
  part="$OUT/.$name.part"
  if info=$(curl -sS --fail --proto '=https' --max-time 120 -A "$UA" -o "$part" \
            -w '%{http_code} %{content_type}' "$url" </dev/null); then
    case "$info" in
      "200 text/"*) ;;  # an error or check page, not an image
      "200"*) mv -f "$part" "$OUT/$name" && { echo "ASSET $name"; got=$((got + 1)); continue; } ;;
    esac
    echo "ASSET-FAIL $name (got: $info)"
  else
    echo "ASSET-FAIL $name (curl exit $?)"
  fi
  rm -f "$part"; failed=$((failed + 1))
done < "$LIST"
echo "== assets for $TEAM: $got new, $have already there, $refused refused, $failed failed"
[ $((refused + failed)) -eq 0 ]
