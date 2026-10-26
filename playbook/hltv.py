"""Plan HLTV demo downloads for a team: list its matches, keep tier-1 events, order by
HLTV's popularity stars, skip archives we already have, and write a page for downloading
the rest by hand.

HLTV allows demo downloads by people only (its robots.txt disallows automated demo
downloads and its terms reportedly forbid scraping), so nothing here contacts hltv.org.
The owner saves a team's results page (``/results?team=<id>``) and, if he likes, match
pages from his browser; this module parses them, plans the downloads and renders
``_sync/<team>_queue.html``, which he opens in Safari and clicks through one link at a time.

All parsing here works on HTML text and is unit-tested with small fixtures.
"""
from __future__ import annotations

import json
import plistlib
import re
import tomllib
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

from playbook.config import CONFIG_DIR

HLTV = "https://www.hltv.org"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


# --- a tiny DOM (stdlib only) -------------------------------------------------------------

@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node | str"] = field(default_factory=list)
    parent: "Node | None" = None

    @property
    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def iter(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag: str | None = None, cls: str | None = None, attr: str | None = None):
        for node in self.iter():
            if tag and node.tag != tag:
                continue
            if cls and cls not in node.classes:
                continue
            if attr and attr not in node.attrs:
                continue
            yield node

    def find(self, tag: str | None = None, cls: str | None = None, attr: str | None = None) -> "Node | None":
        return next(self.find_all(tag, cls, attr), None)

    def text(self) -> str:
        out = []
        for child in self.children:
            out.append(child if isinstance(child, str) else child.text())
        return re.sub(r"\s+", " ", "".join(out)).strip()


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, {k: (v or "") for k, v in attrs}, parent=self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:  # tolerate stray end tags
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse_html(text: str) -> Node:
    builder = _Builder()
    builder.feed(text)
    builder.close()
    return builder.root


