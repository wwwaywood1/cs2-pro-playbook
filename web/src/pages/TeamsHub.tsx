import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";
import HeatmapCanvas, { HeatmapMarkers, type HeatmapMarker } from "../components/HeatmapCanvas";
import RecipeRadar, { type RecipeSpot } from "../components/RecipeRadar";
import { MapLinkHint, useMapLink } from "../mapLink";
import { heatmapMarkers, linkedLevel } from "../mapPlaces";
import "../tactics.css";
import GrenadeIcon, { GrenadeGlyph, GRENADE_COLORS } from "../components/GrenadeIcon";
import TeamDetails from "../components/TeamDetails";
import TeamSummaryLinks, { signatureRecipe } from "../components/TeamSummaryLinks";
import LowSampleBanner from "../components/LowSampleBanner";
import Stat from "../components/Stat";
import PlayerWpa from "../components/PlayerWpa";
import { Loading } from "../components/Status";
import { getAssetSlots, getHeatmapBaseline, getHeatmapTeams, getMeta, getPlayerQuotes, getPlayers, getTactics, getTeam, getTeamHeatmap, useData } from "../data";
import { fmtInt, fmtPct } from "../format";
import { blur, combine, denseLayers, HEAT_PHASES, playerRgba, toDataUrl, VIEW_WEIGHTS, type Dense, type HeatView } from "../heatmap";
import { calloutLabel, t, useLang } from "../i18n";
import type { AssetSlots, HeatLayer, HeatPhase, HeatmapBaseline, HeatmapTeamIndexEntry, PlayerProfile, PlayerQuotes, PlayerSideSummary, RosterEntry, Side, TeamHeatmap, TeamProfile, TacticsFile, UtilitySpot } from "../types";
import { rememberPortrait, usePlayerEntrance } from "./teamsHubMotion";
import CountUp, { type NumberFormat } from "../components/CountUp";
import { NumberEntrance, ReducedMotion, useMotionPointer, useMotionRoute, useReducedMotion } from "../motion";
import { teamTheme } from "../theme";
import "../heatmap.css";
import "../teams-hub.css";

type HubSide = Side;
type TeamEntry = HeatmapTeamIndexEntry;
type Selection = { team: string; map: string; player: string; side: HubSide };
type Change = (selection: Partial<Selection>) => void;
const SIDES: HubSide[] = ["T", "CT"];
const VIEWS: HeatView[] = ["presence", "holding", "fights", "utility"];
const EMPTY_ASSETS: AssetSlots = { teams: [], players: [] };
const Assets = createContext<AssetSlots>(EMPTY_ASSETS);
const SIDE_COLORS = {
  T: { key: "orange", light: "#ffdaa9", deep: "#e8893c" },
  CT: { key: "blue", light: "#c7e7ff", deep: "#519ee9" },
};
type Route = Pick<Selection, "team" | "map" | "player">;
function routeKey(route: Route) { return JSON.stringify([route.team, route.map, route.player]); }
function depth(route: Route) { return route.player ? 3 : route.map ? 2 : route.team ? 1 : 0; }
// HashRouter defers React renders; history already holds the latest destination.
// Read it for actions so rapid Escape presses cannot reuse an outgoing route.
function currentHubParams() { return new URLSearchParams(window.location.hash.split("?")[1] ?? ""); }

function useSlideRoute(route: Route, reduced: boolean) {
  return useMotionRoute(route, routeKey(route), reduced, hubDirection);
}
function hubDirection(next: Route, previous: Route) { return depth(next) < depth(previous) ? -1 : 1; }

function AnimatedStat({ label, value, format, sub }: { label: string; value: number | null | undefined; format?: NumberFormat; sub?: string }) {
  return <Stat label={label} value={<CountUp value={value} format={format} />} sub={sub} />;
}

function Verse({ text }: { text: string }) {
  // Owner copy is authoritative. Split a couplet at punctuation; balance a single line.
  const phrases = text.trim().split(/[，,。！？；;\n]+/u).map((part) => part.trim()).filter(Boolean);
  const glyphs = Array.from(phrases[0] ?? "");
  const columns = phrases.length > 1 ? phrases : [glyphs.slice(0, Math.ceil(glyphs.length / 2)).join(""), glyphs.slice(Math.ceil(glyphs.length / 2)).join("")].filter(Boolean);
  let offset = 0;
  const total = columns.reduce((sum, column) => sum + Array.from(column).length, 0);
  return <p className="hub-verse-line" lang="zh"><span className="sr-only">{text}</span>
    <span aria-hidden="true" className="hub-verse-columns">{columns.map((column, columnIndex) => <span className="hub-verse-column" key={columnIndex}>{Array.from(column).map((character) => {
      const index = offset++;
      return <span className="hub-verse-character" key={index} style={{ "--character-delay": `${index * Math.min(38, 500 / Math.max(1, total - 1))}ms` } as CSSProperties}>{character}</span>;
    })}</span>)}</span>
  </p>;
}

/** Retain the previous heat textures for a real crossfade, including an empty side.
 * The radar and utility semantics stay stable; rapid switches replace the old fade. */
