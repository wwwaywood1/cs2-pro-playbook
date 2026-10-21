import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import Stat from "../components/Stat";
import { ErrorNotice, Loading } from "../components/Status";
import { getMeta, getTactics, useData } from "../data";
import { fmtInt, fmtNum, fmtPct, fmtSeconds } from "../format";
import { t, useLang, type Lang } from "../i18n";
import type { CTTactics, Ranked, Recipe, Spot, SpotRef, TTactics } from "../types";
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
        <Stat label={t("tactics.split_rate")} value={fmtPct(data.split_rate)} />
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
  ref: SpotRef;
  spot: Spot | undefined;
  core: boolean;
  number: number;
  name: string;
  to: string | null;
}

function resolveSpot(map: string, ref: SpotRef, spot: Spot | undefined, core: boolean, number: number, lang: Lang): RecipeSpot {
  // Use the most-thrown position for the landing spot, regardless of export order.
  const lineups = spot?.lineups.length ? spot.lineups : ref.lineups;
  const mostThrown = lineups.reduce<(typeof lineups)[number] | undefined>(
    (best, lineup) => !best || lineup.n_throws > best.n_throws ? lineup : best, undefined,
  );
  return {
    ref, spot, core, number,
    name: ref.name?.[lang] || spot?.name?.[lang] || ref.label,
    to: mostThrown ? `/${encodeURIComponent(map)}/lineups?${new URLSearchParams({ id: mostThrown.lineup_id })}` : null,
  };
}

function RecipeRadar({ map, level, spots }: { map: string; level: number; spots: RecipeSpot[] }) {
  const source = `${import.meta.env.BASE_URL}radars/${map}${level === 1 ? "_lower" : ""}.png`;
  const [failedSource, setFailedSource] = useState<string | null>(null);
  return (
    <figure className="tactics-radar-wrap">
      <svg className="radar tactics-radar" viewBox="0 0 1024 1024" role="group" aria-label={t("tactics.radar_label", { map })}>
        <rect className="radar-bg" width="1024" height="1024" />
        {failedSource !== source && <image href={source} width="1024" height="1024" onError={() => setFailedSource(source)} />}
        {spots.map((entry) => {
          const spot = entry.spot;
          if (!spot || spot.level !== level || !Number.isFinite(spot.radar_x) || !Number.isFinite(spot.radar_y)) return null;
          const label = `${entry.number}. ${entry.name} · ${t(`grenade.${entry.ref.type}`)} · ${t(entry.core ? "tactics.core" : "tactics.optional")}`;
          const marker = (
            <g transform={`translate(${spot.radar_x}, ${spot.radar_y})`} className={entry.core ? "tactics-marker is-core" : "tactics-marker"}>
              <circle className="tactics-marker-hit" r="30" />
              {entry.ref.type === "smoke"
                ? <circle className="tactics-smoke" r="16" />
                : <path className="tactics-molotov" d="M 0 -20 L 19 15 L -19 15 Z" />}
              <text x="22" y="-20">{entry.number}</text>
            </g>
          );
          return entry.to ? (
            <a key={entry.ref.spot_id} href={`#${entry.to}`} aria-label={`${label} · ${t("tactics.open_lineup")}`}>
              <title>{label} · {t("tactics.open_lineup")}</title>{marker}
            </a>
          ) : <g key={entry.ref.spot_id}><title>{label}</title>{marker}</g>;
        })}
      </svg>
      {map === "de_nuke" && <figcaption className="muted">{t(`heatmap.level.${level === 1 ? "lower" : "upper"}`)}</figcaption>}
      {failedSource === source && <p className="muted">{t("tactics.radar_unavailable")}</p>}
    </figure>
  );
}

