import Segmented from "../components/Segmented";
import { Reveal, Stagger } from "../components/Motion";
import { teamTheme } from "../theme";
import { PageContext, PageSurface, SampleStrip } from "../components/Page";
import { Fragment, useCallback, useEffect, useMemo, type CSSProperties } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { MapLinkHint, useMapLink } from "../mapLink";
import { heatmapMarkers, linkedLevel } from "../mapPlaces";
import HeatmapCanvas from "../components/HeatmapCanvas";
import MapSwitcher from "../components/MapSwitcher";
import PlayerChips from "../components/PlayerChips";
import { ErrorNotice, Loading } from "../components/Status";
import { getHeatmapBaseline, getHeatmapTeams, getTeamHeatmap, useData } from "../data";
import { fmtInt, fmtNum, fmtPct } from "../format";
import {
  blur, combine, denseLayers, differenceRgba, HEAT_PHASES, ownerRgba, perRound,
  playerColor, playerRgba, toDataUrl, UTILITY_LAYERS, VIEW_WEIGHTS,
} from "../heatmap";
import type { HeatView, Weights } from "../heatmap";
import { calloutLabel, t, useLang } from "../i18n";
import type {
  HeatLayer, HeatmapBaseline, HeatmapTeamIndexEntry, HeatPhase, Lane,
  PlayerSideSummary, RosterEntry, Side, TeamHeatmap as TeamHeatmapData,
} from "../types";
import "../heatmap.css";

const VIEWS: HeatView[] = ["presence", "holding", "fights", "utility"];
const UTILS = ["all", "smoke", "flash", "molotov", "he"] as const;
const LANES: Lane[] = ["A", "MID", "B", "T_SPAWN", "CT_SPAWN", "OTHER"];

function choice<T extends string>(raw: string | null, options: readonly T[], fallback: T): T {
  return options.find((option) => option === raw) ?? fallback;
}

function PlayerCard({
  player, summary, map, side, phases, showHolds, onShowHolds, className = "", style,
}: {
  className?: string;
  style?: CSSProperties;
  player: RosterEntry;
  summary: PlayerSideSummary | undefined;
  map: string;
  side: Side;
  phases: HeatPhase[];
  showHolds: boolean;
  onShowHolds: (checked: boolean) => void;
}) {
  const { bind } = useMapLink();
  const color = playerColor(player.color, side).deep;
  return (
    <article className={`hm-player-card ${className}`} data-motion-tilt style={{ ...style, borderColor: color }}>
      <h2><span className="hm-swatch" style={{ backgroundColor: color }} aria-hidden="true" />{player.name}</h2>
      {!summary ? <p>{t("heatmap.no_data")}</p> : (
        <>
          <h3>{t("heatmap.zones")}</h3>
          {phases.map((phase) => (
            <div key={phase}>
              <h4>{t(`heatmap.phase.${phase}`)}</h4>
              {summary.zones[phase]?.length ? (
                <ul>{summary.zones[phase]?.slice(0, 3).map((zone, index) => (
                  <li key={`${zone.place}:${index}`} {...bind(`place:${zone.place}`)} tabIndex={0}>{calloutLabel(map, zone.place)} · {fmtPct(zone.share)}</li>
                ))}</ul>
              ) : <p>{t("heatmap.no_data")}</p>}
            </div>
          ))}
          <h3>{t("heatmap.holds")}</h3>
          <label className="hm-check">
            <input type="checkbox" checked={showHolds} onChange={(event) => onShowHolds(event.target.checked)} />
            {t("heatmap.show_holds")}
          </label>
          {summary.holds.length ? (
            <ul>{summary.holds.slice(0, 3).map((hold, index) => (
              <li key={`${hold.place}:${index}`} {...bind(`place:${hold.place}`)} tabIndex={0}>{t("heatmap.hold_line", {
                place: calloutLabel(map, hold.place), sec: fmtNum(hold.seconds_per_round, 1), rounds: fmtInt(hold.rounds_held),
              })}</li>
            ))}</ul>
          ) : <p>{t("heatmap.no_data")}</p>}
          <h3>{t("heatmap.fights")}</h3>
          <dl className="hm-metrics">
            <div><dt>{t("heatmap.kpr")}</dt><dd>{fmtNum(summary.fights.kills_pr, 2)}</dd></div>
            <div><dt>{t("heatmap.dpr")}</dt><dd>{fmtNum(summary.fights.deaths_pr, 2)}</dd></div>
            <div><dt>{t("heatmap.openings")}</dt><dd>{fmtInt(summary.fights.opening_kills)} / {fmtInt(summary.fights.opening_deaths)}</dd></div>
          </dl>
          {summary.fights.places.length ? (
            <ul>{summary.fights.places.slice(0, 3).map((place, index) => (
              <li key={`${place.place}:${index}`} {...bind(`place:${place.place}`)} tabIndex={0}>{calloutLabel(map, place.place)} · {fmtInt(place.kills)} / {fmtInt(place.deaths)}</li>
            ))}</ul>
          ) : <p>{t("heatmap.no_data")}</p>}
          <h3>{t("heatmap.utility")}</h3>
          <dl className="hm-metrics">
            {UTILITY_LAYERS.map((layer) => (
              <div key={layer}>
                <dt>{t(`heatmap.util.${layer}`)} · {t("heatmap.unit.count")} / {t("heatmap.per_round")}</dt>
                <dd>{fmtNum(summary.utility.per_round[layer as keyof typeof summary.utility.per_round], 2)}</dd>
              </div>
            ))}
          </dl>
          <h4>{t("heatmap.util_spots")}</h4>
          {summary.utility.spots.length ? (
            <ul>{summary.utility.spots.slice(0, 5).map((spot) => (
              <li key={spot.spot_id} {...bind(`spot:${spot.spot_id}`)} tabIndex={0}>
                {t(`heatmap.util.${spot.type === "flashbang" ? "flash" : spot.type}`)} · {calloutLabel(map, spot.place)} · {fmtInt(spot.n)}
                {spot.lineups.length > 0 && (
                  <Link className="hm-lineup-link" to={`/${encodeURIComponent(map)}/lineups?${new URLSearchParams({ id: spot.lineups[0].lineup_id })}`}>
                    {t("heatmap.to_lineup")}
                  </Link>
                )}
              </li>
            ))}</ul>
          ) : <p>{t("heatmap.no_data")}</p>}
        </>
      )}
    </article>
  );
}