function HeatLayers({ overlays }: { overlays: { key: string; url: string }[] }) {
  const reduced = useContext(ReducedMotion);
  const latest = useRef(overlays);
  const [previous, setPrevious] = useState<typeof overlays>([]);
  useLayoutEffect(() => {
    const old = latest.current;
    latest.current = overlays;
    if (reduced) { setPrevious([]); return; }
    if (old === overlays) return;
    setPrevious(old);
    const timer = window.setTimeout(() => setPrevious([]), 420);
    return () => window.clearTimeout(timer);
  }, [overlays, reduced]);
  return <svg className="hub-heat-layers" viewBox="0 0 1024 1024" aria-hidden="true">
    {previous.length ? <g className="hub-layer-out" key={`out-${previous.map((layer) => layer.key).join()}`}>{previous.map((layer) => <image key={layer.key} href={layer.url} width="1024" height="1024" preserveAspectRatio="none" />)}</g> : null}
    <g className="hub-layer-in" key={overlays.map((layer) => layer.key).join()}>{overlays.map((layer) => <image key={layer.key} href={layer.url} width="1024" height="1024" preserveAspectRatio="none" />)}</g>
  </svg>;
}


function Asset({ path, name, badge = false }: { path: string; name: string; badge?: boolean }) {
  const [failed, setFailed] = useState(false);
  const assets = useContext(Assets);
  const stem = path.split("/").pop()?.replace(/\.png$/, "") ?? "";
  const supplied = (badge ? assets.teams : assets.players).includes(stem);
  return <span className={`hub-asset ${badge ? "hub-badge" : "hub-portrait"}`}>
    {!failed && supplied ? <img src={`${import.meta.env.BASE_URL}${path}`} alt="" width={badge ? 80 : 1000} height={badge ? 80 : 666} onError={() => setFailed(true)} /> : badge ?
      <span aria-hidden="true">{name.split(/\s+/).map((part) => part[0]).join("").slice(0, 3).toUpperCase()}</span> :
      <svg viewBox="0 0 240 280" aria-hidden="true"><circle cx="120" cy="88" r="42" /><path d="M32 260v-28a88 88 0 0 1 176 0v28Z" /></svg>}
  </span>;
}

function Failure() {
  return <p className="notice notice-error" role="alert">{t("hub.load_error")}</p>;
}

function Heading({ children }: { children: string }) {
  return <h2 id="hub-heading" tabIndex={-1}>{children}</h2>;
}

function Results({ team }: { team: TeamEntry }) {
  const results = team.maps.flatMap((map) => (map.results ?? []).map((match) => ({ ...match, map: map.display_name })));
  results.sort((a, b) => (b.hltv_match_id ?? 0) - (a.hltv_match_id ?? 0) || b.demo_id.localeCompare(a.demo_id));
  return <section className="hub-results" aria-label={t("hub.results")}>
    <h3>{t("hub.results")}</h3>
    <p className="muted">{t("hub.results_order")}</p>
    {results.length ? <ul>{results.slice(0, 5).map((result) => <li key={result.demo_id}>
      <span className={`hub-result ${result.score_for > result.score_against ? "is-win" : ""}`}>
        {t(result.score_for === result.score_against ? "hub.draw" : result.score_for > result.score_against ? "hub.win" : "hub.loss")}
      </span>
      <span>{result.opponent ?? t("hub.unknown_opponent")}<small>{[result.map, result.event_name || result.event, result.date].filter(Boolean).join(" · ")}</small></span>
      <strong>{result.score_for} : {result.score_against}</strong>
    </li>)}</ul> : <p className="muted">{t("heatmap.no_data")}</p>}
  </section>;
}

function TeamPanel({ team, change }: { team: TeamEntry; change: Change }) {
  const ranked = [...team.maps].filter((map) => map.map_win_rate != null).sort((a, b) => (b.map_win_rate ?? 0) - (a.map_win_rate ?? 0) || a.map.localeCompare(b.map));
  const best = ranked[0]?.map;
  const worst = ranked.length > 1 ? ranked[ranked.length - 1]?.map : undefined;
  return <section className="hub-panel hub-team-panel" key={team.slug} aria-labelledby="hub-heading">
    <header className="hub-team-head"><Asset path={`logos/teams/${team.slug}.png`} name={team.team} badge />
      <div><p className="hub-eyebrow">{t("hub.step_team")}</p><Heading>{team.team}</Heading>
        <p className="muted">{t("hub.sample", { matches: team.n_matches, maps: team.maps.length })}</p></div>
    </header>
    <div className="hub-team-layout">
      <section><h3>{t("hub.choose_map")}</h3><p className="muted">{t("hub.map_rate_help")}</p>
        <div className="hub-map-grid">{team.maps.map((map, index) => <button type="button" className="hub-map-card hub-primary" data-rate={map.map_win_rate == null ? "unknown" : map.map_win_rate >= .65 ? "strong" : map.map_win_rate < .48 ? "weak" : "neutral"} style={{ "--stagger": `${index * 70}ms`, "--hub-progress": 100 - Math.max(0, Math.min(1, map.map_win_rate ?? 0)) * 100 } as CSSProperties} id={`hub-map-${map.map}`} key={map.map} onClick={() => change({ map: map.map, player: "", side: "T" })}>
          <img className="hub-map-preview" src={`${import.meta.env.BASE_URL}radars/${map.map}.png`} alt="" aria-hidden="true" loading="lazy" onError={(event) => { event.currentTarget.hidden = true; }} />
          <span className="hub-map-name">{map.display_name}</span>
          {map.map === best ? <span className="hub-map-badge is-best">{t("round2.best_map")}</span> : map.map === worst ? <span className="hub-map-badge is-weak">{t("round2.weak_map")}</span> : null}<span className="hub-rate">
            <svg viewBox="0 0 100 100" aria-hidden="true"><circle className="hub-arc-track" cx="50" cy="50" r="44" /><circle className="hub-arc" cx="50" cy="50" r="44" pathLength="100" /></svg>
            <strong><CountUp value={map.map_win_rate} format="percent" /></strong>
          </span>
          <span>{t("hub.map_win_rate")}</span><small>{t("hub.matches", { n: map.n_matches })}{map.low_sample ? ` · ${t("heatmap.low_sample")}` : ""}</small>
        </button>)}</div>
      </section><details className="hub-details hub-team-results"><summary>{t("hub.results")}</summary><Results team={team} /></details>
    </div>
  </section>;
}

