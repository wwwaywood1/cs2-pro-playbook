import CountUp from "../components/CountUp";
import { Reveal } from "../components/Motion";
import type { CSSProperties } from "react";
import { PageContext, PageSurface } from "../components/Page";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import GrenadeIcon, { GrenadeGlyph } from "../components/GrenadeIcon";
import Stat from "../components/Stat";
import { ErrorNotice, Loading } from "../components/Status";
import { getLineups, getMeta, getTactics, useData } from "../data";
import { fmtInt, fmtNum, fmtPct, fmtSeconds } from "../format";
import { calloutLabel, t, useLang, type Lang } from "../i18n";
import type { CTTactics, Lineup, Ranked, Recipe, Spot, SpotRef, TTactics } from "../types";
import "../tactics.css";

function siteLabel(site: string): string {
  return site === "A" || site === "B" ? t(`region.${site}_SITE`) : t("tactics.no_target");
}

function ShareBars({ rows, labelFor }: { rows: Ranked[]; labelFor: (value: string) => string }) {
  if (!rows.length) return <p className="muted">{t("tactics.no_data")}</p>;
  return (
    <ul className="ranked-list">
      {rows.map((row) => (
        <li key={row.value} className="ranked-row">
          <div className="ranked-head">
            <span>{labelFor(row.value)}</span>
            <span className="ranked-count">{t("tactics.round_count", { n: fmtInt(row.rounds) })}</span>
          </div>
          <div className="bar-track" aria-hidden="true">
            <div className="bar-fill" style={{ width: `${Math.max(0, Math.min(1, row.share ?? 0)) * 100}%` }} />
          </div>
          <div className="ranked-meta">{fmtPct(row.share)}</div>
        </li>
      ))}
    </ul>
  );
}

function TOverview({ data }: { data: TTactics }) {
  return (
    <section className="panel">
      <h2>{t("tactics.t_overview")}</h2>
      <p className="muted">{t("tactics.gun_rounds", { n: fmtInt(data.gun_rounds) })}</p>
      <div className="two-col">
        <div>
          <h3>{t("tactics.tempo_title")}</h3>
          <ShareBars rows={data.tempo} labelFor={(value) => t(`tactics.tempo.${value}`)} />
        </div>
        <div>
          <h3>{t("tactics.target")}</h3>
          <ShareBars rows={data.target} labelFor={siteLabel} />
        </div>
      </div>
      <div className="stat-row">
        <Stat label={t("tactics.avg_commit")} value={fmtSeconds(data.avg_commit_s)} />
        <Stat label="多方向进点率" title="进点位置相距至少 400 游戏单位，或相对包点中心的方位角相差至少 50°；不限定中路。" value={fmtPct(data.split_rate)} />
        <Stat label={t("tactics.lurk_rate")} value={fmtPct(data.lurk_rate)} />
        <Stat label={t("tactics.fake_rate")} value={fmtPct(data.fake_rate)} />
      </div>
      <h3>{t("tactics.lurkers")}</h3>
      {data.lurkers.length ? (
        <ul className="tactics-people">
          {[...data.lurkers].sort((a, b) => b.rounds - a.rounds).slice(0, 5).map((player) => (
            <li key={player.steamid}>{player.name || player.steamid} · {t("tactics.round_count", { n: fmtInt(player.rounds) })}</li>
          ))}
        </ul>
      ) : <p className="muted">{t("tactics.no_data")}</p>}
    </section>
  );
}

