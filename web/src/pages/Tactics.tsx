import PracticeCopy from "../components/PracticeCopy";
import { recipeBind } from "../practice";
import Num from "../components/Num";
import Segmented from "../components/Segmented";
import { ctSetupLabel } from "../labels";
import { ReplayButton } from "../components/RoundReplay";
import CountUp from "../components/CountUp";
import { Reveal } from "../components/Motion";
import type { CSSProperties } from "react";
import { PageContext, PageSurface } from "../components/Page";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import GrenadeIcon from "../components/GrenadeIcon";
import { MapLinkHint } from "../mapLink";
import RecipeRadar, { SpotList, type RecipeSpot } from "../components/RecipeRadar";
import Stat from "../components/Stat";
import { ErrorNotice, Loading } from "../components/Status";
import { getLineups, getMeta, getTactics, getTeams, useData } from "../data";
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
      <ShareBars rows={[...data.setups_20s].sort((a, b) => b.rounds - a.rounds).slice(0, 6)} labelFor={ctSetupLabel} />
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

function resolveSpot(map: string, ref: SpotRef, spot: Spot | undefined, core: boolean, number: number, lang: Lang, byLineup: Map<string, Lineup>): RecipeSpot {
  const lineups = ref.lineups.length ? ref.lineups : spot?.lineups ?? [];
  const mostThrown = [...lineups].sort((a, b) => b.n_throws - a.n_throws)[0];
  return {
    lineup: mostThrown ? byLineup.get(mostThrown.lineup_id) : undefined,
    id: ref.spot_id, type: ref.type, spot, core, number: ref.order ?? number, share: ref.share,
    thrower: ref.thrower, throwerTeam: ref.thrower_team, throwPlace: calloutLabel(map, ref.throw_place), order: ref.order,
    name: ref.name?.[lang] || spot?.name?.[lang] || ref.label,
    to: mostThrown ? `/${encodeURIComponent(map)}/lineups?${new URLSearchParams({ id: mostThrown.lineup_id })}` : null,
  };
}

function recipeSpots(map: string, recipe: Recipe, byId: Map<string, Spot>, lang: Lang, byLineup: Map<string, Lineup>): RecipeSpot[] {
  return [...recipe.core.map((ref) => ({ ref, core: true })), ...recipe.options.map((ref) => ({ ref, core: false }))]
    .sort((a, b) => (a.ref.order ?? Infinity) - (b.ref.order ?? Infinity))
    .map(({ ref, core }, index) => resolveSpot(map, ref, byId.get(ref.spot_id), core, index + 1, lang, byLineup));
}

function RecipeTitle({ entries }: { entries: RecipeSpot[] }) {
  return <span className="tactics-recipe-name">{entries.length ? entries.map((entry, index) => <span key={entry.id}>
    {index > 0 && <span className="muted"> + </span>}<GrenadeIcon type={entry.type} /> {entry.name}
  </span>) : t("tactics.no_spots")}</span>;
}