function MapOverview({ profile, tactics }: { profile: TeamProfile; tactics: TacticsFile }) {
  const lang = useLang();
  const { T, CT } = profile.sides;
  const rounds = T.rounds + CT.rounds;
  const recipes = (profile.tactics?.T.recipes ?? []).slice(0, 3);
  const setup = profile.tactics?.CT.setups_20s[0];
  return <>
    <LowSampleBanner n_matches={profile.n_matches} low_sample={profile.low_sample} />
    <div className="hub-kpis">
      <AnimatedStat label={t("ui.round_win_rate")} value={rounds ? (T.won + CT.won) / rounds : null} format="percent" sub={t("heatmap.rounds", { n: fmtInt(rounds) })} />
      <div className="hub-side-stat" data-side="T"><AnimatedStat label={t("hub.t_win")} value={T.win_rate} format="percent" sub={t("heatmap.rounds", { n: fmtInt(T.rounds) })} /></div>
      <div className="hub-side-stat" data-side="CT"><AnimatedStat label={t("hub.ct_win")} value={CT.win_rate} format="percent" sub={t("heatmap.rounds", { n: fmtInt(CT.rounds) })} /></div>
      <AnimatedStat label={t("tactics.avg_commit")} value={profile.tactics?.T.avg_commit_s} format="seconds" />
    </div>
    {profile.summary?.[lang] || profile.insights?.length || profile.tactics?.T.recipes.length ? <p className="hub-summary"><TeamSummaryLinks profile={profile} tactics={tactics} /></p> : null}
    <details className="hub-details"><summary>{t("hub.team_details")}</summary>
      <div className="hub-team-layout"><section><h3>{t("tactics.tempo_title")}</h3>
        <ul className="hub-data-list">{(profile.tactics?.T.tempo ?? []).map((row) => <li key={row.value}><span>{t(`tactics.tempo.${row.value}`)}</span><strong>{fmtPct(row.share)}</strong></li>)}</ul>
        <h3>{t("tactics.default_setup")}</h3><p>{setup ? `${setup.value} · ${fmtPct(setup.share)}` : t("heatmap.no_data")}</p>
        <p className="muted">{t("ui.setup_shape_help")}</p>
      </section><section><h3>{t("hub.top_recipes")}</h3>
        {recipes.length ? <ul className="hub-data-list">{recipes.map((rank) => {
          const recipe = tactics.recipes.find((item) => item.id === rank.value);
          return <li key={rank.value}><Link to={`/${profile.map}/tactics?recipe=${encodeURIComponent(rank.value)}`}>{recipe ? `${t(`region.${recipe.site}_SITE`)} · ` : ""}{recipe ? recipe.core.map((spot) => spot.name?.[lang] || spot.label).join(" + ") : rank.value}<small>{t("tactics.round_count", { n: rank.rounds })} · {t("ui.round_win_rate")} {fmtPct(rank.win_rate)}</small></Link></li>;
        })}</ul> : <p className="muted">{t("tactics.no_recipes")}</p>}
      </section></div>
    </details>
  </>;
}

function PlayerCards({ roster, change }: { roster: RosterEntry[]; change: Change }) {
  const reduced = useContext(ReducedMotion);
  const ordered = [...roster].sort((a, b) => (b.rounds.T + b.rounds.CT) - (a.rounds.T + a.rounds.CT) || a.color - b.color);
  function cards(players: RosterEntry[]) {
    return <div className="hub-player-cards" data-hub-parallax>{players.map((player, index) => <button type="button" className="hub-player-card hub-primary" style={{ "--stagger": `${index * 75}ms` } as CSSProperties} key={player.steamid} id={`hub-player-${player.steamid}`} onClick={(event) => { rememberPortrait(event.currentTarget, reduced); change({ player: player.steamid, side: "T" }); }}>
      <span className="hub-roster-light" aria-hidden="true" /><span className="hub-card-portrait-depth"><Asset path={`players/${player.steamid}.png`} name={player.name} /></span><strong>{player.name}</strong>
      <small>{t("heatmap.rounds", { n: fmtInt(player.rounds.T + player.rounds.CT) })}</small>
    </button>)}</div>;
  }
  return <section className="hub-roster"><h3>{t("hub.choose_player")}</h3><p className="muted">{t("hub.roster_help")}</p>
    {cards(ordered.slice(0, 5))}
    {ordered.length > 5 ? <details className="hub-details"><summary>{t("hub.other_players", { n: ordered.length - 5 })}</summary>{cards(ordered.slice(5))}</details> : null}
  </section>;
}