function CTOverview({ data }: { data: CTTactics }) {
  return (
    <section className="panel">
      <h2>{t("tactics.ct_overview")}</h2>
      <p className="muted">{t("tactics.gun_rounds", { n: fmtInt(data.gun_rounds) })}</p>
      <h3>{t("tactics.setups")}</h3>
      <p className="muted tactics-help">{t("ui.setup_shape_help")}</p>
      <ShareBars rows={[...data.setups_20s].sort((a, b) => b.rounds - a.rounds).slice(0, 6)} labelFor={(value) => value} />
      <div className="stat-row">
        <Stat label={t("tactics.forward_rate")} value={fmtPct(data.forward_rate)} />
        <Stat label={t("tactics.stack_rate")} value={fmtPct(data.stack_rate)} />
      </div>
      <h3>{t("tactics.forward_players")}</h3>
      {data.forward_players.length ? (
        <ul className="tactics-people">
          {[...data.forward_players].sort((a, b) => b.rounds - a.rounds).slice(0, 5).map((player) => (
            <li key={player.steamid}>
              {player.name || player.steamid} · {fmtPct(player.share)} · {t("tactics.round_count", { n: fmtInt(player.rounds) })}
            </li>
          ))}
        </ul>
      ) : <p className="muted">{t("tactics.no_data")}</p>}
      <h3>{t("tactics.stacked_site")}</h3>
      <ShareBars rows={data.stacks} labelFor={siteLabel} />
      <h3>{t("tactics.rotation")}</h3>
      <p className="muted">{t("tactics.round_count", { n: fmtInt(data.rotation.rounds) })}</p>
      <div className="stat-row">
        <Stat label={t("tactics.far_players")} value={fmtNum(data.rotation.avg_far_players)} />
        <Stat label={t("tactics.rotated")} value={fmtNum(data.rotation.avg_rotated)} />
        <Stat label={t("tactics.rotation_delay")} value={fmtSeconds(data.rotation.avg_delay_s)} />
        <Stat label={t("tactics.pre_rotated")} value={fmtNum(data.rotation.avg_pre_rotated)} />
      </div>
    </section>
  );
}

interface RecipeSpot {
  id: string;
  type: Spot["type"];
  spot: Spot | undefined;
  core: boolean;
  number: number;
  name: string;
  share: number | null;
  to: string | null;
  lineup?: Lineup;
}

function resolveSpot(map: string, ref: SpotRef, spot: Spot | undefined, core: boolean, number: number, lang: Lang, byLineup: Map<string, Lineup>): RecipeSpot {
  const lineups = ref.lineups.length ? ref.lineups : spot?.lineups ?? [];
  const mostThrown = [...lineups].sort((a, b) => b.n_throws - a.n_throws)[0];
  return {
    lineup: mostThrown ? byLineup.get(mostThrown.lineup_id) : undefined,
    id: ref.spot_id, type: ref.type, spot, core, number, share: ref.share,
    name: ref.name?.[lang] || spot?.name?.[lang] || ref.label,
    to: mostThrown ? `/${encodeURIComponent(map)}/lineups?${new URLSearchParams({ id: mostThrown.lineup_id })}` : null,
  };
}

