import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import GrenadeIcon, { GrenadeGlyph } from "./GrenadeIcon";
import { useMapLink } from "../mapLink";
import { calloutLabel, t } from "../i18n";
import { fmtPct, fmtInt } from "../format";
import type { Lineup, Recipe, RecipeRoute, Spot } from "../types";

export interface RecipeSpot {
  id: string;
  type: Spot["type"];
  spot: Spot | undefined;
  core: boolean;
  number: number;
  name: string;
  share: number | null;
  to: string | null;
  lineup?: Lineup;
  thrower?: string | null;
  throwerTeam?: string | null;
  throwPlace?: string | null;
  order?: number | null;
}

interface ViewBox { x: number; y: number; size: number }
const FULL_VIEW: ViewBox = { x: 0, y: 0, size: 1024 };

interface RadarPoint { x: number; y: number }
// Mean plant positions, matching playbook/tactics.py:site_centres, transformed
// with each map's radar metadata. Keep these frontend-only anchors in radar px.
const SITE_CENTRES: Record<string, Record<Recipe["site"], RadarPoint> | undefined> = {
  de_ancient: { A: { x: 324.1, y: 282.0 }, B: { x: 759.1, y: 426.0 } },
  de_anubis: { A: { x: 770.8, y: 263.4 }, B: { x: 329.4, y: 512.2 } },
  de_dust2: { A: { x: 800.8, y: 184.6 }, B: { x: 213.3, y: 162.2 } },
  de_inferno: { A: { x: 820.4, y: 701.6 }, B: { x: 528.8, y: 205.1 } },
  de_mirage: { A: { x: 564.1, y: 759.2 }, B: { x: 251.8, y: 267.8 } },
  de_nuke: { A: { x: 583.6, y: 526.0 }, B: { x: 572.4, y: 561.2 } },
  de_overpass: { A: { x: 454.6, y: 221.9 }, B: { x: 701.7, y: 352.5 } },
};

function fitSpots(entries: RecipeSpot[], scale: number | undefined, siteCentre?: RadarPoint, routePoints: RadarPoint[] = []): ViewBox {
  const points = entries.flatMap(({ spot, type }) => spot && Number.isFinite(spot.radar_x) && Number.isFinite(spot.radar_y)
    ? [{ x: spot.radar_x, y: spot.radar_y, radius: scale ? (type === "smoke" ? 144 : type === "molotov" ? 120 : 0) / scale : 0 }] : []);
  for (const { lineup } of entries) if (lineup && Number.isFinite(lineup.throw.radar_x) && Number.isFinite(lineup.throw.radar_y)) {
    points.push({ x: lineup.throw.radar_x, y: lineup.throw.radar_y, radius: 12 });
    points.push({ x: lineup.land.radar_x, y: lineup.land.radar_y, radius: 12 });
  }
  for (const point of routePoints) points.push({ ...point, radius: 12 });
  if (!points.length) return FULL_VIEW;
  const left = Math.min(...points.map((p) => p.x - p.radius));
  const right = Math.max(...points.map((p) => p.x + p.radius));
  const top = Math.min(...points.map((p) => p.y - p.radius));
  const bottom = Math.max(...points.map((p) => p.y + p.radius));
  const cx = (left + right) / 2;
  const cy = (top + bottom) / 2;
  const size = Math.min(1024, Math.max(1024 * 0.6, right - left + 112, bottom - top + 112,
    siteCentre ? Math.abs(siteCentre.x - cx) * 2 + 112 : 0,
    siteCentre ? Math.abs(siteCentre.y - cy) * 2 + 112 : 0));
  return { size, x: Math.max(0, Math.min(1024 - size, cx - size / 2)),
    y: Math.max(0, Math.min(1024 - size, cy - size / 2)) };
}

/** Catmull–Rom interpolation retains the exported medoid's sample points. */
function routePath(points: [number, number][]) {
  return points.reduce((path, point, index) => {
    if (!index) return `M ${point[0]} ${point[1]}`;
    const previous = points[index - 1];
    const before = points[Math.max(0, index - 2)];
    const after = points[Math.min(points.length - 1, index + 1)];
    return `${path} C ${previous[0] + (point[0] - before[0]) / 6} ${previous[1] + (point[1] - before[1]) / 6}, ${point[0] - (after[0] - previous[0]) / 6} ${point[1] - (after[1] - previous[1]) / 6}, ${point[0]} ${point[1]}`;
  }, "");
}