/** Bound the square to its column and remaining viewport, just like the tactics radar. */
function HubRadar({ map, level, overlays, spots = [], markers = [] }: {
  map: string; level: number; overlays: { key: string; url: string }[]; spots?: UtilitySpot[]; markers?: HeatmapMarker[];
}) {
  const { bind } = useMapLink();
  const host = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const meta = useData(() => getMeta(map), [map]);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const page = element.closest<HTMLElement>(".hub-page");
    const topbar = document.querySelector<HTMLElement>(".topbar");
    const measure = () => {
      // offsetTop is unaffected by the panel's entrance transform or page scrolling.
      let top = 0;
      let node: HTMLElement | null = element;
      while (node) { top += node.offsetTop; node = node.offsetParent as HTMLElement | null; }
      element.style.setProperty("--hub-radar-top", `${top}px`);
      setWidth(element.getBoundingClientRect().width || 640);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (page) observer.observe(page);
    if (topbar) observer.observe(topbar);
    window.addEventListener("resize", measure);
    measure();
    return () => { observer.disconnect(); window.removeEventListener("resize", measure); };
  }, []);
  const unit = 1024 / width;
  const scale = meta.data?.radar.scale;
  return <div className="hub-radar" ref={host}>
    <HeatmapCanvas map={map} level={level} overlays={[]} />
    {overlays.length ? <HeatLayers overlays={overlays} /> : null}
    {markers.length ? <svg className="hub-place-overlay" viewBox="0 0 1024 1024" role="group" aria-label={t("heatmap.zones")}><HeatmapMarkers markers={markers} /></svg> : null}
    {spots.length ? <svg className="hub-utility-overlay" viewBox="0 0 1024 1024" role="group" aria-label={t("heatmap.util_spots")}>
      {spots.map((spot) => {
        if (spot.radar_x === null || spot.radar_y === null) return null;
        const kind = spot.type === "flashbang" ? "flash" : spot.type;
        const radius = scale && scale > 0 && (kind === "smoke" || kind === "molotov") ? (kind === "smoke" ? 144 : 120) / scale : 16 * unit;
        const id = [...spot.lineups].sort((a, b) => b.n - a.n)[0]?.lineup_id;
        const label = `${t(`grenade.${spot.type}`)} · ${calloutLabel(map, spot.place)} · ${fmtInt(spot.n)}`;
        const marker = <g transform={`translate(${spot.radar_x} ${spot.radar_y})`}>
          <title>{`${t(`grenade.${spot.type}`)} · ${calloutLabel(map, spot.place)} · ${fmtInt(spot.n)}`}</title>
          <circle className="map-link-ring" r={22 * unit} />
          <circle r={radius} fill={GRENADE_COLORS[kind]} fillOpacity={0.16} />
          <g transform={`scale(${unit})`}><g transform="translate(-12 -12) scale(0.75)"><GrenadeGlyph type={spot.type} /></g></g>
        </g>;
        return id ? <a key={spot.spot_id} {...bind(`spot:${spot.spot_id}`)} href={`#/${map}/lineups?id=${encodeURIComponent(id)}`} aria-label={`${label} · 查看道具`}>{marker}</a> : <g key={spot.spot_id} {...bind(`spot:${spot.spot_id}`)} tabIndex={0} role="img" aria-label={label}>{marker}</g>;
      })}
    </svg> : null}
  </div>;
}

function MapControls({ view, level, levels, setView, setLevel, phase, setPhase }: {
  view: HeatView; level: number; levels: number; setView: (view: HeatView) => void; setLevel: (level: number) => void;
  phase: HeatPhase; setPhase: (phase: HeatPhase) => void;
}) {
  return <div className="hub-map-controls"><fieldset className="hub-segments"><legend>{t("hub.layer")}</legend><div>{VIEWS.map((v) => <button type="button" key={v} aria-pressed={view === v} onClick={() => setView(v)}>{t(`heatmap.view.${v}`)}</button>)}</div></fieldset>
    <fieldset className="hub-segments hub-time-slices"><legend>{t("heatmap.phases")}</legend><div>{HEAT_PHASES.map((value) => <button type="button" key={value} aria-pressed={phase === value} onClick={() => setPhase(value)}>{t(`round2.time_${value}`)}</button>)}</div><p className="muted">{t("round2.time_help")}</p></fieldset>
    {levels > 1 ? <label>{t("tactics.floor")}<select value={level} onChange={(event) => setLevel(Number(event.target.value))}><option value={0}>{t("heatmap.level.upper")}</option><option value={1}>{t("heatmap.level.lower")}</option></select></label> : null}
  </div>;
}