function recipeSpots(map: string, recipe: Recipe, byId: Map<string, Spot>, lang: Lang, byLineup: Map<string, Lineup>): RecipeSpot[] {
  return [...recipe.core.map((ref) => ({ ref, core: true })), ...recipe.options.map((ref) => ({ ref, core: false }))]
    .map(({ ref, core }, index) => resolveSpot(map, ref, byId.get(ref.spot_id), core, index + 1, lang, byLineup));
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

function fitSpots(entries: RecipeSpot[], scale: number | undefined, siteCentre?: RadarPoint): ViewBox {
  const points = entries.flatMap(({ spot, type }) => spot && Number.isFinite(spot.radar_x) && Number.isFinite(spot.radar_y)
    ? [{ x: spot.radar_x, y: spot.radar_y, radius: scale ? (type === "smoke" ? 144 : type === "molotov" ? 120 : 0) / scale : 0 }] : []);
  for (const { lineup } of entries) if (lineup && Number.isFinite(lineup.throw.radar_x) && Number.isFinite(lineup.throw.radar_y)) {
    points.push({ x: lineup.throw.radar_x, y: lineup.throw.radar_y, radius: 12 });
    points.push({ x: lineup.land.radar_x, y: lineup.land.radar_y, radius: 12 });
  }
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

/** SVG is rendered by the browser at devicePixelRatio, including all vector overlays. */
function RecipeRadar({ map, spots, scale, site, title, selectionLabel }: { map: string; spots: RecipeSpot[]; scale: number | undefined; site?: Recipe["site"]; title: string; selectionLabel?: string }) {
  const [full, setFull] = useState(false);
  const [chosenLevel, setChosenLevel] = useState<number | null>(null);
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const [width, setWidth] = useState(640);
  const [pixelRatio, setPixelRatio] = useState(1);
  const host = useRef<HTMLElement>(null);
  const radar = useRef<SVGSVGElement>(null);
  const maskId = useId();
  const levels = [...new Set(spots.flatMap(({ spot }) => spot ? [spot.level] : []))].sort();
  const level = chosenLevel !== null && levels.includes(chosenLevel) ? chosenLevel : levels[0] ?? 0;
  const visible = useMemo(() => spots.filter(({ spot }) => spot?.level === level), [spots, level]);
  const siteCentre = site ? SITE_CENTRES[map]?.[site] : undefined;
  const focus = useMemo(() => site && !siteCentre ? FULL_VIEW : fitSpots(visible, scale, siteCentre), [visible, scale, site, siteCentre]);
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
        {t(`heatmap.level.${value === 1 ? "lower" : "upper"}`)} ({spots.filter(({ spot }) => spot?.level === value).length})
      </button>)}
    </div>}
    <svg ref={radar} className="radar tactics-radar" viewBox={`${view.x} ${view.y} ${view.size} ${view.size}`} role="group" aria-label={t("tactics.radar_label", { map })}>
      <defs>
        <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024"><rect width="1024" height="1024" fill="white" /><rect x={focus.x} y={focus.y} width={focus.size} height={focus.size} fill="black" /></mask>
        <radialGradient id={`${maskId}-smoke`}><stop offset="0" stopColor="#d4dae0" stopOpacity="0.4" /><stop offset="0.75" stopColor="#c6ced8" stopOpacity="0.25" /><stop offset="1" stopColor="#c6ced8" stopOpacity="0.04" /></radialGradient>
        <radialGradient id={`${maskId}-molotov`}><stop offset="0" stopColor="#ff853d" stopOpacity="0.42" /><stop offset="0.7" stopColor="#ff853d" stopOpacity="0.28" /><stop offset="1" stopColor="#ff853d" stopOpacity="0.04" /></radialGradient>
      </defs>
      <rect className="radar-bg" width="1024" height="1024" />
      {failedSource !== source && <image href={source} width="1024" height="1024" onError={() => setFailedSource(source)} />}
      <rect width="1024" height="1024" fill="#060b12" opacity="0.55" mask={`url(#${maskId})`} pointerEvents="none" />
      {visible.filter((entry) => entry.lineup).map((entry) => {
        const lineup = entry.lineup!;
        return <g className="tactics-throw-route" key={`route-${entry.id}`} opacity={entry.core ? .85 : .4}>
          <title>{`${entry.number}. ${calloutLabel(map, lineup.throw_place)} → ${entry.name} · 最常用起投点`}</title>
          <line x1={lineup.throw.radar_x} y1={lineup.throw.radar_y} x2={lineup.land.radar_x} y2={lineup.land.radar_y} vectorEffect="non-scaling-stroke" />
          <circle cx={lineup.throw.radar_x} cy={lineup.throw.radar_y} r={4 * unit} />
        </g>;
      })}
      {visible.map((entry) => {
        const spot = entry.spot;
        if (!spot || !Number.isFinite(spot.radar_x) || !Number.isFinite(spot.radar_y)) return null;
        const radius = scale && (entry.type === "smoke" || entry.type === "molotov") ? (entry.type === "smoke" ? 144 : 120) / scale : null;
        const label = `${entry.number}. ${entry.name} · ${t(`grenade.${entry.type}`)} · ${t(entry.core ? "tactics.core" : "tactics.optional")}`;
        const marker = <g transform={`translate(${spot.radar_x}, ${spot.radar_y})`} opacity={entry.core ? 1 : 0.5}>
          {radius !== null && <circle r={radius} fill={`url(#${maskId}-${entry.type})`} className={`tactics-effect tactics-effect-${entry.type}`} strokeDasharray={entry.core ? undefined : "5 4"} vectorEffect="non-scaling-stroke" />}
          <g transform={`scale(${unit})`}>
            {!entry.core && <circle r="17" fill="none" stroke="#8fa3bd" strokeWidth="1" strokeDasharray="4 3" />}
            <g className="tactics-marker-icon" transform="translate(-14 -14) scale(0.875)"><GrenadeGlyph type={entry.type} /></g>
            <g transform="translate(15 -15)"><circle r="8" fill="#0b1220" /><text className="tactics-marker-number" textAnchor="middle" y="4">{entry.number}</text></g>
          </g>
        </g>;
        return entry.to ? <a key={entry.id} href={`#${entry.to}`} aria-label={`${label} · ${t("tactics.open_lineup")}`}><title>{label}</title>{marker}</a>
          : <g key={entry.id}><title>{label}</title>{marker}</g>;
      })}
    </svg>
    {!visible.length && <p className="muted">{t("tactics.no_spots")}</p>}
    {failedSource === source && <p className="muted">{t("tactics.radar_unavailable")}</p>}
    {!scale && <p className="muted">{t("tactics.no_scale")}</p>}
    <p className="tactics-help muted">{t("tactics.radar_help")} · 细线：最常用起投点 → 落点；非队员移动路线</p>
    {!!visible.length && <details className="tactics-map-spots"><summary>{t("tactics.spot_index", { n: visible.length })}</summary><SpotList entries={visible} /></details>}
  </figure>;
}