function routeLabelPoint(points: [number, number][]): [number, number] {
  const lengths = points.slice(1).map((point, index) => Math.hypot(point[0] - points[index][0], point[1] - points[index][1]));
  let remaining = lengths.reduce((total, length) => total + length, 0) * 2 / 3;
  for (let index = 0; index < lengths.length; index++) {
    if (remaining <= lengths[index]) {
      const ratio = lengths[index] ? remaining / lengths[index] : 0;
      return [points[index][0] + (points[index + 1][0] - points[index][0]) * ratio,
        points[index][1] + (points[index + 1][1] - points[index][1]) * ratio];
    }
    remaining -= lengths[index];
  }
  return points[points.length - 1];
}

/** SVG is rendered by the browser at devicePixelRatio, including all vector overlays. */
export default function RecipeRadar({ map, spots, scale, site, title, selectionLabel, routes, routeKey }: { routes?: RecipeRoute[]; routeKey?: string; map: string; spots: RecipeSpot[]; scale: number | undefined; site?: Recipe["site"]; title: string; selectionLabel?: string }) {
  const { activeId, bind } = useMapLink();
  const entryRoutes = useMemo(() => (routes ?? []).filter((route) => Number.isFinite(route.share) && route.points.length >= 2
    && route.points.every((point) => point.length === 2 && point.every(Number.isFinite))), [routes]);
  const [full, setFull] = useState(false);
  const [chosenLevel, setChosenLevel] = useState<number | null>(null);
  const [activeRoute, setActiveRoute] = useState<number | null>(null);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const [width, setWidth] = useState(640);
  const [pixelRatio, setPixelRatio] = useState(1);
  const host = useRef<HTMLElement>(null);
  const radar = useRef<SVGSVGElement>(null);
  const maskId = useId();
  const levels = [...new Set(spots.flatMap(({ spot }) => spot ? [spot.level] : []))].sort();
  const linkedSpot = spots.find((entry) => activeId === `spot:${entry.id}`)?.spot;
  const level = linkedSpot?.level ?? (chosenLevel !== null && levels.includes(chosenLevel) ? chosenLevel : levels[0] ?? 0);
  const visible = useMemo(() => spots.filter(({ spot }) => spot?.level === level), [spots, level]);
  const siteCentre = site ? SITE_CENTRES[map]?.[site] : undefined;
  const focus = useMemo(() => site && !siteCentre ? FULL_VIEW : fitSpots(visible, scale, siteCentre, entryRoutes.flatMap((route) => route.points.map(([x, y]) => ({ x, y })))), [visible, scale, site, siteCentre, entryRoutes]);
  // Leave a little context around the focus box so the dimmed perimeter remains visible.
  const target = useMemo(() => {
    if (full) return FULL_VIEW;
    // Cap raster enlargement in physical pixels, including high-DPI screens.
    const size = Math.min(1024, Math.max(focus.size * 1.12, width * pixelRatio / 1.6));
    return { size, x: Math.max(0, Math.min(1024 - size, focus.x - (size - focus.size) / 2)),
      y: Math.max(0, Math.min(1024 - size, focus.y - (size - focus.size) / 2)) };
  }, [focus, full, width, pixelRatio]);
  const [view, setView] = useState(FULL_VIEW);
  const currentView = useRef(view);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = currentView.current;
    let frame = 0;
    const began = performance.now();
    const animate = (now: number) => {
      const progress = reduced ? 1 : Math.min(1, (now - began) / 280);
      const eased = 1 - (1 - progress) ** 3;
      const next = { x: start.x + (target.x - start.x) * eased, y: start.y + (target.y - start.y) * eased,
        size: start.size + (target.size - start.size) * eased };
      currentView.current = next;
      setView(next);
      if (progress < 1) frame = window.requestAnimationFrame(animate);
    };
    frame = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frame);
  }, [target]);
  useEffect(() => {
    const element = host.current;
    const svg = radar.current;
    if (!element || !svg) return;
    const workspace = element.closest<HTMLElement>(".tactics-workspace");
    const panel = element.closest<HTMLElement>(".tactics-map-panel");
    const page = element.closest<HTMLElement>(".tactics-page");
    const topbar = document.querySelector<HTMLElement>(".topbar");
    const measure = () => {
      const dpr = window.devicePixelRatio || 1;
      setPixelRatio(dpr);
      element.style.setProperty("--tactics-raster-limit", `${1024 * 1.6 / dpr}px`);
      const stickyTop = panel ? parseFloat(window.getComputedStyle(panel).top) || 0 : 0;
      // The workspace stays in normal flow while its map panel sticks. Reserve
      // its initial viewport offset as well as the caption/floor controls.
      const workspaceTop = workspace ? workspace.getBoundingClientRect().top + window.scrollY : stickyTop;
      const controlsHeight = svg.getBoundingClientRect().top - element.getBoundingClientRect().top;
      element.style.setProperty("--tactics-radar-top", `${Math.max(stickyTop, workspaceTop) + controlsHeight}px`);
      const renderedWidth = svg.getBoundingClientRect().width;
      if (renderedWidth > 0) setWidth(renderedWidth);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    observer.observe(svg);
    if (page) observer.observe(page);
    if (topbar) observer.observe(topbar);
    window.addEventListener("resize", measure);
    measure();
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, []);
  const source = `${import.meta.env.BASE_URL}radars/${map}${level === 1 ? "_lower" : ""}.png`;
  const unit = view.size / width;
  return <figure className="tactics-radar-wrap" ref={host}>
    <figcaption className="tactics-map-head">
      <div><h2>{title}</h2><p className="muted tactics-selection-label" aria-live="polite">{selectionLabel || t("tactics.map_hint")}</p></div>
      <button type="button" className="button button-ghost" aria-pressed={full} onClick={() => setFull((value) => !value)}>{t("tactics.full_map")}</button>
    </figcaption>
    {map === "de_nuke" && <div className="segmented tactics-levels" role="group" aria-label={t("tactics.floor")}>
      {[0, 1].map((value) => <button key={value} type="button" aria-pressed={level === value} disabled={!levels.includes(value)}
        className={level === value ? "is-active" : ""} onClick={() => setChosenLevel(value)}>
        {t(`heatmap.level.${value === 1 ? "lower" : "upper"}`)} ({fmtInt(spots.filter(({ spot }) => spot?.level === value).length)})
      </button>)}
    </div>}
    <svg ref={radar} className="radar tactics-radar" viewBox={`${view.x} ${view.y} ${view.size} ${view.size}`} role="group" aria-label={t("tactics.radar_label", { map })}>
      <defs>
        <marker id={`${maskId}-entry-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 Z" fill="#efad55" /></marker>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024"><rect width="1024" height="1024" fill="white" /><rect x={focus.x} y={focus.y} width={focus.size} height={focus.size} fill="black" /></mask>
        <radialGradient id={`${maskId}-smoke`}><stop offset="0" stopColor="#d4dae0" stopOpacity="0.4" /><stop offset="0.75" stopColor="#c6ced8" stopOpacity="0.25" /><stop offset="1" stopColor="#c6ced8" stopOpacity="0.04" /></radialGradient>
        <radialGradient id={`${maskId}-molotov`}><stop offset="0" stopColor="#ff853d" stopOpacity="0.42" /><stop offset="0.7" stopColor="#ff853d" stopOpacity="0.28" /><stop offset="1" stopColor="#ff853d" stopOpacity="0.04" /></radialGradient>
      </defs>
      <rect className="radar-bg" width="1024" height="1024" />
      {failedSource !== source && <image href={source} width="1024" height="1024" onError={() => setFailedSource(source)} />}
      <rect width="1024" height="1024" fill="#060b12" opacity="0.55" mask={`url(#${maskId})`} pointerEvents="none" />
      <g className="tactics-entry-routes" key={routeKey} pointerEvents="none">{entryRoutes.map((route, index) => {
        const label = t("round3.route_label", { via: route.via.map((place) => calloutLabel(map, place)).join(" → "), p: fmtPct(route.share) });
        const [x, y] = routeLabelPoint(route.points);
        return <g key={index} opacity={Math.max(.3, .9 - index * .17)}
          className={activeRoute === null ? undefined : activeRoute === index ? "is-active" : "is-dimmed"}>
          <title>{label}</title>
          <path className="tactics-entry-path" d={routePath(route.points)} pathLength={1} strokeWidth={2 + Math.max(0, Math.min(1, route.share)) * 4} markerEnd={`url(#${maskId}-entry-arrow)`} vectorEffect="non-scaling-stroke" />
          <circle className="tactics-route-dot" cx={x} cy={y} r={7 * unit} />
          <text className="tactics-route-num" x={x} y={y + 3 * unit} textAnchor="middle" fontSize={9 * unit}>{"abcd"[index]}</text>
        </g>;
      })}</g>
      {visible.filter((entry) => entry.lineup).map((entry) => {
        const lineup = entry.lineup!;
        return <g className="tactics-throw-route" key={`route-${entry.id}`} opacity={entry.core ? .85 : .4}>
          <title>{`${fmtInt(entry.number)}. ${calloutLabel(map, lineup.throw_place)} → ${entry.name} · 最常用起投点`}</title>
          <line x1={lineup.throw.radar_x} y1={lineup.throw.radar_y} x2={lineup.land.radar_x} y2={lineup.land.radar_y} vectorEffect="non-scaling-stroke" />
          <circle cx={lineup.throw.radar_x} cy={lineup.throw.radar_y} r={4 * unit} />
        </g>;
      })}
      {visible.map((entry) => {
        const spot = entry.spot;
        if (!spot || !Number.isFinite(spot.radar_x) || !Number.isFinite(spot.radar_y)) return null;
        const radius = scale && (entry.type === "smoke" || entry.type === "molotov") ? (entry.type === "smoke" ? 144 : 120) / scale : null;
        const label = `${fmtInt(entry.number)}. ${entry.name} · ${t(`grenade.${entry.type}`)} · ${t(entry.core ? "tactics.core" : "tactics.optional")}`;
        const marker = <g transform={`translate(${spot.radar_x}, ${spot.radar_y})`} opacity={entry.core ? 1 : 0.5}>
          {radius !== null && <circle r={radius} fill={`url(#${maskId}-${entry.type})`} className={`tactics-effect tactics-effect-${entry.type}`} strokeDasharray={entry.core ? undefined : "5 4"} vectorEffect="non-scaling-stroke" />}
          <circle className="map-link-ring" r={22 * unit} />
          <g transform={`scale(${unit})`}>
            {!entry.core && <circle r="17" fill="none" stroke="#8fa3bd" strokeWidth="1" strokeDasharray="4 3" />}
            <g className="tactics-marker-icon" transform="translate(-14 -14) scale(0.875)"><GrenadeGlyph type={entry.type} /></g>
            <g transform="translate(15 -15)"><circle r="8" fill="#0b1220" /><text className="tactics-marker-number" textAnchor="middle" y="4">{fmtInt(entry.number)}</text></g>
          </g>
        </g>;
        return entry.to ? <a key={entry.id} {...bind(`spot:${entry.id}`)} href={`#${entry.to}`} aria-label={`${label} · ${t("tactics.open_lineup")}`}><title>{label}</title>{marker}</a>
          : <g key={entry.id} {...bind(`spot:${entry.id}`)} tabIndex={0} role="img" aria-label={label}><title>{label}</title>{marker}</g>;
      })}
    </svg>
    {routes !== undefined ? <div className="tactics-routes-legend"><strong tabIndex={0} title={t("round3.routes_tip")}>{t("round3.routes_title")} ⓘ</strong>
      {!entryRoutes.length ? <p className="muted">{t("round3.routes_none")}</p> : entryRoutes.map((route, index) => {
        const label = t("round3.route_label", { via: route.via.map((place) => calloutLabel(map, place)).join(" → "), p: fmtPct(route.share) });
        return <button key={index} type="button" className="tactics-route-row"
          onMouseEnter={() => setActiveRoute(index)} onMouseLeave={() => setActiveRoute(null)}
          onFocus={() => setActiveRoute(index)} onBlur={() => setActiveRoute(null)}>
          <span className="tactics-route-swatch" aria-hidden="true" style={{ opacity: Math.max(.3, .9 - index * .17) }} />
          <span className="tactics-route-badge" aria-hidden="true">{"abcd"[index]}</span>
          <span className="tactics-route-text">{label}</span>
        </button>;
      })}
    </div> : null}
    {!visible.length && <p className="muted">{t("tactics.no_spots")}</p>}
    {failedSource === source && <p className="muted">{t("tactics.radar_unavailable")}</p>}
    {!scale && <p className="muted">{t("tactics.no_scale")}</p>}
    <p className="tactics-help muted">{t("tactics.radar_help")} · 细线：最常用起投点 → 落点；非队员移动路线</p>
    {!!visible.length && <details className="tactics-map-spots"><summary>{t("tactics.spot_index", { n: fmtInt(visible.length) })}</summary><SpotList entries={visible} /></details>}
  </figure>;
}

export function SpotList({ entries }: { entries: RecipeSpot[] }) {
  const { bind } = useMapLink();
  return <ul className="tactics-spots">{[...entries].sort((a, b) => (a.order ?? Infinity) - (b.order ?? Infinity)).map((entry) => <li key={entry.id} {...bind(`spot:${entry.id}`)} tabIndex={0} className={entry.core ? "" : "is-optional"}>
    <GrenadeIcon type={entry.type} /><span>{fmtInt(entry.number)}. {entry.to ? <Link to={entry.to} title={t("tactics.open_lineup")}>{entry.name}</Link> : entry.name}
      <span className="muted"> · {t(`grenade.${entry.type}`)}{entry.share !== null ? ` · ${fmtPct(entry.share)}` : ""}</span>
      <small className="recipe-assignment muted">{t("round4.throw_from", { place: entry.throwPlace ?? entry.lineup?.throw_place ?? "—" })}</small>
      {entry.thrower ? <small className="recipe-assignment muted">{t("round4.thrower_example", { name: entry.thrower, team: entry.throwerTeam || "—" })}</small> : null}
      {!entry.spot && <span className="muted"> · {t("tactics.position_missing")}</span>}
    </span>
  </li>)}</ul>;
}