function HeatmapView({ entry, team, baseline }: {
  entry: HeatmapTeamIndexEntry;
  team: TeamHeatmapData;
  baseline: HeatmapBaseline;
}) {
  const { activeId } = useMapLink();
  const [params, setParams] = useSearchParams();
  const ghost = params.get("ghost") === "1";
  const side = choice<Side>(params.get("side"), ["T", "CT"], "T");
  const view = choice(params.get("view"), VIEWS, "presence");
  const util = view === "utility" ? choice(params.get("util"), UTILS, "all") : "all";
  const mode = choice(params.get("mode"), ["stack", "owner"], "stack");
  const rawSigma = params.get("sigma");
  const parsedSigma = rawSigma?.trim() ? Number(rawSigma) : NaN;
  const sigma = Number.isFinite(parsedSigma) && parsedSigma >= 0 && parsedSigma <= 2.5
    ? Math.round(parsedSigma * 10) / 10 : 1;
  const chosenLevel = baseline.levels === 2 && params.get("level") === "1" ? 1 : 0;
  const allSummaries = useMemo(() => Object.values(team.summary).flatMap((sides) => Object.values(sides).filter((summary): summary is PlayerSideSummary => !!summary)), [team]);
  const places = useMemo(() => heatmapMarkers(team.map, baseline, allSummaries, "#efad55"), [team.map, baseline, allSummaries]);
  const utilityMarkers = allSummaries.flatMap((summary) => summary.utility.spots.filter((spot) => spot.radar_x !== null && spot.radar_y !== null).map((spot) => ({
    id: `spot:${spot.spot_id}`, level: spot.level, x: spot.radar_x!, y: spot.radar_y!, color: "#efad55", title: calloutLabel(team.map, spot.place), small: true,
  })));
  const level = linkedLevel(activeId, [...places, ...utilityMarkers], chosenLevel);
  const phasesRaw = params.get("phases");
  const phases = useMemo(() => {
    const requested = phasesRaw?.split(",") ?? [];
    return requested.length && requested.every((phase) => HEAT_PHASES.some((value) => value === phase))
      ? HEAT_PHASES.filter((phase) => requested.includes(phase)) : ["early" as HeatPhase];
  }, [phasesRaw]);
  const playersRaw = params.get("players");
  const selectedIds = useMemo(() => {
    const available = team.roster.filter((player) => player.rounds[side] > 0);
    if (playersRaw === "") return [];
    const requested = playersRaw?.split(",");
    if (!requested || !requested.every((id) => available.some((player) => player.steamid === id))) {
      return available.filter((player) => player.color < 5).map((player) => player.steamid);
    }
    return available.filter((player) => requested.includes(player.steamid)).map((player) => player.steamid);
  }, [playersRaw, team, side]);
  const holdsRaw = params.get("holds") ?? "";
  const holdsIds = useMemo(() => team.roster.filter((player) => holdsRaw.split(",").includes(player.steamid)).map((player) => player.steamid), [team, holdsRaw]);

  // Store defaults as well, so a shared URL has an explicit, reproducible state.
  const canonical = new URLSearchParams(params);
  Object.entries({
    map: team.map, side, players: selectedIds.join(","), view, util,
    phases: phases.join(","), mode, sigma: fmtNum(sigma, 1), level: String(chosenLevel),
  }).forEach(([key, value]) => canonical.set(key, value));
  if (holdsIds.length) canonical.set("holds", holdsIds.join(","));
  else canonical.delete("holds");
  const canonicalQuery = canonical.toString();
  const currentQuery = params.toString();
  useEffect(() => {
    if (canonicalQuery !== currentQuery) setParams(canonicalQuery, { replace: true });
  }, [canonicalQuery, currentQuery, setParams]);

  const update = useCallback((patch: Record<string, string | null>) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      Object.entries(patch).forEach(([key, value]) => {
        if (value === null) next.delete(key);
        else next.set(key, value);
      });
      return next;
    });
  }, [setParams]);
  const changeMap = useCallback((map: string) => update({ map, players: null, level: "0" }), [update]);
  const shape = useMemo(() => ({ grid: baseline.grid, levels: baseline.levels }), [baseline.grid, baseline.levels]);
  const weights = useMemo<Weights>(() => view === "utility" && util !== "all" ? { [util]: 1 } : VIEW_WEIGHTS[view], [view, util]);
  const layers = useMemo(() => Object.keys(weights) as HeatLayer[], [weights]);

  // Selection is deliberately absent: toggling a chip reuses every player's grid and PNG.
  const computed = useMemo(() => team.roster.filter((player) => player.rounds[side] > 0).map((player) => {
    const data = team.players[player.steamid];
    return {
      ...player, values: data ? blur(combine(denseLayers(data, side, phases, shape), weights, shape), shape, sigma) : null,
    };
  }), [team, side, phases, shape, weights, sigma]);
  const images = useMemo(() => computed.map((player) => ({
    key: player.steamid, color: player.color,
    url: player.values ? toDataUrl(playerRgba(player.values, shape, level, playerColor(player.color, side)), shape.grid) : "",
  })), [computed, shape, level, side]);
  const selected = useMemo(() => computed.filter((player) => selectedIds.includes(player.steamid)), [computed, selectedIds]);
  const overlays = useMemo(() => {
    if (ghost) {
      const values = new Float32Array(shape.grid * shape.grid * shape.levels);
      for (const player of selected) if (player.values) for (let i = 0; i < values.length; i++) values[i] += player.values[i];
      const average = blur(combine(denseLayers(baseline, side, phases, shape), weights, shape), shape, sigma);
      const rgba = differenceRgba(values, average, shape, level);
      return rgba.some((value, index) => index % 4 === 3 && value > 0) ? [{ key: "ghost", url: toDataUrl(rgba, shape.grid) }] : [];
    }
    if (mode === "stack") return images.filter((image) => selectedIds.includes(image.key) && image.url)
      .sort((a, b) => b.color - a.color).map(({ key, url }) => ({ key, url }));
    const owners = selected.flatMap((player) => player.values ? [{ values: player.values, color: playerColor(player.color, side) }] : []);
    return owners.length ? [{ key: "owner", url: toDataUrl(ownerRgba(owners, shape, level), shape.grid) }] : [];
  }, [mode, images, selectedIds, selected, shape, level, side, ghost, baseline, phases, weights, sigma]);
  const holdMarkers = selected.flatMap((player) => holdsIds.includes(player.steamid)
    ? (team.summary[player.steamid]?.[side]?.holds ?? []).slice(0, 3)
      .filter((hold) => hold.level === level && Number.isFinite(hold.radar_x) && Number.isFinite(hold.radar_y))
      .map((hold) => ({ id: `place:${hold.place}`, x: hold.radar_x, y: hold.radar_y, color: playerColor(player.color, side).deep, title: `${player.name} · ${calloutLabel(team.map, hold.place)}` }))
    : []);
  const markers = [...places.filter((place) => place.level === level), ...holdMarkers,
    ...utilityMarkers.filter((marker, index) => marker.level === level && utilityMarkers.findIndex((item) => item.id === marker.id) === index)];
  const setup = team.setup[side]?.early;
  const setupLanes = LANES.filter((lane) => setup?.[lane]?.length);
  const captionLabel = view === "utility" && util !== "all" ? t(`heatmap.util.${util}`) : t(`heatmap.view.${view}`);

  return (
    <PageSurface className="hm-page" style={teamTheme(entry.slug)} data-side={side}>
      <header className="page-head">
        <div><p className="eyebrow">{team.map}</p><h1>{entry.team} · {t("heatmap.title")}</h1><PageContext>{t("site.team_heatmap_context")}</PageContext></div>
        <Link to="/heatmaps" className="button button-ghost">{t("heatmap.back")}</Link>
        <Link className="button button-ghost" to={`/teams-hub?${new URLSearchParams({ team: entry.slug, map: team.map })}`}>{t("ui.nav_teams")}</Link>
      </header>
      <SampleStrip matches={entry.maps.find((map) => map.map === team.map)?.n_matches} players={selected.length} maps={entry.maps.length} />
      <MapSwitcher maps={entry.maps} map={team.map} onChange={changeMap} />
      <MapLinkHint />
      <div className="hm-workspace">
        <div className="hm-controls">
          <fieldset className="hm-field">
            <legend>{t("heatmap.side")}</legend>
            <Segmented className="hm-buttons">{(["T", "CT"] as const).map((value) => (
              <button key={value} type="button" aria-pressed={side === value} onClick={() => update({ side: value, players: null })}>{value}</button>
            ))}</Segmented>
          </fieldset>
          <PlayerChips roster={team.roster} side={side} selected={selectedIds} onChange={(ids) => update({ players: ids.join(",") })} />
          <Segmented className="hm-buttons" role="group" aria-label={t("heatmap.title")}>
            {VIEWS.map((value) => (
              <button key={value} type="button" aria-pressed={view === value} onClick={() => update({ view: value })}>{t(`heatmap.view.${value}`)}</button>
            ))}
          </Segmented>
          {view === "utility" && <Segmented className="hm-buttons" role="group" aria-label={t("heatmap.utility")}>
            {UTILS.map((value) => (
              <button key={value} type="button" aria-pressed={util === value} onClick={() => update({ util: value })}>{t(`heatmap.util.${value}`)}</button>
            ))}
          </Segmented>}
          <fieldset className="hm-field">
            <legend>{t("heatmap.phases")}</legend>
            <Segmented className="hm-buttons">{HEAT_PHASES.map((phase) => <button type="button" key={phase} aria-pressed={phases.length === 1 && phases[0] === phase} onClick={() => update({ phases: phase })}>{t(`round2.time_${phase}`)}</button>)}</Segmented>
            <p className="muted">{t("round2.time_help")}</p>
          </fieldset>
          <Segmented className="hm-buttons" role="group" aria-label={t("heatmap.mode.owner")}>
            {(["stack", "owner"] as const).map((value) => (
              <button key={value} type="button" aria-pressed={mode === value} onClick={() => update({ mode: value })}>{t(`heatmap.mode.${value}`)}</button>
            ))}
          </Segmented>
          <label className="hm-slider">
            <span>{t("heatmap.sigma")} · {fmtNum(sigma, 1)}</span>
            <input type="range" min="0" max="2.5" step="0.1" value={sigma} onChange={(event) => update({ sigma: event.target.value })} />
          </label>
          {baseline.levels === 2 && <Segmented className="hm-buttons" role="group" aria-label={t("heatmap.level.upper")}>
            {([0, 1] as const).map((value) => (
              <button key={value} type="button" aria-pressed={level === value} onClick={() => update({ level: String(value) })}>{t(`heatmap.level.${value === 0 ? "upper" : "lower"}`)}</button>
            ))}
          </Segmented>}
          <label className="ghost-toggle" title="比较所选队员与本图同侧、同阶段的归一化分布"><input type="checkbox" checked={ghost} onChange={(event) => update({ ghost: event.target.checked ? "1" : null })} />{t("round5.ghost_toggle")}</label>
          <p className="hm-help">{ghost ? t("round5.ghost_legend") : t("heatmap.help")}</p>
        </div>
        <figure className="hm-figure">
          <Reveal className="motion-radar" key={`${team.map}:${level}`}><HeatmapCanvas map={team.map} level={level} overlays={overlays} markers={markers} /></Reveal>
          <figcaption>
            {selected.length ? selected.map((player) => (
              <div key={player.steamid} className="hm-caption">
                <span className="hm-swatch" style={{ backgroundColor: playerColor(player.color, side).deep }} aria-hidden="true" />
                <span>{player.name} · {captionLabel} {fmtNum(team.players[player.steamid] ? perRound(team.players[player.steamid], side, phases, layers) : null, 1)} {t(view === "presence" || view === "holding" ? "heatmap.unit.seconds" : "heatmap.unit.count")} / {t("heatmap.per_round")}</span>
              </div>
            )) : <p>{t("heatmap.no_data")}</p>}
          </figcaption>
        </figure>
      </div>
      <section className="hm-setup">
        <h2>{t("heatmap.setup")}</h2>
        {setupLanes.length ? setupLanes.map((lane, index) => (
          <Fragment key={lane}>
            {index > 0 && " ｜ "}<span>{t(`lane.${lane}`)}: </span>
            {setup?.[lane]?.map((nameOrId, playerIndex) => {
              const player = team.roster.find((item) => item.steamid === nameOrId)
                ?? team.roster.find((item) => item.name === nameOrId);
              return <Fragment key={`${nameOrId}:${playerIndex}`}>{playerIndex > 0 && ", "}<span style={player ? { color: playerColor(player.color, side).deep } : undefined}>{player?.name ?? nameOrId}</span></Fragment>;
            })}
          </Fragment>
        )) : <p>{t("heatmap.no_data")}</p>}
      </section>
      <Stagger className="hm-player-grid">
        {selected.map((player) => (
          <PlayerCard key={player.steamid} player={player} summary={team.summary[player.steamid]?.[side]} map={team.map} side={side} phases={phases}
            showHolds={holdsIds.includes(player.steamid)} onShowHolds={(checked) => update({ holds: (checked ? [...holdsIds, player.steamid] : holdsIds.filter((id) => id !== player.steamid)).join(",") })} />
        ))}
      </Stagger>
    </PageSurface>
  );
}