function SpotList({ entries }: { entries: RecipeSpot[] }) {
  if (!entries.length) return <p className="muted">{t("tactics.no_data")}</p>;
  return (
    <ul className="tactics-spots">
      {entries.map((entry) => {
        const name = entry.core ? <strong>{entry.name}</strong> : entry.name;
        return (
          <li key={entry.ref.spot_id}>
            <span className={`tactics-symbol tactics-symbol-${entry.ref.type}`} aria-hidden="true" />
            <span>
              {entry.number}. {entry.to ? <Link to={entry.to} title={t("tactics.open_lineup")}>{name}</Link> : name}
              <span className="muted"> · {t(`grenade.${entry.ref.type}`)} · {fmtPct(entry.ref.share)}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function RecipeCard({ map, recipe, spotsById, lang }: { map: string; recipe: Recipe; spotsById: Map<string, Spot>; lang: Lang }) {
  const spots = [...recipe.core.map((ref) => ({ ref, core: true })), ...recipe.options.map((ref) => ({ ref, core: false }))]
    .map(({ ref, core }, index) => resolveSpot(map, ref, spotsById.get(ref.spot_id), core, index + 1, lang));
  const levels = [...new Set(spots.flatMap(({ spot }) => spot ? [spot.level] : []))].sort();
  return (
    <article className="panel tactics-recipe" id={recipe.id}>
      <header className="page-head">
        <h3>{siteLabel(recipe.site)} · {recipe.id}</h3>
        <span className="chip">{t("tactics.round_count", { n: fmtInt(recipe.n_rounds) })}</span>
      </header>
      <div className="tactics-recipe-body">
        <div>
          {(levels.length ? levels : [0]).map((level) => <RecipeRadar key={`${map}:${level}`} map={map} level={level} spots={spots} />)}
          <p className="muted tactics-help">{t("tactics.radar_help")}</p>
        </div>
        <div>
          <h4>{t("tactics.core")}</h4>
          <SpotList entries={spots.filter((spot) => spot.core)} />
          <h4>{t("tactics.optional")}</h4>
          <SpotList entries={spots.filter((spot) => !spot.core)} />
          <div className="stat-row">
            <Stat label={t("tactics.rounds")} value={fmtInt(recipe.n_rounds)} />
            <Stat label={t("ui.matches_title")} value={fmtInt(recipe.n_matches)} />
            <Stat label={t("metric.win_rate")} value={fmtPct(recipe.win_rate)} />
            <Stat label={t("tactics.plant_rate")} value={fmtPct(recipe.plant_rate)} />
            <Stat label={t("tactics.median_commit")} value={fmtSeconds(recipe.median_commit_s)} />
          </div>
          <h4>{t("tactics.tempo_title")}</h4>
          {recipe.tempo.length ? (
            <ul className="tactics-inline-list">
              {recipe.tempo.map((row) => <li key={row.value}>{t(`tactics.tempo.${row.value}`)} · {t("tactics.round_count", { n: fmtInt(row.rounds) })}</li>)}
            </ul>
          ) : <p className="muted">{t("tactics.no_data")}</p>}
          <h4>{t("tactics.teams")}</h4>
          {recipe.teams.length ? (
            <ul className="tactics-inline-list">
              {[...recipe.teams].sort((a, b) => b.rounds - a.rounds).map((team) => (
                <li key={team.team}>{team.team} · {t("tactics.round_count", { n: fmtInt(team.rounds) })}</li>
              ))}
            </ul>
          ) : <p className="muted">{t("tactics.no_data")}</p>}
        </div>
      </div>
    </article>
  );
}

export default function Tactics() {
  const lang = useLang();
  const { map = "" } = useParams<{ map: string }>();
  const [params, setParams] = useSearchParams();
  const site = params.get("site") === "A" ? "A" : params.get("site") === "B" ? "B" : "all";
  const sort = params.get("sort") === "win_rate" ? "win_rate" : "rounds";
  const { data, loading, error } = useData(() => getTactics(map), [map]);
  const { data: meta } = useData(() => getMeta(map), [map]);
  const currentQuery = params.toString();
  const canonical = new URLSearchParams(params);
  canonical.set("site", site);
  canonical.set("sort", sort);
  const canonicalQuery = canonical.toString();
  useEffect(() => {
    if (canonicalQuery !== currentQuery) setParams(canonicalQuery, { replace: true });
  }, [canonicalQuery, currentQuery, setParams]);

  const spotsById = useMemo(() => new Map((data?.spots ?? []).map((spot) => [spot.spot_id, spot])), [data]);
  const recipes = useMemo(() => (data?.recipes ?? []).filter((recipe) => site === "all" || recipe.site === site)
    .sort((a, b) => (sort === "win_rate" ? b.win_rate - a.win_rate : b.n_rounds - a.n_rounds)
      || b.n_rounds - a.n_rounds || a.id.localeCompare(b.id)), [data, site, sort]);
  const update = (key: "site" | "sort", value: string) => setParams((current) => {
    const next = new URLSearchParams(current);
    next.set(key, value);
    return next;
  });

  if (loading) return <Loading />;
  if (error || !data) return <ErrorNotice error={error ?? new Error(t("tactics.no_data"))} />;
  return (
    <div className="tactics-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">{map}</p>
          <h1>{meta?.display_name ?? map} · {t("ui.nav_tactics")}</h1>
          <p className="muted">{t("tactics.description")}</p>
        </div>
      </header>
      <div className="two-col tactics-overviews">
        <TOverview data={data.t_overview} />
        <CTOverview data={data.ct_overview} />
      </div>
      <section aria-labelledby="tactics-recipes-title">
        <h2 id="tactics-recipes-title">{t("tactics.recipes")}</h2>
        <div className="filters">
          <div className="filter-group">
            <span className="filter-label" id="tactics-site-label">{t("tactics.site")}</span>
            <div className="segmented" role="group" aria-labelledby="tactics-site-label">
              {(["all", "A", "B"] as const).map((value) => (
                <button key={value} type="button" className={site === value ? "is-active" : ""} aria-pressed={site === value} onClick={() => update("site", value)}>
                  {value === "all" ? t("ui.filter_all") : siteLabel(value)}
                </button>
              ))}
            </div>
          </div>
          <label className="filter-group">
            <span className="filter-label">{t("tactics.sort")}</span>
            <select value={sort} onChange={(event) => update("sort", event.target.value)}>
              <option value="rounds">{t("tactics.sort_rounds")}</option>
              <option value="win_rate">{t("tactics.sort_win_rate")}</option>
            </select>
          </label>
          <p className="result-count" role="status">{t("tactics.recipe_count", { n: fmtInt(recipes.length) })}</p>
        </div>
        <div className="tactics-recipes">
          {recipes.length ? recipes.map((recipe) => <RecipeCard key={`${map}:${recipe.id}`} map={map} recipe={recipe} spotsById={spotsById} lang={lang} />)
            : <p className="panel muted">{t("tactics.no_recipes")}</p>}
        </div>
      </section>
    </div>
  );
}