function SpotList({ entries }: { entries: RecipeSpot[] }) {
  return <ul className="tactics-spots">{entries.map((entry) => <li key={entry.id} className={entry.core ? "" : "is-optional"}>
    <GrenadeIcon type={entry.type} /><span>{entry.number}. {entry.to ? <Link to={entry.to} title={t("tactics.open_lineup")}>{entry.name}</Link> : entry.name}
      <span className="muted"> · {t(`grenade.${entry.type}`)}{entry.share !== null ? ` · ${fmtPct(entry.share)}` : ""}</span>
      {!entry.spot && <span className="muted"> · {t("tactics.position_missing")}</span>}
    </span>
  </li>)}</ul>;
}

function RecipeTitle({ entries }: { entries: RecipeSpot[] }) {
  return <span className="tactics-recipe-name">{entries.length ? entries.map((entry, index) => <span key={entry.id}>
    {index > 0 && <span className="muted"> + </span>}<GrenadeIcon type={entry.type} /> {entry.name}
  </span>) : t("tactics.no_spots")}</span>;
}

function RecipeDetails({ recipe, entries, splitDefinition }: { recipe: Recipe; entries: RecipeSpot[]; splitDefinition: string }) {
  const tempos = (["fast", "mid", "late"] as const).map((value) => ({ value, rounds: recipe.tempo.find((row) => row.value === value)?.rounds ?? 0 }));
  const total = tempos.reduce((n, row) => n + row.rounds, 0);
  return <div className="tactics-recipe-details">
    <dl className="tactics-detail-stats">
      <div><dt>{t("ui.matches_title")}</dt><dd>{fmtInt(recipe.n_matches)}</dd></div>
      <div><dt>{t("tactics.plant_rate")}</dt><dd>{fmtPct(recipe.plant_rate)}</dd></div>
      <div><dt tabIndex={0} title={splitDefinition}>多方向进点率 ⓘ</dt><dd>{fmtPct(recipe.split_rate)}</dd></div>
      <div><dt>{t("tactics.avg_flashes")}</dt><dd>{fmtNum(recipe.avg_flashes)}</dd></div>
    </dl>
    {recipe.wp && recipe.wp.n > 0 && Number.isFinite(recipe.wp.before) && Number.isFinite(recipe.wp.after) ? <p className="recipe-wp">
      胜率变化 <strong>{fmtPct(recipe.wp.before)} → {fmtPct(recipe.wp.after)}</strong>{" "}
      <span className="data-tooltip" tabIndex={0} role="note" aria-label="胜率变化说明">ⓘ<span role="tooltip">T 方模型胜率：进点前 5 秒与进点后 10 秒的均值（{recipe.wp.n} 回合）。能推进到进点的回合本就较顺利，因此估计偏高；用于套路之间的比较，不代表这套道具的绝对或因果效果。</span></span>
    </p> : null}
    <div className="tactics-spot-columns">
      <section><h4>{t("tactics.core")}</h4><SpotList entries={entries.filter((entry) => entry.core)} /></section>
      <section><h4>{t("tactics.optional")}</h4>{entries.some((entry) => !entry.core) ? <SpotList entries={entries.filter((entry) => !entry.core)} /> : <p className="muted">{t("tactics.no_data")}</p>}</section>
    </div>
    <h4>{t("tactics.tempo_title")}</h4>
    {total ? <div className="tactics-tempo-bar" role="img" aria-label={tempos.map((row) => `${t(`tactics.tempo.${row.value}`)} ${fmtPct(row.rounds / total)}`).join(" · ")}>
      {tempos.map((row) => <span key={row.value} data-tempo={row.value} style={{ flexGrow: row.rounds }} title={`${t(`tactics.tempo.${row.value}`)} · ${row.rounds} 回合`} />)}
    </div> : <p className="muted">{t("tactics.no_data")}</p>}
    <ul className="tactics-tempo-labels">{tempos.map((row) => <li key={row.value} data-tempo={row.value}>{t(`tactics.tempo.${row.value}`)} {total ? fmtPct(row.rounds / total) : "—"}</li>)}</ul>
    <details><summary>{t("tactics.teams")}</summary><ul className="tactics-inline-list">{[...recipe.teams].sort((a, b) => b.rounds - a.rounds).map((team) => <li key={team.team}>{team.team} · {t("tactics.round_count", { n: fmtInt(team.rounds) })}</li>)}</ul></details>
    <details><summary>{t("tactics.examples")}</summary>{recipe.examples.length ? <ul className="tactics-inline-list">{recipe.examples.map((example) => <li key={`${example.demo_id}:${example.round_num}:${example.team}`}>
      {example.team} · {t("tactics.example_round", { n: example.round_num })} · <code>{example.demo_id}</code>
    </li>)}</ul> : <p className="muted">{t("tactics.no_data")}</p>}</details>
  </div>;
}