function MapData({ entry, map }: { entry: HeatmapTeamIndexEntry; map: string }) {
  const { data, loading, error } = useData(async () => {
    const [team, baseline] = await Promise.all([getTeamHeatmap(map, entry.slug), getHeatmapBaseline(map)]);
    return { team, baseline };
  }, [map, entry.slug]);
  if (loading) return <Loading />;
  if (error || !data) return <PageSurface className="hm-page" style={teamTheme(entry.slug)}>
    <header className="page-head"><div><p className="eyebrow">{map}</p><h1>{entry.team} · {t("heatmap.title")}</h1><PageContext>{t("site.team_heatmap_context")}</PageContext></div>
      <Link to="/heatmaps" className="button button-ghost">{t("heatmap.back")}</Link></header>
    <ErrorNotice error={error ?? new Error(t("heatmap.no_data"))} />
  </PageSurface>;
  return <HeatmapView entry={entry} team={data.team} baseline={data.baseline} />;
}

export default function TeamHeatmap() {
  useLang();
  const { slug = "" } = useParams<{ slug: string }>();
  const [params] = useSearchParams();
  const { data: teams, loading, error } = useData(getHeatmapTeams, []);
  if (loading) return <Loading />;
  if (error) return <ErrorNotice error={error} />;
  const entry = teams?.find((team) => team.slug === slug);
  if (!entry || !entry.maps.length) return (
    <PageSurface className="hm-page" style={teamTheme(slug)}>
      <header className="page-head"><div><p className="eyebrow">{t("site.eyebrow")}</p><h1>{t("heatmap.title")}</h1><PageContext>{t("site.team_heatmap_context")}</PageContext></div>
        <Link to="/heatmaps" className="button button-ghost">{t("heatmap.back")}</Link></header>
      <p role="status">{t(entry ? "heatmap.no_data" : "heatmap.team_not_found")}</p>
    </PageSurface>
  );
  const map = entry.maps.find((item) => item.map === params.get("map"))?.map ?? entry.maps[0].map;
  return <MapData key={`${slug}:${map}`} entry={entry} map={map} />;
}
