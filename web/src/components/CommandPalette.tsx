import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { getIndex, getSearchIndex, useData } from "../data";
import { matchDateLabel, newestMatch } from "../matchDates";
import { calloutLabel, spotLabel, t, useLang, type Lang } from "../i18n";
import type { SearchIndex, SiteIndex } from "../types";
import ErrorBoundary from "./ErrorBoundary";

interface Entry { id: string; label: string; terms: string; to: string; kind: string; map?: string }
const normalise = (value: string) => value.toLocaleLowerCase().replace(/烟雾弹|烟雾/g, "烟").replace(/闪光弹/g, "闪").replace(/燃烧弹|燃烧瓶/g, "火").replace(/de_|[\s_→·+]+/g, " ").trim();
const compact = (value: string) => normalise(value).replace(/\s+/g, "");
const MAX_RESULTS = 80;

export default function CommandPalette({ currentMap }: { currentMap?: string }) {
  useLang();
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && !document.querySelector('dialog[open]:not(.command-palette)')) {
        event.preventDefault();
        if (!open) opener.current = document.activeElement as HTMLElement;
        setOpen((value) => !value);
      }
    };
    document.addEventListener("keydown", shortcut);
    return () => document.removeEventListener("keydown", shortcut);
  }, [open]);
  return <><button type="button" className="palette-trigger button button-ghost" aria-keyshortcuts="Control+k Meta+k" title={t("round5.palette_hint")} onClick={(event) => { opener.current = event.currentTarget; setOpen(true); }}>⌕ <span>Ctrl+K</span></button>{open ? createPortal(<ErrorBoundary fallback={() => null}><PaletteContent currentMap={currentMap} close={() => setOpen(false)} opener={opener.current} /></ErrorBoundary>, document.body) : null}</>;
}

/**
 * Every searchable row, from the one small data/search_index.json (playbook/site_index.py).
 * Labels are composed here so both UI languages share the same file.
 */
function searchEntries(search: SearchIndex | null, index: SiteIndex | null, lang: Lang): Entry[] {
  const maps = (index?.maps ?? []).filter((map) => map.n_matches > 0);
  const entries: Entry[] = maps.map((map) => ({ id: `map:${map.map}`, label: map.display_name, terms: `${map.map} ${map.display_name}`, kind: t("ui.nav_maps"), to: `/${map.map}/tactics` }));
  if (!search) return entries;
  const mapRows = search.maps.rows.map(([map, display]) => ({ map, display, prefix: `${display} ${map}` }));
  const teams = search.teams.rows.map(([slug, team, mapIds]) => ({ slug, team, maps: new Set(mapIds) }));
  const hubTeam = new Map(teams.map((team) => [team.team, team]));
  for (const team of teams) {
    entries.push({ id: `team:${team.slug}`, label: team.team, terms: `${team.team} ${team.slug}`, kind: t("ui.nav_teams"), to: `/teams-hub?${new URLSearchParams({ team: team.slug })}` });
  }
  // Newest first within each team and map, like the hub archive.
  const matches = search.matches.rows.map(([team, map, demo_id, opponent, date, date_precision, event, hltv_match_id]) => ({
    team: teams[team], map: mapRows[map], demo_id, opponent, date, date_precision, event: event == null ? null : search.events[event] ?? null, hltv_match_id,
  })).filter((match) => match.team && match.map);
  const order = new Map(teams.map((team, i) => [team.slug, i]));
  matches.sort((a, b) => (order.get(a.team.slug)! - order.get(b.team.slug)!) || a.map.map.localeCompare(b.map.map) || newestMatch(a, b));
  for (const match of matches) {
    const label = `${match.team.team} vs ${match.opponent ?? "—"} · ${match.map.display} · ${matchDateLabel(match)}`;
    entries.push({ id: `match:${match.map.map}:${match.team.slug}:${match.demo_id}`, label, kind: t("ui.matches_title"),
      terms: `${label} ${match.date ?? ""} ${match.event ?? ""} ${match.demo_id}`,
      to: `/teams-hub?${new URLSearchParams({ team: match.team.slug, map: match.map.map, match: match.demo_id })}` });
  }
  for (const [id, mapId, site, spots] of search.recipes.rows) {
    const map = mapRows[mapId];
    if (!map) continue;
    const names = spots.map(([, place, label, zh, en]) => spotLabel(map.map, { place, label, name: { zh, en } })).join(" + ");
    const label = `${map.display} · ${site} · ${names}`;
    entries.push({ id: `recipe:${id}`, label, kind: t("ui.nav_tactics"), map: map.map,
      terms: `${map.prefix} ${label} ${spots.map(([type, place]) => `${calloutLabel(map.map, place)} ${place ?? ""} ${t(`grenade.${type}`)}`).join(" ")}`,
      to: `/${map.map}/tactics?${new URLSearchParams({ recipe: id, side: "T", site })}` });
  }
  for (const [id, mapId, , type, throwPlace, landPlace, , name] of search.lineups.rows) {
    const map = mapRows[mapId];
    if (!map) continue;
    const named = (lang === "zh" ? name?.[0] ?? name?.[1] : name?.[1] ?? name?.[0]) ?? "";
    const label = `${map.display} · ${calloutLabel(map.map, throwPlace)} → ${calloutLabel(map.map, landPlace)} · ${t(`grenade.${type}`)}${named ? ` · ${named}` : ""}`;
    entries.push({ id: `lineup:${id}`, label, kind: t("ui.nav_lineups"), map: map.map,
      terms: `${map.prefix} ${label} ${throwPlace ?? ""} ${landPlace ?? ""} ${name?.filter(Boolean).join(" ") ?? ""}`,
      to: `/${map.map}/lineups?${new URLSearchParams({ id })}` });
  }
  for (const [steamid, name, rows] of search.players.rows) {
    for (const [mapId, teamName] of rows) {
      const map = mapRows[mapId];
      if (!map) continue;
      const team = teamName ? hubTeam.get(teamName) : undefined;
      const label = `${name} · ${teamName ?? "—"} · ${map.display}`;
      entries.push({ id: `player:${map.map}:${teamName}:${steamid}`, label, kind: t("ui.nav_players"), map: map.map, terms: `${map.prefix} ${label}`,
        to: team?.maps.has(mapId) ? `/teams-hub?${new URLSearchParams({ team: team.slug, map: map.map, player: steamid, side: "T" })}` : `/${map.map}/players?${new URLSearchParams({ player: steamid })}` });
    }
  }
  return entries;
}

