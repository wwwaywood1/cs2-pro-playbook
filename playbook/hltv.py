"""Plan HLTV demo downloads for a team: list its matches, keep tier-1 events, order by
HLTV's popularity stars, skip archives we already have, and write a polite download script.

Why a plan + script instead of a crawler: hltv.org sits behind Cloudflare. Pages with
date filters and the stats section trigger a human check, and a browser started by
automation cannot complete it (and should not try). Plain pages — a team's results
(``/results?team=<id>``, no date parameters), match pages and ``/download/demo/<id>`` —
load normally. So the plan is built from those pages (fetched natively when this runs on
a machine that can reach HLTV, or saved by a browser), and the downloads run from the
owner's own Terminal with ``curl`` at one request every ~20 s.

All parsing here works on HTML text and is unit-tested with small fixtures, so the same
code serves a native run (``--fetch``) and a browser-assisted run (``--html-dir``).
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

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
    """Rows of an HLTV ``/results`` page (featured duplicates are dropped)."""
    root = parse_html(html)
    rows, seen = [], set()
    for con in root.find_all(cls="result-con"):
        link = next((a for a in con.find_all("a") if MATCH_HREF.search(a.attrs.get("href", ""))), None)
        if link is None:
            continue
        m = MATCH_HREF.search(link.attrs["href"])
        mid = int(m[1])
        unix = con.attrs.get("data-zonedgrouping-entry-unix")
        if mid in seen and not unix:
            continue
        stars_box = con.find(cls="stars")
        row = ResultRow(
            match_id=mid, slug=m[2],
            unix_ms=int(unix) if unix and unix.isdigit() and int(unix) > 0 else None,
            stars=sum(1 for _ in stars_box.find_all("i")) if stars_box else 0,
            event=(con.find(cls="event-name").text() if con.find(cls="event-name") else ""),
            fmt=(con.find(cls="map-text").text() if con.find(cls="map-text") else ""),
            teams=[t.text() for t in con.find_all(cls="team")][:2],
            score=(con.find(cls="result-score").text().replace(" ", "") if con.find(cls="result-score") else ""),
        )
        if mid in seen:  # keep the dated copy of a featured row
            rows = [r for r in rows if r.match_id != mid]
        seen.add(mid)
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
    return MatchPage(demo, unix, event, event_id, teams, maps)


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


def is_tier1(event: str, cfg: dict) -> bool:
    tiers = cfg.get("tier1", {})
    if any(x.lower() in event.lower() for x in tiers.get("exclude", [])):
        return False
    include = tiers.get("include", [])
    return not include or any(x.lower() in event.lower() for x in include)


ARCHIVE_RE = re.compile(r"^(?P<prefix>.*)-(?P<fmt>bo[135]|nuke|mirage|inferno|dust2|ancient|anubis|cache|"
                        r"overpass|train|vertigo)-[A-Za-z0-9_-]{18,26}$")


def archive_keys(stems: list[str]) -> dict[tuple[str, str], int]:
    """(event-teams prefix, bo-type or 'map') -> count, from archive stems/folder names."""
    out: dict[tuple[str, str], int] = {}
    for stem in stems:
        m = ARCHIVE_RE.match(stem)
        if m:
            fmt = m["fmt"] if m["fmt"].startswith("bo") else "map"
            out[(m["prefix"], fmt)] = out.get((m["prefix"], fmt), 0) + 1
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


def plan_matches(rows: list[ResultRow], existing_stems: list[str], *, since: str, until: str | None = None,
                 cfg: dict | None = None, known_ids: set[int] | frozenset[int] = frozenset()
                 ) -> tuple[list[ResultRow], list[ResultRow], list[ResultRow]]:
    """(to_download ordered by stars desc then newest first, already_have, skipped_not_tier1).

    A match is already had when its HLTV id is in ``known_ids`` (registered archives, dataset
    folders named ``<id>-...``) or, failing that, when an archive with the same event/teams/format
    prefix exists (archive names carry no match id)."""
    cfg = cfg or {}
    keys = archive_keys(existing_stems)
    used: dict[tuple[str, str], int] = {}
    lo = datetime.fromisoformat(since).replace(tzinfo=timezone.utc).timestamp() * 1000
    hi = datetime.fromisoformat(until).replace(tzinfo=timezone.utc).timestamp() * 1000 if until else None
    want, have, skipped = [], [], []
    for row in rows:
        if row.unix_ms is None or row.unix_ms < lo or (hi is not None and row.unix_ms > hi):
            continue
        if not is_tier1(row.event, cfg):
            skipped.append(row)
            continue
        if row.match_id in known_ids:
            have.append(row)
            continue
        fmt = row.fmt if row.fmt.startswith("bo") else "map"
        hit = None
        for prefix in slug_prefixes(row.slug):
            key = (prefix, fmt)
            if keys.get(key, 0) - used.get(key, 0) > 0:
                hit = key
                break
        if hit:
            used[hit] = used.get(hit, 0) + 1
            have.append(row)
        else:
            want.append(row)
    want.sort(key=lambda r: (-r.stars, -(r.unix_ms or 0)))
    return want, have, skipped


def queue_text(entries: list[dict]) -> str:
    """Download queue for scripts/hltv_download.sh: one "<demo id> <match id>" per line, in order."""
    return "".join(f"{e['demo_id']} {e['hltv_match_id']}\n" for e in entries)


def row_dict(row: ResultRow) -> dict:
    d = asdict(row)
    d["date"] = (datetime.fromtimestamp(row.unix_ms / 1000, tz=timezone.utc).date().isoformat()
                 if row.unix_ms else None)
    return d


def write_plan(path: Path, team: dict, matches: list[dict]) -> None:
    path.write_text(json.dumps({"team": team, "matches": matches}, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