function TeamMapView({ profile, tactics, heatmap, baseline, change }: {
  profile: TeamProfile; tactics: TacticsFile; heatmap: TeamHeatmap; baseline: HeatmapBaseline; change: Change;
}) {
  const lang = useLang();
  const { activeId } = useMapLink();
  const meta = useData(() => getMeta(profile.map), [profile.map]);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const signature = signatureRecipe(profile, tactics);
  const signatureSpots: RecipeSpot[] = signature ? [...signature.core, ...signature.options].map((ref, index) => ({
    id: ref.spot_id, type: ref.type, spot: tactics.spots.find((spot) => spot.spot_id === ref.spot_id), core: index < signature.core.length,
    number: ref.order ?? index + 1, name: ref.name?.[lang] || ref.label, share: ref.share,
    to: ref.lineups[0] ? `/${profile.map}/lineups?${new URLSearchParams({ id: ref.lineups[0].lineup_id })}` : null,
  })) : [];
  useEffect(() => {
    if (signature && [...signature.core, ...signature.options].some((spot) => activeId === `spot:${spot.spot_id}`)) setSummaryOpen(true);
  }, [activeId, signature]);
  const [teamSide, setTeamSide] = useState<Side>("T");
  const [view, setView] = useState<HeatView>("presence");
  const [phase, setPhase] = useState<HeatPhase>("early");
  const [level, setLevel] = useState(0);
  const overlays = useMemo(() => {
    const shape = { grid: baseline.grid, levels: baseline.levels };
    const layers: Partial<Record<HeatLayer, Dense>> = {};
    const total = heatmap.rounds[teamSide];
    for (const side of [teamSide]) {
      const source = denseLayers(heatmap.team_grid, side, [phase], shape);
      for (const key of Object.keys(source) as HeatLayer[]) {
        const values = source[key];
        if (!values) continue;
        const target = layers[key] ?? (layers[key] = new Float32Array(values.length));
        for (let i = 0; i < values.length; i++) target[i] += values[i] * (total ? heatmap.rounds[side] / total : 0);
      }
    }
    const dense = blur(combine(layers, VIEW_WEIGHTS[view], shape), shape, 1.1);
    if (!dense.subarray(level * shape.grid * shape.grid, (level + 1) * shape.grid * shape.grid).some((v) => v > 0)) return [];
    return [{ key: `team-${teamSide}-${phase}-${view}-${level}`, url: toDataUrl(playerRgba(dense, shape, level, SIDE_COLORS[teamSide]), shape.grid) }];
  }, [heatmap, baseline, view, level, teamSide, phase]);
  return <div className="hub-team-map-view">
    <img className="hub-map-backdrop" src={`${import.meta.env.BASE_URL}radars/${heatmap.map}.png`} alt="" aria-hidden="true" />
    <div className="hub-map-context"><MapOverview profile={profile} tactics={tactics} /></div>
    <PlayerCards roster={heatmap.roster} change={change} />
    <TeamDetails team={profile} />
    {signature ? <details className="hub-details hub-summary-radar" open={summaryOpen} onToggle={(event) => setSummaryOpen(event.currentTarget.open)}>
      <summary>{t("tactics.selected_utility")}</summary>
      <RecipeRadar map={profile.map} spots={signatureSpots} scale={meta.data?.radar.scale} title={t("tactics.selected_utility")} site={signature.site} routes={signature.routes ?? []} routeKey={signature.id} />
    </details> : null}
    <details className="hub-details hub-team-radar"><summary>{t("ui.nav_heatmaps")}</summary><section aria-label={t("ui.nav_heatmaps")}>
      <div className="segmented">{SIDES.map((value) => <button type="button" key={value} data-side={value} aria-pressed={teamSide === value} onClick={() => setTeamSide(value)}>{value}</button>)}</div><MapControls view={view} level={level} levels={baseline.levels} setView={setView} setLevel={setLevel} phase={phase} setPhase={setPhase} />
      <HubRadar map={heatmap.map} level={level} overlays={overlays} />
      {!overlays.length ? <p className="muted" role="status">{t("hub.no_layer")}</p> : null}
    </section></details>
  </div>;
}

function summaryRate(heatmap: TeamHeatmap, steamid: string, side: HubSide, metric: (summary: PlayerSideSummary) => number | null): number | null {
  const sides: Side[] = [side];
  const known = sides.flatMap((s) => {
    const summary = heatmap.summary[steamid]?.[s];
    return summary && summary.rounds > 0 && metric(summary) !== null ? [summary] : [];
  });
  const rounds = known.reduce((n, summary) => n + summary.rounds, 0);
  return rounds ? known.reduce((n, summary) => n + (metric(summary) ?? 0) * summary.rounds, 0) / rounds : null;
}
function utilityRate(summary: PlayerSideSummary): number | null {
  const values = Object.values(summary.utility.per_round);
  return values.some((value) => value !== null) ? values.reduce<number>((n, value) => n + (value ?? 0), 0) : null;
}