function KeyNumber({ label, value, context, primary = false }: { label: string; value: string; context: string; primary?: boolean }) {
  return <div className={`tactics-key${primary ? " is-primary" : ""}`}><dt>{label}</dt><dd><CountUp text={value} /></dd><p>{context}</p></div>;
}

export default function Tactics() {
  const lang = useLang();
  const { map = "" } = useParams<{ map: string }>();
  const [params, setParams] = useSearchParams();
  const side = params.get("side") === "CT" ? "CT" : "T";
  const site = params.get("site") === "A" ? "A" : params.get("site") === "B" ? "B" : "all";
  const sort = params.get("sort") === "win_rate" ? "win_rate" : "rounds";
  const { data, loading, error } = useData(() => getTactics(map), [map]);
  const { data: lineupData } = useData(() => getLineups(map), [map]);
  const byLineup = useMemo(() => new Map((lineupData ?? []).map((lineup) => [lineup.id, lineup])), [lineupData]);
  const { data: meta } = useData(() => getMeta(map), [map]);
  const [preview, setPreview] = useState<string | null>(null);
  const [collapsedRecipe, setCollapsedRecipe] = useState<string | null>(null);
  const [setupChoice, setSetupChoice] = useState<string | null>(null);
  const [collapsedSetup, setCollapsedSetup] = useState<string | null>(null);
  const spotsById = useMemo(() => new Map((data?.spots ?? []).map((spot) => [spot.spot_id, spot])), [data]);
  const recipes = useMemo(() => (data?.recipes ?? []).filter((recipe) => site === "all" || recipe.site === site)
    .sort((a, b) => (sort === "win_rate" ? b.win_rate - a.win_rate : b.n_rounds - a.n_rounds)
      || b.n_rounds - a.n_rounds || a.id.localeCompare(b.id)), [data, site, sort]);
  const selected = recipes.find((recipe) => recipe.id === params.get("recipe")) ?? recipes[0];
  const shown = recipes.find((recipe) => recipe.id === preview) ?? selected;
  const entries = useMemo(() => shown ? recipeSpots(map, shown, spotsById, lang, byLineup) : [], [shown, map, spotsById, lang, byLineup]);
  const ctSpots = useMemo<RecipeSpot[]>(() => (data?.spots ?? []).filter((spot) => spot.side === "CT" && (site === "all" || spot.lane === site))
    .sort((a, b) => b.n_throws - a.n_throws || a.spot_id.localeCompare(b.spot_id)).slice(0, 6).map((spot, index) => {
      const mostThrown = [...spot.lineups].sort((a, b) => b.n_throws - a.n_throws)[0];
      return { lineup: mostThrown ? byLineup.get(mostThrown.lineup_id) : undefined, id: spot.spot_id, spot, type: spot.type, core: true, number: index + 1, share: null,
        name: spot.name?.[lang] || spot.label,
        to: mostThrown ? `/${encodeURIComponent(map)}/lineups?${new URLSearchParams({ id: mostThrown.lineup_id })}` : null };
    }), [data, map, site, lang, byLineup]);
  const setups = useMemo(() => [...(data?.ct_overview.setups_20s ?? [])].sort((a, b) => b.rounds - a.rounds || a.value.localeCompare(b.value)), [data]);
  const currentSetup = setups.find((setup) => setup.value === setupChoice) ?? setups[0];
  const currentQuery = params.toString();
  const canonical = new URLSearchParams(params);
  canonical.set("site", site); canonical.set("sort", sort); canonical.set("side", side);
  if (data?.map === map && !loading) { if (selected) canonical.set("recipe", selected.id); else canonical.delete("recipe"); }
  const canonicalQuery = canonical.toString();
  useEffect(() => { if (canonicalQuery !== currentQuery) setParams(canonicalQuery, { replace: true }); }, [canonicalQuery, currentQuery, setParams]);
  useEffect(() => { setPreview(null); setCollapsedRecipe(null); setSetupChoice(null); setCollapsedSetup(null); }, [map, site, sort, side]);
  const update = (key: "site" | "sort" | "recipe" | "side", value: string) => setParams((current) => {
    const next = new URLSearchParams(current); next.set(key, value); return next;
  });
  if (loading) return <Loading />;
  if (error || !data) return <ErrorNotice error={error ?? new Error(t("tactics.no_data"))} />;
  const topTarget = [...data.t_overview.target].filter((row) => row.value !== "none").sort((a, b) => b.rounds - a.rounds)[0];
  const topRecipe = [...data.recipes].sort((a, b) => b.n_rounds - a.n_rounds || a.id.localeCompare(b.id))[0];
  const topRecipeName = topRecipe ? recipeSpots(map, topRecipe, spotsById, lang, byLineup).filter((entry) => entry.core).map((entry) => entry.name).join(" + ") : t("tactics.no_data");
  const scale = meta && Number.isFinite(meta.radar.scale) && meta.radar.scale > 0 ? meta.radar.scale : undefined;
  return <PageSurface className="tactics-page" data-side={side}>
    <header className="page-head">
      <div><p className="eyebrow">{map}</p><h1>{meta?.display_name ?? map} · {t("ui.nav_tactics")}</h1><PageContext>{t("site.tactics_context")}</PageContext></div>
      <div className="segmented tactics-sides" role="group" aria-label={t("ui.filter_side")}>
        {(["T", "CT"] as const).map((value) => <button key={value} type="button" className={side === value ? "is-active" : ""} aria-pressed={side === value} onClick={() => update("side", value)}>{t(`tactics.side_${value}`)}</button>)}
      </div>
    </header>
    <dl className="tactics-key-numbers">
      {side === "T" ? <>
        <KeyNumber primary label={t("tactics.top_target")} value={topTarget ? fmtPct(topTarget.share) : "—"} context={topTarget ? t("tactics.target_context", { site: siteLabel(topTarget.value) }) : t("tactics.no_data")} />
        <KeyNumber label={t("tactics.avg_commit")} value={fmtSeconds(data.t_overview.avg_commit_s)} context={t("tactics.commit_context")} />
        <KeyNumber label={t("tactics.signature_win")} value={fmtPct(topRecipe?.win_rate)} context={topRecipeName} />
      </> : <>
        <KeyNumber primary label={t("tactics.default_setup")} value={fmtPct(setups[0]?.share)} context={setups[0]?.value ?? t("tactics.no_data")} />
        <KeyNumber label={t("tactics.setup_win")} value={fmtPct(setups[0]?.win_rate)} context={t("tactics.setup_context")} />
        <KeyNumber label={t("tactics.forward_rate")} value={fmtPct(data.ct_overview.forward_rate)} context={t("tactics.forward_context")} />
        <KeyNumber label={t("tactics.stack_rate")} value={fmtPct(data.ct_overview.stack_rate)} context={t("tactics.stack_context")} />
      </>}
    </dl>
    <div className="tactics-workspace">
      <aside className="tactics-map-panel">
        <Reveal className="motion-radar" key={`${map}:${side}`}><RecipeRadar key={`${map}:${side}`} map={map} scale={scale} spots={side === "T" ? entries : ctSpots} title={side === "T" ? t("tactics.selected_utility") : t("tactics.ct_utility")}
          site={side === "T" ? shown?.site : site === "all" ? undefined : site}
          selectionLabel={side === "T" && shown ? `${siteLabel(shown.site)} · ${entries.filter((entry) => entry.core).map((entry) => entry.name).join(" + ")}` : undefined} /></Reveal>
      </aside>
      <section className="tactics-browser" aria-labelledby="tactics-recipes-title">
        <h2 id="tactics-recipes-title">{t(side === "T" ? "tactics.recipes" : "tactics.setups")}</h2>
        <div className="tactics-controls">
          <div className="segmented" role="group" aria-label={t("tactics.site")}>
            {(["all", "A", "B"] as const).map((value) => <button key={value} type="button" className={site === value ? "is-active" : ""} aria-pressed={site === value} onClick={() => update("site", value)}>{value === "all" ? t("ui.filter_all") : siteLabel(value)}</button>)}
          </div>
          {side === "T" && <label><span className="visually-hidden">{t("tactics.sort")}</span><select value={sort} onChange={(event) => update("sort", event.target.value)}><option value="rounds">{t("tactics.sort_rounds")}</option><option value="win_rate">{t("tactics.sort_win_rate")}</option></select></label>}
        </div>
        {side === "T" ? <div className="tactics-recipes" onMouseLeave={() => setPreview(null)} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setPreview(null); }}>
          <p className="muted tactics-help">{t("tactics.recipe_count", { n: fmtInt(recipes.length) })} · {t("tactics.preview_hint")}</p>
          {recipes.length ? recipes.map((recipe, index) => {
            const rowEntries = recipeSpots(map, recipe, spotsById, lang, byLineup);
            const active = recipe.id === selected?.id;
            const open = active && collapsedRecipe !== recipe.id;
            return <article className={`tactics-recipe motion-reveal${active ? " is-selected" : ""}`} data-motion-tilt={active || undefined} style={{ "--stagger": `${Math.min(index * 55, 385)}ms` } as CSSProperties} key={recipe.id} onMouseEnter={() => setPreview(recipe.id)} onFocus={() => setPreview(recipe.id)}>
              <h3><button type="button" className="tactics-recipe-toggle" aria-expanded={open} aria-controls={`details-${recipe.id}`} onClick={() => {
                setCollapsedRecipe(open ? recipe.id : null); setPreview(null); update("recipe", recipe.id);
              }}><span className="tactics-recipe-heading"><span className="tactics-chevron" aria-hidden="true">{open ? "▾" : "▸"}</span><span className="tactics-site">{siteLabel(recipe.site)}</span><RecipeTitle entries={rowEntries.filter((entry) => entry.core)} /></span>
                <span className="tactics-row-meta">{t("tactics.recipe_meta", { rounds: fmtInt(recipe.n_rounds), win: fmtPct(recipe.win_rate), time: fmtSeconds(recipe.median_commit_s) })}</span>
              </button></h3>
              <div id={`details-${recipe.id}`} hidden={!open}>{open && <RecipeDetails recipe={recipe} entries={rowEntries} splitDefinition={`进点位置相距至少 400 游戏单位，或相对包点中心的方位角相差至少 50°。不限定中路。导出定义：${String(data.definitions.split ?? "未提供")}`} />}</div>
            </article>;
          }) : <p className="muted">{t("tactics.no_recipes")}</p>}
        </div> : <>
          <p className="muted tactics-help">{t("tactics.ct_utility_context")}</p>
          {setups.map((setup, index) => {
            const active = setup.value === currentSetup?.value;
            const open = active && collapsedSetup !== setup.value;
            return <article className={`tactics-recipe motion-reveal${active ? " is-selected" : ""}`} data-motion-tilt={active || undefined} style={{ "--stagger": `${Math.min(index * 55, 385)}ms` } as CSSProperties} key={setup.value}>
              <h3><button type="button" className="tactics-recipe-toggle" aria-expanded={open} aria-controls={`setup-${index}`} onClick={() => { setSetupChoice(setup.value); setCollapsedSetup(open ? setup.value : null); }}>
                <span className="tactics-recipe-heading"><span aria-hidden="true">{open ? "▾" : "▸"}</span>{setup.value}</span>
                <span className="tactics-row-meta">{t("tactics.setup_meta", { rounds: fmtInt(setup.rounds), share: fmtPct(setup.share), win: fmtPct(setup.win_rate) })}</span>
              </button></h3>
              <div id={`setup-${index}`} hidden={!open}>{open && <p className="muted tactics-help">{t("ui.setup_shape_help")}</p>}</div>
            </article>;
          })}
          {!setups.length && <p className="muted">{t("tactics.no_data")}</p>}
        </>}
      </section>
    </div>
    <details className="tactics-more" key={`${map}:${side}`}><summary>{t("tactics.more_data")}</summary>
      {side === "T" ? <TOverview data={data.t_overview} /> : <CTOverview data={data.ct_overview} />}
    </details>
  </PageSurface>;
}