function PaletteContent({ currentMap, close, opener }: { currentMap?: string; close: () => void; opener: HTMLElement | null }) {
  const lang = useLang();
  const navigate = useNavigate();
  const dialog = useRef<HTMLDialogElement>(null);
  const index = useData(getIndex, []);
  const search = useData(getSearchIndex, []);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  useLayoutEffect(() => {
    const element = dialog.current;
    const overflow = document.body.style.getPropertyValue("overflow");
    const priority = document.body.style.getPropertyPriority("overflow");
    document.body.style.overflow = "hidden";
    element?.showModal();
    element?.querySelector<HTMLInputElement>('input')?.focus();
    return () => { element?.close(); if (overflow) document.body.style.setProperty("overflow", overflow, priority); else document.body.style.removeProperty("overflow"); if (opener?.isConnected) opener.focus({ preventScroll: true }); };
  }, [opener]);
  // Compact search terms once per language; filtering then is a plain substring scan.
  const all = useMemo(() => searchEntries(search.data, index.data, lang).map((entry) => ({ entry, key: compact(entry.terms) })),
    [search.data, index.data, lang]);
  const tokens = normalise(query).split(/\s+/).filter(Boolean).map(compact);
  const entries = useMemo(() => {
    const hits = all.filter(({ key }) => tokens.every((token) => key.includes(token))).map(({ entry }) => entry);
    // Rows of the map being viewed come before other maps' rows, keeping their order.
    const here = hits.filter((entry) => !entry.map || entry.map === currentMap);
    return (here.length === hits.length ? hits : [...here, ...hits.filter((entry) => entry.map && entry.map !== currentMap)]).slice(0, MAX_RESULTS);
  }, [all, query, currentMap]);
  const selected = Math.min(active, Math.max(0, entries.length - 1));
  const go = (entry: Entry) => { close(); navigate(entry.to); };
  useEffect(() => { dialog.current?.querySelector(`#palette-result-${selected}`)?.scrollIntoView({ block: "nearest" }); }, [selected]);
  const loading = index.loading || search.loading;
  return <dialog ref={dialog} className="command-palette" aria-label={t("round5.palette_hint")} onCancel={(event) => { event.preventDefault(); close(); }} onClick={(event) => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close(); } }} onKeyDown={(event) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); }
    if (event.key === "Tab") { event.preventDefault(); dialog.current?.querySelector<HTMLInputElement>('input')?.focus(); }
    if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); setActive((selected + (event.key === "ArrowDown" ? 1 : -1) + Math.max(1, entries.length)) % Math.max(1, entries.length)); }
    if (event.key === "Enter" && entries[selected]) { event.preventDefault(); go(entries[selected]); }
  }}>
    <label className="sr-only" htmlFor="palette-query">{t("round5.palette_hint")}</label><input id="palette-query" type="search" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="palette-results" aria-activedescendant={entries.length ? `palette-result-${selected}` : undefined} placeholder={t("round5.palette_hint")} value={query} onChange={(event) => { setQuery(event.target.value); setActive(0); }} />
    <div className="palette-results" id="palette-results" role="listbox" aria-label={t("round5.palette_results")}>{entries.map((entry, index) => <div role="option" aria-selected={selected === index} id={`palette-result-${index}`} key={entry.id} onPointerMove={() => setActive(index)} onClick={() => go(entry)}><small>{entry.kind}</small><span>{entry.label}</span></div>)}</div>
    <p role="status">{loading ? t("round5.palette_loading") : !entries.length ? t("round5.palette_empty") : t("round5.palette_count", { n: entries.length })}{search.error || index.error ? ` · ${t("round5.palette_index_error")}` : ""}</p>
  </dialog>;
}