function PlayerView({ player, profile, heatmap, baseline, side, quote, change, displayName }: {
  player: RosterEntry; profile?: PlayerProfile; heatmap: TeamHeatmap; baseline: HeatmapBaseline;
  side: HubSide; quote?: PlayerQuotes[string]; change: Change; displayName: string;
}) {
  const { activeId, bind } = useMapLink();
  const reduced = useContext(ReducedMotion);
  const details = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    if ((activeId?.startsWith("place:") || activeId?.startsWith("spot:")) && details.current) details.current.open = true;
  }, [activeId]);
  const host = useRef<HTMLDivElement>(null);
  const { entrance, skip } = usePlayerEntrance(player.steamid, reduced, host);
  const [view, setView] = useState<HeatView>("presence");
  const [phase, setPhase] = useState<HeatPhase>("early");
  const [chosenLevel, setLevel] = useState(0);
  const selectedSides: Side[] = [side];
  const summaries = selectedSides.flatMap((s) => {
    const summary = heatmap.summary[player.steamid]?.[s];
    return summary ? [summary] : [];
  });
  const places = heatmapMarkers(heatmap.map, baseline, summaries, SIDE_COLORS[side].light);
  const allMarkers = [...places, ...summaries.flatMap((summary) => summary.utility.spots.filter((spot) => spot.radar_x !== null && spot.radar_y !== null).map((spot) => ({
    id: `spot:${spot.spot_id}`, level: spot.level, x: spot.radar_x!, y: spot.radar_y!, color: SIDE_COLORS[side].light, title: calloutLabel(heatmap.map, spot.place),
  })))];
  const level = linkedLevel(activeId, allMarkers, chosenLevel);
  const rounds = summaries.reduce((sum, s) => sum + s.rounds, 0);
  const rate = (metric: (summary: PlayerSideSummary) => number | null) => summaryRate(heatmap, player.steamid, side, metric);
  function comparison(metric: (summary: PlayerSideSummary) => number | null, lower = false): string {
    const value = rate(metric);
    const cohort = heatmap.roster.map((entry) => summaryRate(heatmap, entry.steamid, side, metric)).filter((n): n is number => n !== null);
    if (value === null || cohort.length < 2) return "队内同图同侧：无可比样本";
    const rank = 1 + cohort.filter((n) => lower ? n < value : n > value).length;
    return `队内第 ${rank} / ${cohort.length} · 同图${side + "方"}长枪局${lower ? " · 越低越前" : ""}`;
  }
  const overlays = useMemo(() => {
    const grid = heatmap.players[player.steamid];
    if (!grid) return [];
    const shape = { grid: baseline.grid, levels: baseline.levels };
    const layers: Partial<Record<HeatLayer, Dense>> = {};
    const sides: Side[] = [side];
    const total = sides.reduce((n, s) => n + player.rounds[s], 0);
    for (const s of sides) {
      const source = denseLayers(grid, s, [phase], shape);
      for (const key of Object.keys(source) as HeatLayer[]) {
        const values = source[key];
        if (!values) continue;
        const target = layers[key] ?? (layers[key] = new Float32Array(values.length));
        for (let i = 0; i < values.length; i++) target[i] += values[i] * (total ? player.rounds[s] / total : 0);
      }
    }
    const dense = blur(combine(layers, VIEW_WEIGHTS[view], shape), shape, 1.1);
    const floor = dense.subarray(level * shape.grid * shape.grid, (level + 1) * shape.grid * shape.grid);
    if (!floor.some((v) => v > 0)) return [];
    return [{ key: `${player.steamid}-${side}-${phase}-${view}-${level}`, url: toDataUrl(playerRgba(dense, shape, level, SIDE_COLORS[side]), shape.grid) }];
  }, [heatmap, player, baseline, side, view, level, phase]);
  const spots = new Map<string, UtilitySpot>();
  for (const summary of summaries) for (const spot of summary.utility.spots) {
    const prev = spots.get(spot.spot_id);
    spots.set(spot.spot_id, prev ? { ...prev, n: prev.n + spot.n } : spot);
  }
  const landingSpots = [...spots.values()].filter((spot) => spot.level === level).sort((a, b) => b.n - a.n);
  return <NumberEntrance.Provider value={entrance === "settled" || reduced ? "static" : entrance === "full" ? 1670 : 0}><div className="hub-player-view" ref={host} data-entrance={entrance} data-side={side} data-phase={phase} data-hub-parallax>
    {entrance !== "settled" && !reduced ? <button type="button" className="hub-intro-skip" onClick={skip}>{t("round2.skip_intro")}</button> : null}
    <aside className="hub-player-bio" aria-label={player.name}>
      <div className="hub-stage-light" aria-hidden="true" /><div className="hub-depth-grid" aria-hidden="true" />
      <span className="hub-outline-name" aria-hidden="true">{player.name}</span>
      <div className="hub-portrait-motion"><Asset path={`players/${player.steamid}.png`} name={player.name} /></div>
      <div className="hub-foreground-dust" aria-hidden="true" />
      {quote && (quote.zh.trim() || quote.en.trim()) ? <blockquote className="hub-verse"><p className="hub-eyebrow">{t("hub.verse")}</p>
        {quote.zh.trim() ? <Verse text={quote.zh} /> : null}
        {quote.en.trim() ? <p className="hub-verse-translation" lang="en">{quote.en}</p> : null}
      </blockquote> : null}
      <div className="hub-player-identity"><h3>{player.name}</h3>
        <p className="hub-player-role">{profile?.role_hints[0] ? t(`role.${profile.role_hints[0].role}`) : t("hub.player")} · {displayName}</p></div>
      <details className="hub-details hub-player-roles"><summary>{t("hub.role_hints")}</summary>
        <p className="muted">{t("hub.roles_scope")}</p>
        {profile?.role_hints.length ? <ul>{profile.role_hints.map((hint) => <li key={hint.role}>{t(`role.${hint.role}`)}<p className="muted">{t(`role_desc.${hint.role}`)}</p></li>)}</ul> : <p className="muted">{t("heatmap.no_data")}</p>}
      </details>
    </aside>
    <section className="hub-player-analysis" aria-label={t("hub.player_analysis")}>
      <header className="hub-analysis-head"><div className="hub-player-title"><Heading>{`${player.name} · ${displayName}`}</Heading><small className="hub-sample-inline">{t("hub.sample_rounds")} · <CountUp value={rounds} format="integer" /></small></div>
      <fieldset className="hub-segments hub-side-switch"><legend className="sr-only">{t("heatmap.side")}</legend>
        <div style={{ "--side-index": SIDES.indexOf(side) } as CSSProperties}><span className="hub-side-indicator" aria-hidden="true" />{SIDES.map((s) => <button type="button" key={s} aria-pressed={side === s} onClick={() => change({ side: s })}>{t(`side.${s}`)}</button>)}</div>
      </fieldset></header>
      <div className="hub-analysis-toolbar"><div className="hub-kpis">
        <AnimatedStat label={t("heatmap.kpr")} value={rate((s) => s.fights.kills_pr)} sub={comparison((s) => s.fights.kills_pr)} />
        <AnimatedStat label={t("heatmap.dpr")} value={rate((s) => s.fights.deaths_pr)} sub={comparison((s) => s.fights.deaths_pr, true)} />
        <AnimatedStat label={t("hub.utility_pr")} value={rate(utilityRate)} sub={comparison(utilityRate)} />
      </div></div>
      {selectedSides.some((s) => player.low_sample[s]) ? <p className="hub-low">{t("hub.player_low", { n: baseline.min_reliable_rounds })}</p> : null}
      {!rounds || !overlays.length ? <p className="hub-low" role="status">{t("hub.no_layer")}</p> : null}
      <div className="hub-map-stage"><figure className="hub-map-figure"><HubRadar map={heatmap.map} level={level} overlays={overlays} markers={places.filter((place) => place.level === level)} spots={landingSpots} />
        <figcaption>
          <div className="hub-mini-legend" aria-label={t(`heatmap.view.${view}`)}><span>{t(`side.${side}`)}</span><span className="hub-heat-scale" style={{ background: `linear-gradient(90deg, transparent, ${SIDE_COLORS[side].light}, ${SIDE_COLORS[side].deep})` }} /><span>{t(`heatmap.view.${view}`)} · {t(`round2.time_${phase}`)}</span></div>
          <details className="hub-map-notes"><summary>{t(`heatmap.view.${view}`)} · {t(`side.${side}`)}</summary><p>{t("round2.time_help")}</p>
        </details></figcaption>
      </figure>
      <aside className="hub-map-side"><PlayerWpa player={profile} side={side} />
        <MapControls view={view} level={level} levels={baseline.levels} setView={setView} setLevel={setLevel} phase={phase} setPhase={setPhase} /></aside></div>
      <details ref={details} className="hub-details"><summary>{t("hub.player_details")}</summary>
        <div className="hub-kpis">
          {side !== "CT" ? <Stat label={t("hub.lurk_share")} value={fmtPct(profile?.T.lurk_share)} sub={t("hub.lurk_scope")} /> : null}
          {side !== "T" ? <Stat label={t("hub.forward_share")} value={fmtPct(profile?.CT.forward_share)} sub={t("hub.forward_scope")} /> : null}
        </div>
        <h3>{t("heatmap.zones")}</h3>
        <ul className="hub-data-list">{(summaries[0]?.zones[phase] ?? []).slice(0, 5).map((zone) => <li key={zone.place} {...bind(`place:${zone.place}`)} tabIndex={0}><span>{calloutLabel(heatmap.map, zone.place)}</span><strong>{fmtPct(zone.share)}</strong></li>)}</ul>
        <h3>{t("heatmap.holds")}</h3>
        <ul className="hub-data-list">{(summaries[0]?.holds ?? []).map((hold, index) => <li key={`${hold.place}:${index}`} {...bind(`place:${hold.place}`)} tabIndex={0}>{t("heatmap.hold_line", { place: calloutLabel(heatmap.map, hold.place), sec: hold.seconds_per_round ?? "—", rounds: hold.rounds_held })}</li>)}</ul>
        <h3>{t("heatmap.fights")}</h3>
        <ul className="hub-data-list">{(summaries[0]?.fights.places ?? []).map((place) => <li key={place.place} {...bind(`place:${place.place}`)} tabIndex={0}><span>{calloutLabel(heatmap.map, place.place)}</span><strong>{place.kills} / {place.deaths}</strong></li>)}</ul>
        <h3>{t("heatmap.util_spots")}</h3><p className="muted">{t("hub.spot_scope")}</p>
        <ul className="hub-data-list">{landingSpots.map((spot) => <li key={spot.spot_id} {...bind(`spot:${spot.spot_id}`)} tabIndex={0}>
          <span className="grenade-label"><GrenadeIcon type={spot.type} />{calloutLabel(heatmap.map, spot.place)}</span><span>{fmtInt(spot.n)}</span>
          {spot.lineups[0] ? <Link to={`/${heatmap.map}/lineups?id=${encodeURIComponent(spot.lineups[0].lineup_id)}`}>{t("heatmap.to_lineup")}</Link> : null}
        </li>)}</ul>{!landingSpots.length ? <p className="muted">{t("heatmap.no_data")}</p> : null}
      </details>
    </section>
  </div></NumberEntrance.Provider>;
}