def read_saved_page(path: Path) -> tuple[str, str]:
    """(HTML, page URL or "") of a page saved from a browser: an .html file, or Safari's default
    .webarchive (a binary plist that holds the page and the URL it came from)."""
    data = path.read_bytes()
    if not data.startswith(b"bplist"):
        return data.decode("utf-8", errors="replace"), ""
    main = plistlib.loads(data).get("WebMainResource") or {}
    raw = bytes(main.get("WebResourceData") or b"")
    try:
        text = raw.decode(main.get("WebResourceTextEncodingName") or "utf-8", errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    return text, str(main.get("WebResourceURL") or "")


# --- page parsers -----------------------------------------------------------------------

MATCH_HREF = re.compile(r"/matches/(\d+)/([^/?#]+)")


@dataclass
class ResultRow:
    match_id: int
    slug: str
    unix_ms: int | None
    stars: int
    event: str
    fmt: str            # bo1/bo3/bo5 or a map abbreviation for single-map matches
    teams: list[str]
    score: str


def parse_results(html: str) -> list[ResultRow]:
    """Rows of an HLTV ``/results`` page, one per match. Featured matches are listed twice,
    once without a date (``data-zonedgrouping-entry-unix="0"``): the dated copy is kept,
    whichever of the two comes first."""
    root = parse_html(html)
    rows: list[ResultRow] = []
    dated: dict[int, bool] = {}  # match id -> whether the copy kept so far has a date
    for con in root.find_all(cls="result-con"):
        link = next((a for a in con.find_all("a") if MATCH_HREF.search(a.attrs.get("href", ""))), None)
        if link is None:
            continue
        m = MATCH_HREF.search(link.attrs["href"])
        mid = int(m[1])
        unix = con.attrs.get("data-zonedgrouping-entry-unix", "")
        unix_ms = int(unix) if unix.isdigit() and int(unix) > 0 else None
        if mid in dated and (dated[mid] or unix_ms is None):
            continue  # a duplicate that adds no date
        stars_box = con.find(cls="stars")
        row = ResultRow(
            match_id=mid, slug=m[2], unix_ms=unix_ms,
            stars=sum(1 for _ in stars_box.find_all("i")) if stars_box else 0,
            event=(con.find(cls="event-name").text() if con.find(cls="event-name") else ""),
            fmt=(con.find(cls="map-text").text() if con.find(cls="map-text") else ""),
            teams=[t.text() for t in con.find_all(cls="team")][:2],
            score=(con.find(cls="result-score").text().replace(" ", "") if con.find(cls="result-score") else ""),
        )
        if mid in dated:  # the dated copy replaces the undated featured one
            rows = [r for r in rows if r.match_id != mid]
        dated[mid] = unix_ms is not None
        rows.append(row)
    return rows


@dataclass
class MatchPage:
    demo_id: int | None
    unix_ms: int | None
    event: str
    event_id: int | None
    teams: list[str]
    maps_played: list[str]
    match_id: int | None = None  # from the page's canonical / og:url link, when it has one


def parse_match(html: str) -> MatchPage:
    root = parse_html(html)
    demo = None
    for node in root.iter():
        link = node.attrs.get("data-demo-link") or (node.attrs.get("href") if node.tag == "a" else None)
        m = re.search(r"/download/demo/(\d+)", link or "")
        if m:
            demo = int(m[1])
            break
    box = root.find(cls="timeAndEvent")
    unix = None
    event, event_id = "", None
    if box is not None:
        dated = box.find(attr="data-unix")
        unix = int(dated.attrs["data-unix"]) if dated and dated.attrs["data-unix"].isdigit() else None
        ev = box.find(cls="event")
        link = ev.find("a") if ev else None
        if link is not None:
            event = link.text()
            m = re.search(r"/events/(\d+)/", link.attrs.get("href", ""))
            event_id = int(m[1]) if m else None
    teams = [t.text() for t in root.find_all(cls="teamName")][:2]
    maps = []
    for holder in root.find_all(cls="mapholder"):
        name = holder.find(cls="mapname")
        played = holder.find(cls="optional") is None and holder.find(cls="results-team-score") is not None
        if name is not None and played:
            maps.append(name.text())
    own_url = " ".join([n.attrs.get("href", "") for n in root.find_all("link") if n.attrs.get("rel") == "canonical"]
                       + [n.attrs.get("content", "") for n in root.find_all("meta")
                          if n.attrs.get("property") == "og:url"])
    m = MATCH_HREF.search(own_url)
    return MatchPage(demo, unix, event, event_id, teams, maps, int(m[1]) if m else None)


@dataclass
class TeamPage:
    name: str
    logos: list[str]
    roster: list[dict]


def parse_team(html: str) -> TeamPage:
    root = parse_html(html)
    name_node = root.find(cls="profile-team-name")
    logos = [img.attrs["src"] for img in root.find_all("img") if "teamlogo" in img.attrs.get("src", "")
             and img.parent is not None and "profile-team-logo-container" in img.parent.classes]
    roster, seen = [], set()
    for img in root.find_all("img"):
        m = re.match(r"Image of Counter-Strike player (.+)", img.attrs.get("alt", ""))
        if m and "playerbodyshot" in img.attrs.get("src", "") and m[1] not in seen:
            seen.add(m[1])
            roster.append({"nick": m[1], "bodyshot": img.attrs["src"]})
    status = {}
    table = root.find(cls="players-table")
    if table is not None:
        for tr in table.find_all("tr"):
            cells = [td.text() for td in tr.find_all("td")]
            if len(cells) >= 3:
                status[cells[0]] = {"status": cells[1], "time_on_team": cells[2]}
    for p in roster:
        p.update(status.get(p["nick"], {}))
    return TeamPage(name_node.text() if name_node else "", logos, roster)


# --- planning ---------------------------------------------------------------------------

def load_config(path: Path | None = None) -> dict:
    path = path or CONFIG_DIR / "hltv.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def has_term(event: str, term: str) -> bool:
    """Case-insensitive: ``term`` occurs in ``event`` starting at a word, so "Series" matches
    "Europe Series 12" but not "StarSeries", while "Qualifier" still matches "Qualifiers"."""
    start = r"(?<!\w)" if re.match(r"\w", term) else ""
    return re.search(start + re.escape(term), event, re.IGNORECASE) is not None


def is_tier1(event: str, cfg: dict) -> bool:
    tiers = cfg.get("tier1", {})
    if any(has_term(event, x) for x in tiers.get("exclude", [])):
        return False
    include = tiers.get("include", [])
    return not include or any(has_term(event, x) for x in include)


ARCHIVE_RE = re.compile(r"^(?P<prefix>.*)-(?P<fmt>bo[135]|nuke|mirage|inferno|dust2|ancient|anubis|cache|"
                        r"overpass|train|vertigo)-[A-Za-z0-9_-]{18,26}$")


def format_key(fmt: str) -> str:
    """Format used to compare matches with archive names: "bo3"/"bo5" as they are; a bo1 and a
    single-map match are both "map" (results pages show the map instead of "bo1", and an
    archive may be named either way)."""
    fmt = fmt.strip().lower()
    if not fmt:
        return ""
    return fmt if fmt.startswith("bo") and fmt != "bo1" else "map"


def archive_keys(stems: Iterable[str]) -> dict[tuple[str, str], int]:
    """(event-teams prefix, format key) -> number of distinct archives, from archive stems and
    extracted folder names (an archive and its extracted folder share the stem: counted once)."""
    out: dict[tuple[str, str], int] = {}
    for stem in set(stems):
        m = ARCHIVE_RE.match(stem)
        if m:
            key = (m["prefix"], format_key(m["fmt"]))
            out[key] = out.get(key, 0) + 1
    return out


def slug_prefixes(slug: str) -> list[str]:
    """Match slug ``<t1>-vs-<t2>-<event>`` -> candidate archive prefixes ``<event>-<t1>-vs-<t2>``."""
    parts = slug.split("-")
    out = []
    for k in range(1, len(parts)):
        head, tail = "-".join(parts[:k]), "-".join(parts[k:])
        if "-vs-" in head and not head.endswith("-vs"):
            out.append(f"{tail}-{head}")
    return out


class Plan(NamedTuple):
    want: list[ResultRow]       # to download: most stars first, then newest
    have: list[ResultRow]       # already here
    skipped: list[ResultRow]    # not a tier-1 event
    ambiguous: list[ResultRow]  # archive names cannot tell (a rematch at the same event): a human decides


def plan_matches(rows: list[ResultRow], existing_stems: Iterable[str], *, since: str, until: str | None = None,
                 cfg: dict | None = None, known_ids: set[int] | frozenset[int] = frozenset()) -> Plan:
    """Sort the result rows inside [since, until] into a Plan.

    A match is had when its HLTV id is in ``known_ids`` (registered archives, dataset folders
    named ``<id>-...``). Otherwise archive names, which carry no match id, are compared by
    event/teams/format prefix; ``existing_stems`` should leave out archives already registered
    to a match id. When more matches share a prefix than there are archives with it (a rematch
    at the same event, same format), the archives cannot be attributed, so none of those
    matches counts as had and all of them come back in ``ambiguous``. Matches outside the date
    window count for that comparison too: an archive may be theirs."""
    cfg = cfg or {}
    keys = archive_keys(existing_stems)
    lo = datetime.fromisoformat(since).replace(tzinfo=timezone.utc).timestamp() * 1000
    hi = datetime.fromisoformat(until).replace(tzinfo=timezone.utc).timestamp() * 1000 if until else None
    unique: dict[int, ResultRow] = {}
    for row in rows:  # overlapping results pages list a match more than once
        kept = unique.get(row.match_id)
        if kept is None or (kept.unix_ms is None and row.unix_ms is not None):
            unique[row.match_id] = row

    def key_of(row: ResultRow) -> tuple[str, str] | None:
        fmt = format_key(row.fmt)
        return next(((p, fmt) for p in slug_prefixes(row.slug) if (p, fmt) in keys), None)

    claims: dict[tuple[str, str], int] = {}
    for row in unique.values():
        key = None if row.match_id in known_ids else key_of(row)
        if key is not None:
            claims[key] = claims.get(key, 0) + 1
    plan = Plan([], [], [], [])
    for row in unique.values():
        if row.unix_ms is None or row.unix_ms < lo or (hi is not None and row.unix_ms > hi):
            continue
        key = key_of(row)
        if not is_tier1(row.event, cfg):
            plan.skipped.append(row)
        elif row.match_id in known_ids:
            plan.have.append(row)
        elif key is None:
            plan.want.append(row)
        elif claims[key] <= keys[key]:
            plan.have.append(row)
        else:
            plan.ambiguous.append(row)
    plan.want.sort(key=lambda r: (-r.stars, -(r.unix_ms or 0)))
    return plan


def queue_text(entries: list[dict]) -> str:
    """The download queue, most wanted first: one "<demo id> <match id>" per line, "-" for a demo
    id not known yet (no saved match page: the download page links to the match page instead)."""
    return "".join(f"{'-' if e.get('demo_id') is None else e['demo_id']} {e['hltv_match_id']}\n" for e in entries)


def read_queue(text: str) -> list[tuple[int | None, int]]:
    """(demo id or None, match id) for each line of a queue file."""
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit() and (parts[0].isdigit() or parts[0] == "-"):
            out.append((int(parts[0]) if parts[0].isdigit() else None, int(parts[1])))
    return out


def row_dict(row: ResultRow) -> dict:
    d = asdict(row)
    d["date"] = (datetime.fromtimestamp(row.unix_ms / 1000, tz=timezone.utc).date().isoformat()
                 if row.unix_ms else None)
    return d


def write_plan(path: Path, team: dict, matches: list[dict], ambiguous: list[dict] | None = None) -> None:
    """``matches``: the planned downloads (``demo_id`` None when no match page was saved);
    ``ambiguous``: matches a human has to decide about (see plan_matches)."""
    doc = {"team": team, "matches": matches}
    if ambiguous:
        doc["ambiguous"] = ambiguous
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# --- what we already have ---------------------------------------------------------------

ARCHIVE_SUFFIXES = (".rar", ".zip")


def archive_registry(root: Path) -> dict[str, int]:
    """config/hltv_archives.json "archives": archive stem -> HLTV match id."""
    path = root / "config" / "hltv_archives.json"
    if not path.exists():
        return {}
    return {stem: int(mid) for stem, mid in json.loads(path.read_text(encoding="utf-8")).get("archives", {}).items()}


def archive_dir(root: Path) -> Path | None:
    """``[archive] dir`` of config/storage.toml, where imported archives are moved."""
    path = root / "config" / "storage.toml"
    if not path.exists():
        return None
    value = (tomllib.loads(path.read_text(encoding="utf-8")).get("archive") or {}).get("dir")
    return Path(value).expanduser() if value else None


def local_stems(root: Path) -> set[str]:
    """Stems of the HLTV archives we have: folders and .rar/.zip files in data/raw/hltv and
    .rar/.zip files in the archive dir (hidden files and macOS ._ sidecars ignored)."""
    stems: set[str] = set()
    raw = root / "data" / "raw" / "hltv"
    if raw.is_dir():
        for p in raw.iterdir():
            if p.name.startswith("."):
                continue
            if p.is_dir():
                stems.add(p.name)
            elif p.suffix.lower() in ARCHIVE_SUFFIXES:
                stems.add(p.stem)
    adir = archive_dir(root)
    if adir is not None and adir.is_dir():
        stems |= {p.stem for p in adir.iterdir()
                  if p.suffix.lower() in ARCHIVE_SUFFIXES and not p.name.startswith(".")}
    return stems


def dataset_match_ids(root: Path) -> set[int]:
    """HLTV match ids of dataset folders data/raw/<source>/<event>/<id>-... (sources other than hltv)."""
    ids: set[int] = set()
    raw = root / "data" / "raw"
    if raw.is_dir():
        for source in raw.iterdir():
            if source.is_dir() and source.name != "hltv":
                for folder in source.glob("*/*"):
                    head = folder.name.split("-", 1)[0]
                    if head.isdigit() and folder.is_dir():
                        ids.add(int(head))
    return ids


def present_match_ids(root: Path) -> set[int]:
    """HLTV match ids whose demos are here: an archive (or its extracted folder) registered to the
    match in config/hltv_archives.json, or a dataset folder named ``<id>-...``."""
    registry = archive_registry(root)
    return {registry[s] for s in local_stems(root) if s in registry} | dataset_match_ids(root)


# --- the page for downloading by hand ---------------------------------------------------

def demo_url(demo_id: int) -> str:
    return f"{HLTV}/download/demo/{int(demo_id)}"


def match_url(match_id: int, slug: str | None = None) -> str:
    return f"{HLTV}/matches/{int(match_id)}/{quote(slug or 'x', safe='-_.')}"


def queue_entries(plan: dict, queue: list[tuple[int | None, int]] | None) -> list[dict]:
    """The plan's matches in queue order (plan order without a queue file). A queue line that
    is not in the plan still gets an entry with its ids; a demo id on the line wins."""
    matches = plan.get("matches", [])
    if queue is None:
        return [dict(m) for m in matches]
    by_match = {int(m["hltv_match_id"]): m for m in matches}
    out = []
    for demo, mid in queue:
        entry = dict(by_match.get(mid) or {"hltv_match_id": mid})
        if demo is not None:
            entry["demo_id"] = demo
        out.append(entry)
    return out


PAGE_NOTE = "HLTV 只允许人工下载：逐个点击，下载完成后让 Claude 运行 refresh（或在终端运行 bash scripts/refresh.sh）"
PAGE_NOTE_EN = ("HLTV allows manual downloads only: click the links one by one; when the downloads have "
                "finished, ask Claude to run refresh (or run bash scripts/refresh.sh in Terminal).")
PAGE_HEAD = ('<tr><th>#</th><th>热度<span class="en">Stars</span></th><th>日期<span class="en">Date</span></th>'
             '<th>赛事<span class="en">Event</span></th><th>对阵<span class="en">Teams</span></th>'
             '<th>链接<span class="en">Link</span></th><th>完成<span class="en">Done</span></th></tr>')
PAGE_CSS = """
:root { color-scheme: light dark; --bg: #ffffff; --fg: #1d1d1f; --muted: #6e6e73; --line: #e2e2e7;
  --link: #0a5bd3; --visited: #7a3fb8; --done: #e6f4ea; --note: #fff7e0; --note-line: #f0c36d; --warn: #b3261e; }
@media (prefers-color-scheme: dark) { :root { --bg: #1c1c1e; --fg: #f2f2f7; --muted: #a1a1a6; --line: #3a3a3c;
  --link: #6aa8ff; --visited: #c49bff; --done: #1e3a24; --note: #3a3016; --note-line: #8a6d1f; --warn: #ff8a80; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Helvetica Neue", sans-serif; }
main { max-width: 1120px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 14px; }
h2 { font-size: 18px; margin: 32px 0 8px; }
.en, .sub { display: block; font-size: 12px; font-weight: 400; color: var(--muted); }
.note { background: var(--note); border: 1px solid var(--note-line); border-radius: 10px; padding: 10px 14px;
  margin: 0 0 14px; }
.note p { margin: 0; }
.warn { color: var(--warn); font-weight: 600; }
.summary { color: var(--muted); margin: 0 0 10px; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; vertical-align: top; padding: 9px 10px; border-bottom: 1px solid var(--line); }
th { font-size: 13px; white-space: nowrap; }
td.n, td.when { color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
td.stars { color: #d4a017; white-space: nowrap; letter-spacing: 1px; }
td.link a { display: block; color: var(--link); }
td.link a.dl { font-weight: 600; }
td.link a.mp { font-size: 12px; margin-top: 2px; }
td.link a:visited { color: var(--visited); }
td.done { text-align: center; }
td.done input { width: 18px; height: 18px; }
tr.done td { background: var(--done); }
tr.have td { opacity: .45; }
"""
PAGE_JS = """
(function () {
  function get(key) { try { return window.localStorage.getItem(key) === "1"; } catch (e) { return false; } }
  function put(key, on) {
    try { if (on) { window.localStorage.setItem(key, "1"); } else { window.localStorage.removeItem(key); } }
    catch (e) { /* storage unavailable: the page still works, it just forgets */ }
  }
  Array.prototype.forEach.call(document.querySelectorAll("tr[data-key]"), function (row) {
    var key = "hltv-queue:" + row.getAttribute("data-key");
    var box = row.querySelector("input[type=checkbox]");
    function show(on) { row.classList.toggle("done", on); if (box) { box.checked = on; } }
    show(get(key));
    Array.prototype.forEach.call(row.querySelectorAll("a.dl"), function (a) {
      a.addEventListener("click", function () { show(true); put(key, true); });
    });
    if (box) { box.addEventListener("change", function () { show(box.checked); put(key, box.checked); }); }
  });
})();
"""


def _page_row(n: int, e: dict, present: set[int]) -> str:
    mid = int(e["hltv_match_id"])
    stars = int(e.get("stars") or 0)
    when = datetime.fromtimestamp(e["unix_ms"] / 1000, tz=timezone.utc) if e.get("unix_ms") else None
    day, clock = (when.strftime("%Y-%m-%d"), when.strftime("%H:%M UTC")) if when else ("?", "")
    page = escape(match_url(mid, e.get("slug")))
    if e.get("demo_id") is not None:
        link = (f'<a class="dl" href="{escape(demo_url(e["demo_id"]))}">下载 demo<span class="en">Download demo'
                f'</span></a><a class="mp" href="{page}" target="_blank" rel="noopener">比赛页 · match page</a>')
    else:
        link = (f'<a class="dl" href="{page}" target="_blank" rel="noopener">打开比赛页，点 GOTV Demo'
                f'<span class="en">Open the match page, click GOTV Demo</span></a>')
    have = mid in present
    done = ('已有<span class="en">here</span>' if have else
            '<input type="checkbox" aria-label="已下载 / downloaded">')
    teams = " vs ".join(e.get("teams") or []) or f"#{mid}"
    maps = ", ".join(e.get("maps_played") or [])
    return (f'<tr data-key="m{mid}"' + (' class="have"' if have else "") + ">"
            f'<td class="n">{n}</td><td class="stars" title="{stars} 星 / stars">{"★" * stars or "–"}</td>'
            f'<td class="when">{day}<span class="en">{clock}</span></td><td>{escape(e.get("event") or "")}</td>'
            f"<td>{escape(teams)}" + (f'<span class="sub">{escape(maps)}</span>' if maps else "") + "</td>"
            f'<td class="link">{link}</td><td class="done">{done}</td></tr>')


def _page_table(entries: list[dict], present: set[int]) -> str:
    rows = "\n".join(_page_row(i, e, present) for i, e in enumerate(entries, 1))
    return f'<div class="scroll"><table>\n<thead>{PAGE_HEAD}</thead>\n<tbody>\n{rows}\n</tbody>\n</table></div>\n'


def queue_html(team: str, entries: list[dict], present: set[int], ambiguous: list[dict] | None = None, *,
               drive_missing: bool = False, generated: str = "") -> str:
    """A self-contained page (inline style and script, nothing loaded from elsewhere) for
    downloading the queue by hand: one row per match with its demo link (or its match page),
    matches already here greyed out, clicked links remembered by the browser."""
    here = sum(1 for e in entries if int(e["hltv_match_id"]) in present)
    todo = len(entries) - here
    title = f"HLTV 下载队列 · {escape(team)}"
    parts = [
        '<!doctype html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n<style>{PAGE_CSS}</style>\n</head>\n<body>\n<main>\n"
        f'<h1>{title}<span class="en">HLTV download queue</span></h1>\n'
        f'<div class="note"><p>{PAGE_NOTE}</p><p class="en">{PAGE_NOTE_EN}</p></div>\n'
    ]
    if drive_missing:
        parts.append('<p class="warn">外置硬盘没有连接，无法判断哪些 demo 已经有了。<span class="en">The external '
                     "drive is not mounted, so the page cannot tell which demos are already here.</span></p>\n")
    parts.append(f'<p class="summary">共 {len(entries)} 场 · 已有 {here} 场 · 待下载 {todo} 场<span class="en">'
                 f"{len(entries)} matches · {here} already here · {todo} to download"
                 + (f" · updated {escape(generated)}" if generated else "") + "</span></p>\n")
    parts.append(_page_table(entries, present))
    if ambiguous:
        parts.append('<h2>待确认<span class="en">To check</span></h2>\n<p class="summary">这些比赛与已有录像的赛事、'
                     "队伍和赛制都相同，但比赛比录像多（重赛？），无法确定哪场已经有了，所以没有放进队列。确定缺哪一场时，"
                     '打开它的比赛页手动下载。<span class="en">Same event, teams and format as archives we already have, '
                     "but more matches than archives (a rematch?), so it is unclear which ones we have; they are not "
                     "queued. If you know one is missing, open its match page and download it by hand.</span></p>\n")
        parts.append(_page_table(ambiguous, present))
    parts.append(f"</main>\n<script>{PAGE_JS}</script>\n</body>\n</html>\n")
    return "".join(parts)


def write_queue_page(team: str, sync_dir: Path, root: Path) -> tuple[Path, int, int]:
    """Write ``<sync_dir>/<team>_queue.html`` from ``<team>_plan.json`` and ``<team>_queue.txt``,
    greying out what is already under ``root``; returns (page, matches listed, already here)."""
    plan = json.loads((sync_dir / f"{team}_plan.json").read_text(encoding="utf-8"))
    queue_path = sync_dir / f"{team}_queue.txt"
    queue = read_queue(queue_path.read_text(encoding="utf-8")) if queue_path.exists() else None
    entries = queue_entries(plan, queue)
    present = present_match_ids(root)
    raw = root / "data" / "raw"
    page = sync_dir / f"{team}_queue.html"
    page.write_text(queue_html(team, entries, present, plan.get("ambiguous"),
                               drive_missing=raw.is_symlink() and not raw.exists(),
                               generated=datetime.now().strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    return page, len(entries), sum(1 for e in entries if int(e["hltv_match_id"]) in present)