function RecipeDetails({ recipe, entries, splitDefinition, map, teams }: { recipe: Recipe; entries: RecipeSpot[]; splitDefinition: string; map: string; teams: Map<string, string> }) {
  const tempos = (["fast", "mid", "late"] as const).map((value) => ({ value, rounds: recipe.tempo.find((row) => row.value === value)?.rounds ?? 0 }));
  const total = tempos.reduce((n, row) => n + row.rounds, 0);
  return <div className="tactics-recipe-details">
    <PracticeCopy command={recipeBind(recipe.id, entries.map((entry) => entry.lineup))} label={t("round5.recipe_bind")} tip={t("round5.recipe_bind_tip")} />
    <dl className="tactics-detail-stats">
      <div><dt>{t("ui.matches_title")}</dt><dd>{t("round2.recipe_matches", { n: fmtInt(recipe.n_matches) })}</dd></div>
      <div><dt>{t("tactics.plant_rate")}</dt><dd><Num value={fmtPct(recipe.plant_rate)} /></dd></div>
      <div><dt tabIndex={0} title={splitDefinition}>多方向进点率 ⓘ</dt><dd><Num value={fmtPct(recipe.split_rate)} /></dd></div>
      <div><dt>{t("tactics.avg_flashes")}</dt><dd>{fmtNum(recipe.avg_flashes)}</dd></div>
    </dl>
    {recipe.wp && recipe.wp.n > 0 && Number.isFinite(recipe.wp.before) && Number.isFinite(recipe.wp.after) ? <p className="recipe-wp">
      胜率变化 <strong>{fmtPct(recipe.wp.before)} → {fmtPct(recipe.wp.after)}</strong>{" "}
      <span className="data-tooltip" tabIndex={0} role="note" aria-label="胜率变化说明">ⓘ<span role="tooltip">T 方模型胜率：进点前 5 秒与进点后 10 秒的均值（{fmtInt(recipe.wp.n)} 回合）。能推进到进点的回合本就较顺利，因此估计偏高；用于套路之间的比较，不代表这套道具的绝对或因果效果。</span></span>
    </p> : null}
    <div className="tactics-spot-columns">
      <section><h4>{t("tactics.core")}</h4><SpotList entries={entries.filter((entry) => entry.core)} /></section>
      <section><h4>{t("tactics.optional")}</h4>{entries.some((entry) => !entry.core) ? <SpotList entries={entries.filter((entry) => !entry.core)} /> : <p className="muted">{t("tactics.no_data")}</p>}</section>
    </div>
    <h4>{t("tactics.tempo_title")}</h4>
    {total ? <div className="tactics-tempo-bar" role="img" aria-label={tempos.map((row) => `${t(`tactics.tempo.${row.value}`)} ${fmtPct(row.rounds / total)}`).join(" · ")}>
      {tempos.map((row) => <span key={row.value} data-tempo={row.value} style={{ flexGrow: row.rounds }} title={`${t(`tactics.tempo.${row.value}`)} · ${fmtInt(row.rounds)} 回合`} />)}
    </div> : <p className="muted">{t("tactics.no_data")}</p>}
    <ul className="tactics-tempo-labels">{tempos.map((row) => <li key={row.value} data-tempo={row.value}>{t(`tactics.tempo.${row.value}`)} {total ? fmtPct(row.rounds / total) : "—"}</li>)}</ul>
    <details><summary>{t("tactics.teams")}</summary><ul className="tactics-inline-list">{[...recipe.teams].sort((a, b) => b.rounds - a.rounds).map((team) => <li key={team.team}>{teams.has(team.team) ? <Link to={`/teams-hub?${new URLSearchParams({ team: teams.get(team.team)!, map })}`}>{team.team}</Link> : team.team} · {t("tactics.round_count", { n: fmtInt(team.rounds) })}</li>)}</ul></details>
    <details><summary>{t("tactics.examples")}</summary>{recipe.examples.length ? <ul className="tactics-inline-list">{recipe.examples.map((example) => <li key={`${example.demo_id}:${example.round_num}:${example.team}`}>
      {example.team} · {t("tactics.example_round", { n: fmtInt(example.round_num) })} · <code>{example.demo_id}</code> {example.replay ? <ReplayButton map={map} demoId={example.demo_id} round={example.round_num} /> : null}
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
  const teamData = useData(() => getTeams(map), [map]);
  const teams = useMemo(() => new Map((teamData.data ?? []).map((team) => [team.team, team.slug])), [teamData.data]);
  const { data: lineupData } = useData(() => getLineups(map), [map]);
  const byLineup = useMemo(() => new Map((lineupData ?? []).map((lineup) => [lineup.id, lineup])), [lineupData]);
  const { data: meta } = useData(() => getMeta(map), [map]);
  const [collapsedRecipe, setCollapsedRecipe] = useState<string | null>(null);
  const [setupChoice, setSetupChoice] = useState<string | null>(null);
  const [collapsedSetup, setCollapsedSetup] = useState<string | null>(null);
  const spotsById = useMemo(() => new Map((data?.spots ?? []).map((spot) => [spot.spot_id, spot])), [data]);
  const recipes = useMemo(() => (data?.recipes ?? []).filter((recipe) => site === "all" || recipe.site === site)
    .sort((a, b) => (sort === "win_rate" ? b.win_rate - a.win_rate : b.n_rounds - a.n_rounds)
      || b.n_rounds - a.n_rounds || a.id.localeCompare(b.id)), [data, site, sort]);
  const selected = recipes.find((recipe) => recipe.id === params.get("recipe")) ?? recipes[0];
  const shown = selected;
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
  useEffect(() => { setCollapsedRecipe(null); setSetupChoice(null); setCollapsedSetup(null); }, [map, site, sort, side]);
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
      <Segmented className="segmented tactics-sides" role="group" aria-label={t("ui.filter_side")}>
        {(["T", "CT"] as const).map((value) => <button key={value} type="button" className={side === value ? "is-active" : ""} aria-pressed={side === value} onClick={() => update("side", value)}>{t(`tactics.side_${value}`)}</button>)}
      </Segmented>
    </header>
    <dl className="tactics-key-numbers">
      {side === "T" ? <>
        <KeyNumber primary label={t("tactics.top_target")} value={topTarget ? fmtPct(topTarget.share) : "—"} context={topTarget ? t("tactics.target_context", { site: siteLabel(topTarget.value) }) : t("tactics.no_data")} />
        <KeyNumber label={t("tactics.avg_commit")} value={fmtSeconds(data.t_overview.avg_commit_s)} context={t("tactics.commit_context")} />
        <KeyNumber label={t("tactics.signature_win")} value={fmtPct(topRecipe?.win_rate)} context={topRecipeName} />
      </> : <>
        <KeyNumber primary label={t("tactics.default_setup")} value={fmtPct(setups[0]?.share)} context={ctSetupLabel(setups[0]?.value)} />
        <KeyNumber label={t("tactics.setup_win")} value={fmtPct(setups[0]?.win_rate)} context={t("tactics.setup_context")} />
        <KeyNumber label={t("tactics.forward_rate")} value={fmtPct(data.ct_overview.forward_rate)} context={t("tactics.forward_context")} />
        <KeyNumber label={t("tactics.stack_rate")} value={fmtPct(data.ct_overview.stack_rate)} context={t("tactics.stack_context")} />
      </>}
    </dl>
    <MapLinkHint />
    <div className="tactics-workspace">
      <aside className="tactics-map-panel">
        <Reveal className="motion-radar" key={`${map}:${side}`}><RecipeRadar key={`${map}:${side}:${selected?.id ?? "ct"}`} map={map} scale={scale} spots={side === "T" ? entries : ctSpots} title={side === "T" ? t("tactics.selected_utility") : t("tactics.ct_utility")}
          routes={side === "T" ? shown?.routes ?? [] : undefined} routeKey={shown?.id}
          site={side === "T" ? shown?.site : site === "all" ? undefined : site}
          selectionLabel={side === "T" && shown ? `${siteLabel(shown.site)} · ${entries.filter((entry) => entry.core).map((entry) => entry.name).join(" + ")}` : undefined} /></Reveal>
      </aside>
      <section className="tactics-browser" aria-labelledby="tactics-recipes-title">
        <h2 id="tactics-recipes-title">{t(side === "T" ? "tactics.recipes" : "tactics.setups")}</h2>
        <div className="tactics-controls">
          <Segmented className="segmented" role="group" aria-label={t("tactics.site")}>
            {(["all", "A", "B"] as const).map((value) => <button key={value} type="button" className={site === value ? "is-active" : ""} aria-pressed={site === value} onClick={() => update("site", value)}>{value === "all" ? t("ui.filter_all") : siteLabel(value)}</button>)}
          </Segmented>
          {side === "T" && <label><span className="visually-hidden">{t("tactics.sort")}</span><select value={sort} onChange={(event) => update("sort", event.target.value)}><option value="rounds">{t("tactics.sort_rounds")}</option><option value="win_rate">{t("tactics.sort_win_rate")}</option></select></label>}
        </div>
        {side === "T" ? <div className="tactics-recipes">
          <p className="muted tactics-help">{t("tactics.recipe_count", { n: fmtInt(recipes.length) })} · {t("tactics.preview_hint")}</p>
          {recipes.length ? recipes.map((recipe, index) => {
            const rowEntries = recipeSpots(map, recipe, spotsById, lang, byLineup);
            const active = recipe.id === selected?.id;
            const open = active && collapsedRecipe !== recipe.id;
            return <article className={`tactics-recipe motion-reveal${active ? " is-selected" : ""}`} data-motion-tilt={active || undefined} style={{ "--stagger": `${Math.min(index * 55, 385)}ms` } as CSSProperties} key={recipe.id} data-recipe-id={recipe.id}>
              <h3><button type="button" className="tactics-recipe-toggle" aria-expanded={open} aria-controls={`details-${recipe.id}`} onClick={() => {
                setCollapsedRecipe(open ? recipe.id : null); update("recipe", recipe.id);
              }}><span className="tactics-recipe-heading"><span className="tactics-chevron" aria-hidden="true">{open ? "▾" : "▸"}</span><span className="tactics-site">{siteLabel(recipe.site)}</span><RecipeTitle entries={rowEntries.filter((entry) => entry.core)} /></span>
                <span className="tactics-row-meta">{t("tactics.recipe_meta", { rounds: fmtInt(recipe.n_rounds), win: fmtPct(recipe.win_rate), time: fmtSeconds(recipe.median_commit_s) })}</span>
              </button></h3>
              {(recipe.intent_badges?.length || recipe.entry_sync_sec != null) ? <div className="recipe-intent">
                {recipe.intent_badges?.map((badge) => <span className="recipe-intent-badge" key={badge}>{({ fake: "含假打转点", sync_pinch: "多向同步夹击", rush: "爆弹一波流" })[badge]}</span>)}
                {recipe.entry_sync_sec != null ? <small>两路进点相差 {fmtNum(recipe.entry_sync_sec, 1)} 秒</small> : null}
              </div> : null}
              <div id={`details-${recipe.id}`} hidden={!open}>{open && <RecipeDetails recipe={recipe} map={map} teams={teams} entries={rowEntries} splitDefinition={`进点位置相距至少 400 游戏单位，或相对包点中心的方位角相差至少 50°。不限定中路。导出定义：${String(data.definitions.split ?? "未提供")}`} />}</div>
            </article>;
          }) : <p className="muted">{t("tactics.no_recipes")}</p>}
        </div> : <>
          <p className="muted tactics-help">{t("tactics.ct_utility_context")}</p>
          {setups.map((setup, index) => {
            const active = setup.value === currentSetup?.value;
            const open = active && collapsedSetup !== setup.value;
            return <article className={`tactics-recipe motion-reveal${active ? " is-selected" : ""}`} data-motion-tilt={active || undefined} style={{ "--stagger": `${Math.min(index * 55, 385)}ms` } as CSSProperties} key={setup.value}>
              <h3><button type="button" className="tactics-recipe-toggle" aria-expanded={open} aria-controls={`setup-${index}`} onClick={() => { setSetupChoice(setup.value); setCollapsedSetup(open ? setup.value : null); }}>
                <span className="tactics-recipe-heading"><span aria-hidden="true">{open ? "▾" : "▸"}</span>{ctSetupLabel(setup.value)}</span>
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
