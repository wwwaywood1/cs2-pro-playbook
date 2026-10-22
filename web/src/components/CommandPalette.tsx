import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { getHeatmapTeams, getIndex, getLineups, getPlayers, getTactics, useData } from "../data";
import { calloutLabel, t, useLang } from "../i18n";

interface Entry { id: string; label: string; terms: string; to: string; kind: string }
const normalise = (value: string) => value.toLocaleLowerCase().replace(/烟雾弹|烟雾/g, "烟").replace(/闪光弹/g, "闪").replace(/燃烧弹|燃烧瓶/g, "火").replace(/de_|[\s_→·+]+/g, " ").trim();
const compact = (value: string) => normalise(value).replace(/\s+/g, "");

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
  return <><button type="button" className="palette-trigger button button-ghost" aria-keyshortcuts="Control+k Meta+k" title={t("round5.palette_hint")} onClick={(event) => { opener.current = event.currentTarget; setOpen(true); }}>⌕ <span>Ctrl+K</span></button>{open ? createPortal(<PaletteContent currentMap={currentMap} close={() => setOpen(false)} opener={opener.current} />, document.body) : null}</>;
}

function PaletteContent({ currentMap, close, opener }: { currentMap?: string; close: () => void; opener: HTMLElement | null }) {
  const lang = useLang();
  const navigate = useNavigate();
  const dialog = useRef<HTMLDialogElement>(null);
  const index = useData(getIndex, []);
  const teams = useData(getHeatmapTeams, []);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [mapEntries, setMapEntries] = useState<Record<string, Entry[]>>({});
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const loaded = useRef(new Set<string>());
  useLayoutEffect(() => {
    const element = dialog.current;
    const overflow = document.body.style.getPropertyValue("overflow");
    const priority = document.body.style.getPropertyPriority("overflow");
    document.body.style.overflow = "hidden";
    element?.showModal();
    element?.querySelector<HTMLInputElement>('input')?.focus();
    return () => { element?.close(); if (overflow) document.body.style.setProperty("overflow", overflow, priority); else document.body.style.removeProperty("overflow"); if (opener?.isConnected) opener.focus({ preventScroll: true }); };
  }, [opener]);
  const tokens = normalise(query).split(/\s+/).filter(Boolean);
  const mapMatches = index.data?.maps.filter((map) => tokens.some((token) => normalise(`${map.map} ${map.display_name}`).includes(token))) ?? [];
  const maps = (mapMatches.length ? mapMatches : query.trim() ? index.data?.maps ?? [] : index.data?.maps.filter((map) => map.map === currentMap) ?? []).filter((map) => map.n_matches > 0);
  const loadKey = maps.map((map) => map.map).join(",");
  useEffect(() => {
    let alive = true;
    if (teams.loading) return;
    const requested = maps.filter((map) => !loaded.current.has(map.map));
    if (!requested.length) { setLoading(false); return; }
    setLoading(true); setFailed(false);
    const timer = window.setTimeout(async () => {
      const rows = await Promise.all(requested.map(async (map) => {
        const results = await Promise.allSettled([getTactics(map.map), getLineups(map.map), getPlayers(map.map)]);
        const entries: Entry[] = [];
        const prefix = `${map.display_name} ${map.map}`;
        const tactics = results[0], lineups = results[1], players = results[2];
        if (tactics.status === "fulfilled") for (const recipe of tactics.value.recipes) {
          const spots = [...recipe.core, ...recipe.options];
          const names = spots.map((spot) => spot.name?.[lang] || spot.label).join(" + ");
          const label = `${map.display_name} · ${recipe.site} · ${names}`;
          entries.push({ id: `recipe:${recipe.id}`, label, kind: t("ui.nav_tactics"), terms: `${prefix} ${label} ${spots.map((spot) => `${calloutLabel(map.map, spot.place)} ${spot.place ?? ""} ${t(`grenade.${spot.type}`)}`).join(" ")}`, to: `/${map.map}/tactics?${new URLSearchParams({ recipe: recipe.id, side: "T", site: recipe.site })}` });
        }
        if (lineups.status === "fulfilled") for (const lineup of lineups.value) {
          const label = `${map.display_name} · ${calloutLabel(map.map, lineup.throw_place)} → ${calloutLabel(map.map, lineup.land_place)} · ${t(`grenade.${lineup.type}`)}`;
          entries.push({ id: `lineup:${lineup.id}`, label, kind: t("ui.nav_lineups"), terms: `${prefix} ${label} ${lineup.throw_place ?? ""} ${lineup.land_place ?? ""}`, to: `/${map.map}/lineups?${new URLSearchParams({ id: lineup.id })}` });
        }
        if (players.status === "fulfilled") for (const player of players.value) {
          const team = teams.data?.find((team) => team.team === player.team && team.maps.some((item) => item.map === map.map));
          const label = `${player.name} · ${player.team} · ${map.display_name}`;
          entries.push({ id: `player:${map.map}:${player.team}:${player.steamid}`, label, kind: t("ui.nav_players"), terms: `${prefix} ${label}`, to: team ? `/teams-hub?${new URLSearchParams({ team: team.slug, map: map.map, player: player.steamid, side: "T" })}` : `/${map.map}/players?${new URLSearchParams({ player: player.steamid })}` });
        }
        return { map: map.map, entries, complete: results.every((result) => result.status === "fulfilled") };
      }));
      if (!alive) return;
      for (const row of rows) if (row.complete) loaded.current.add(row.map);
      setMapEntries((old) => ({ ...old, ...Object.fromEntries(rows.map((row) => [row.map, row.entries])) }));
      setFailed(rows.some((row) => !row.complete)); setLoading(false);
    }, 180);
    return () => { alive = false; window.clearTimeout(timer); };
  }, [loadKey, lang, teams.data, teams.loading]);
  const entries = useMemo(() => {
    const all: Entry[] = [
      ...(index.data?.maps.filter((map) => map.n_matches > 0).map((map) => ({ id: `map:${map.map}`, label: map.display_name, terms: `${map.map} ${map.display_name}`, kind: t("ui.nav_maps"), to: `/${map.map}/tactics` })) ?? []),
      ...(teams.data?.map((team) => ({ id: `team:${team.slug}`, label: team.team, terms: `${team.team} ${team.slug}`, kind: t("ui.nav_teams"), to: `/teams-hub?${new URLSearchParams({ team: team.slug })}` })) ?? []),
      ...Object.values(mapEntries).flat(),
    ];
    return all.filter((entry) => tokens.every((token) => compact(entry.terms).includes(compact(token)))).slice(0, 80);
  }, [index.data, teams.data, mapEntries, query, lang]);
  const selected = Math.min(active, Math.max(0, entries.length - 1));
  const go = (entry: Entry) => { close(); navigate(entry.to); };
  useEffect(() => { dialog.current?.querySelector(`#palette-result-${selected}`)?.scrollIntoView({ block: "nearest" }); }, [selected]);
  return <dialog ref={dialog} className="command-palette" aria-label={t("round5.palette_hint")} onCancel={(event) => { event.preventDefault(); close(); }} onClick={(event) => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close(); } }} onKeyDown={(event) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); }
    if (event.key === "Tab") { event.preventDefault(); dialog.current?.querySelector<HTMLInputElement>('input')?.focus(); }
    if (["ArrowDown", "ArrowUp"].includes(event.key)) { event.preventDefault(); setActive((selected + (event.key === "ArrowDown" ? 1 : -1) + Math.max(1, entries.length)) % Math.max(1, entries.length)); }
    if (event.key === "Enter" && entries[selected]) { event.preventDefault(); go(entries[selected]); }
  }}>
    <label className="sr-only" htmlFor="palette-query">{t("round5.palette_hint")}</label><input id="palette-query" type="search" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="palette-results" aria-activedescendant={entries.length ? `palette-result-${selected}` : undefined} placeholder={t("round5.palette_hint")} value={query} onChange={(event) => { setQuery(event.target.value); setActive(0); }} />
    <div className="palette-results" id="palette-results" role="listbox" aria-label="搜索结果">{entries.map((entry, index) => <div role="option" aria-selected={selected === index} id={`palette-result-${index}`} key={entry.id} onPointerMove={() => setActive(index)} onClick={() => go(entry)}><small>{entry.kind}</small><span>{entry.label}</span></div>)}</div>
    <p role="status">{loading || index.loading ? "加载中…" : !entries.length ? t("round5.palette_empty") : `${entries.length} 条结果 · ↑/↓ 选择 · Enter 打开 · Esc 关闭`}{failed || index.error || teams.error ? " · 部分数据加载失败，可重新打开重试" : ""}</p>
  </dialog>;
}