function MapPanel({ team, map, playerId, side, change }: { team: TeamEntry; map: string; playerId: string; side: HubSide; change: Change }) {
  const bundle = useData(() => Promise.all([getTeam(map, team.slug), getPlayers(map), getTeamHeatmap(map, team.slug), getHeatmapBaseline(map), getTactics(map)]), [map, team.slug]);
  const quotes = useData(getPlayerQuotes, []);
  const player = bundle.data?.[2].roster.find((entry) => entry.steamid === playerId);
  const displayName = team.maps.find((entry) => entry.map === map)?.display_name ?? map;
  return <section className="hub-panel hub-map-panel" aria-labelledby="hub-heading">
    {!playerId || (!bundle.loading && !player) ? <header className="hub-section-head"><Heading>{playerId ? `${t("hub.player")} · ${displayName}` : `${team.team} · ${displayName}`}</Heading></header> : null}
    {bundle.loading || (playerId && quotes.loading) ? <Loading /> : bundle.error ? <Failure /> : bundle.data ? <>
      {!playerId ? <TeamMapView profile={bundle.data[0]} tactics={bundle.data[4]} heatmap={bundle.data[2]} baseline={bundle.data[3]} change={change} /> : player ? <PlayerView key={player.steamid} displayName={displayName} player={player} profile={bundle.data[1].find((p) => p.steamid === player.steamid && p.team === team.team)} heatmap={bundle.data[2]} baseline={bundle.data[3]} side={side} quote={quotes.data?.[player.steamid]} change={change} /> : <p className="notice" role="alert">{t("hub.player_not_found")}</p>}
    </> : null}
  </section>;
}

export default function TeamsHub() {
  useLang();
  const [params, setParams] = useSearchParams();
  const teams = useData(getHeatmapTeams, []);
  const assets = useData(getAssetSlots, []);
  const [search, setSearch] = useState("");
  const reduced = useReducedMotion();
  const page = useRef<HTMLDivElement>(null);
  useMotionPointer(page, reduced);
  const requested = useMemo(() => ({ team: params.get("team") ?? "", map: params.get("map") ?? "", player: params.get("player") ?? "" }), [params]);
  const slide = useSlideRoute(requested, reduced);
  const { team: teamSlug, map, player } = slide.route;
  const rawSide = params.get("side");
  const side: HubSide = rawSide === "T" || rawSide === "CT" ? rawSide : "T";
  useEffect(() => {
    if (requested.player && rawSide !== "T" && rawSide !== "CT") {
      setParams((current) => { const next = new URLSearchParams(current); next.set("side", "T"); return next; }, { replace: true });
    }
  }, [requested.player, rawSide, setParams]);
  const team = teams.data?.find((entry) => entry.slug === teamSlug);
  const validMap = team?.maps.some((entry) => entry.map === map);
  function change(patch: Partial<Selection>) {
    const next = currentHubParams();
    for (const [key, value] of Object.entries(patch)) value ? next.set(key, value) : next.delete(key);
    if (!next.get("team")) for (const key of ["map", "player", "side"]) next.delete(key);
    else if (!next.get("map")) for (const key of ["player", "side"]) next.delete(key);
    setParams(next);
  }
  function close() {
    const current = currentHubParams();
    if (current.get("player")) change({ player: "", side: "T" });
    else if (current.get("map")) change({ map: "", player: "", side: "T" });
    else change({ team: "" });
  }
  useEffect(() => {
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape" && currentHubParams().get("team") && !event.defaultPrevented) { event.preventDefault(); close(); }
    }
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [params, requested.team]);
  const previous = useRef({ teamSlug, map, player });
  useEffect(() => {
    if (teams.loading) return;
    const prev = previous.current;
    const isClose = (prev.player && !player) || (prev.map && !map) || (prev.teamSlug && !teamSlug);
    if (!teamSlug && !isClose) return;
    const target = isClose ? !teamSlug ? `hub-team-${prev.teamSlug}` : !map ? `hub-map-${prev.map}` : `hub-player-${prev.player}` : "hub-heading";
    let frame = 0;
    const focus = () => {
      const node = document.getElementById(target);
      if (!node) return false;
      const details = node.closest("details");
      if (details) details.open = true;
      node.focus();
      return true;
    };
    const observer = new MutationObserver(() => {
      if (focus()) observer.disconnect();
    });
    frame = requestAnimationFrame(() => {
      if (!focus() && slide.host.current) observer.observe(slide.host.current, { childList: true, subtree: true });
    });
    previous.current = { teamSlug, map, player };
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
  }, [teamSlug, map, player, teams.loading]);
  const filtered = (teams.data ?? []).filter((entry) => entry.team.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  return <ReducedMotion.Provider value={reduced}><Assets.Provider value={assets.data ?? EMPTY_ASSETS}><div className={`hub-page${teamSlug ? " hub-page-selected" : ""}`} ref={page} style={teamTheme(teamSlug)}>
    {!teamSlug ? <header className="page-head"><div><p className="hub-eyebrow">{t("hub.eyebrow")}</p><h1>{t("hub.title")}</h1><p className="muted">{t("hub.description")}</p></div></header> : null}
    {teams.loading ? <Loading /> : teams.error ? <Failure /> : <>
      {teamSlug ? <nav className="hub-breadcrumbs" aria-label={t("hub.breadcrumb")}>
        <h1 className="hub-compact-title">{t("ui.nav_teams")}</h1>
        <button type="button" onClick={() => change({ team: "" })}>{t("hub.all_teams")}</button>
        <span aria-hidden="true">/</span><button type="button" onClick={() => change({ map: "", player: "", side: "T" })} disabled={!map}>{team?.team ?? teamSlug}</button>
        {map ? <><span aria-hidden="true">/</span><button type="button" disabled={!player} onClick={() => change({ player: "", side: "T" })}>{team?.maps.find((m) => m.map === map)?.display_name ?? map}</button></> : null}
        <button type="button" className="hub-close" onClick={close}>{t("hub.close_level")}</button>
      </nav> : null}
      {map ? <MapLinkHint /> : null}
      <div className="hub-stage" ref={slide.host} key={routeKey(slide.route)} data-direction={slide.direction < 0 ? "back" : "forward"}>
      {!teamSlug ? <section aria-label={t("hub.all_teams")}>
        <label className="hub-search">{t("heatmap.search")}<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        <p className="muted" role="status">{t("hub.team_count", { n: filtered.length })}</p>
        <div className="hub-team-grid">{filtered.map((entry) => <button type="button" className="hub-team-card" style={teamTheme(entry.slug)} id={`hub-team-${entry.slug}`} key={entry.slug} onClick={() => change({ team: entry.slug, map: "", player: "", side: "T" })}>
          <Asset path={`logos/teams/${entry.slug}.png`} name={entry.team} badge /><strong>{entry.team}</strong><span>{t("hub.sample", { matches: entry.n_matches, maps: entry.maps.length })}</span>
        </button>)}</div>
      </section> : !team ? <p role="alert">{t("heatmap.team_not_found")}</p> : map && !validMap ? <p role="alert">{t("hub.map_not_found")}</p> : map ? <MapPanel key={`${team.slug}-${map}`} team={team} map={map} playerId={player} side={side} change={change} /> : <TeamPanel team={team} change={change} />}
      </div>
    </>}
  </div></Assets.Provider></ReducedMotion.Provider>;
}
