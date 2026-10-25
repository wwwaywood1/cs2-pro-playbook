import MatchDate, { MatchTimeFilter } from "./MatchDate";
import { getCTPatterns, getIndex, useData } from "../data";
import { inTimeRange, newestMatch, type TimeRange } from "../matchDates";
import Segmented from "./Segmented";
import { ctSetupLabel } from "../labels";
import { Fragment, useEffect, useState, type ReactNode, type CSSProperties } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Stagger } from "./Motion";
import Stat from "./Stat";
import MatchWinprob from "./MatchWinprob";
import { fmtInt, fmtPct, fmtSeconds } from "../format";
import { t, useLang } from "../i18n";
import type { BuyType, CTSide, Ranked, Side, TeamProfile, TSide } from "../types";

const BUY_TYPES: BuyType[] = ["pistol", "eco", "force", "full"];
const SIDE_ORDER: Side[] = ["T", "CT"];

function siteLabel(value: string): string {
  if (value === "A") return t("region.A_SITE");
  if (value === "B") return t("region.B_SITE");
  if (value === "none") return t("ui.no_plant");
  return "—";
}

function CommonStats({ side }: { side: TSide | CTSide }) {
  return (
    <div className="stat-row">
      <Stat
        label={t("metric.win_rate")}
        value={fmtPct(side.win_rate)}
        sub={`${fmtInt(side.won)} / ${fmtInt(side.rounds)}`}
      />
      <Stat
        label={t("metric.opening_win_rate")}
        value={fmtPct(side.opening_win_rate)}
      />
      <Stat
        label={t("metric.avg_first_kill_s")}
        value={fmtSeconds(side.avg_first_kill_s)}
      />
    </div>
  );
}

interface RankedBarsProps {
  rows: Ranked[];
  labelFor: (value: string) => string;
}

function RankedBars({ rows, labelFor }: RankedBarsProps) {
  if (rows.length === 0) return <div className="empty">—</div>;
  return (
    <ul className="ranked-list">
      {rows.map((row) => {
        const share = Math.max(0, Math.min(1, row.share ?? 0));
        return (
          <li key={row.value} className="ranked-row">
            <div className="ranked-head">
              <span>{labelFor(row.value)}</span>
              <span className="ranked-count">{fmtInt(row.rounds)}</span>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${share * 100}%` }} />
            </div>
            <div className="ranked-meta">
              <span>{fmtPct(row.share)}</span>
              <span title={t("ui.round_win_rate")}>W {fmtPct(row.win_rate)}</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function SetupTables({ side, className = "", style }: { side: TSide | CTSide; className?: string; style?: CSSProperties }) {
  const [helpOpen, setHelpOpen] = useState(false);
  const phases = [
    { key: "15s", rows: side.setups_15s },
    { key: "30s", rows: side.setups_30s },
  ];

  return (
    <section className={`panel panel-span-2 ${className}`} style={style}>
      <div className="setup-head">
        <h3>{t("ui.setups_title")}</h3>
        <button
          type="button"
          className="help"
          aria-expanded={helpOpen}
          aria-label={t("ui.setup_shape_help")}
          title={t("ui.setup_shape_help")}
          onClick={() => setHelpOpen((open) => !open)}
        >
          ?
        </button>
      </div>
      {helpOpen ? <p className="help-text">{t("ui.setup_shape_help")}</p> : null}

      <table className="table setup-table">
        <thead>
          <tr>
            <th>{t("ui.setups_title")}</th>
            <th>#</th>
            <th>%</th>
            <th>{t("metric.win_rate")}</th>
          </tr>
        </thead>
        {phases.map((phase) => (
          <tbody key={phase.key}>
            <tr className="group-row">
              <td colSpan={4}>{phase.key}</td>
            </tr>
            {phase.rows.length === 0 ? (
              <tr>
                <td colSpan={4}>—</td>
              </tr>
            ) : (
              phase.rows.map((row) => (
                <tr key={`${phase.key}-${row.value}`}>
                  <td>
                    <span>{ctSetupLabel(row.value)}</span>
                  </td>
                  <td>{fmtInt(row.rounds)}</td>
                  <td>{fmtPct(row.share)}</td>
                  <td>{fmtPct(row.win_rate)}</td>
                </tr>
              ))
            )}
          </tbody>
        ))}
      </table>
    </section>
  );
}

function TSideView({ side }: { side: TSide }) {
  return (
    <>
      <CommonStats side={side} />
      <Stagger className="two-col">
        <SetupTables side={side} />

        <section className="panel">
          <h3>
            {t("ui.plant_sites_title")}{" "}
            <span className="muted" title={t("ui.plant_sites_title")}>
              ⌀ {fmtSeconds(side.avg_plant_t_s)}
            </span>
          </h3>
          <RankedBars rows={side.plant_sites} labelFor={siteLabel} />
        </section>

        <section className="panel">
          <h3>{t("ui.execute_title")}</h3>
          <RankedBars
            rows={side.execute_timing}
            labelFor={(value) => t(`execute_timing.${value}`)}
          />
        </section>

        <section className="panel">
          <h3>{t("ui.filter_lane")}</h3>
          <RankedBars
            rows={side.execute_lane}
            labelFor={(value) => t(`lane.${value}`)}
          />
        </section>
      </Stagger>
    </>
  );
}

function CTSideView({ side }: { side: CTSide }) {
  return (
    <>
      <CommonStats side={side} />
      <Stagger className="two-col">
        <SetupTables side={side} />

        <section className="panel">
          <h3>{t("ui.retake_title")}</h3>
          <div className="stat-row">
            <Stat
              label={t("metric.retake_win_rate")}
              value={fmtPct(side.retake_win_rate)}
              sub={`${fmtInt(side.retakes_won)} / ${fmtInt(side.plants_against)}`}
            />
            <Stat
              label={t("metric.stack_rate_15s")}
              value={fmtPct(side.stack_rate_15s)}
            />
          </div>
        </section>

        <section className="panel">
          <h3>{t("ui.plant_sites_title")}</h3>
          <RankedBars rows={side.plants_against_by_site} labelFor={siteLabel} />
        </section>
      </Stagger>
    </>
  );
}

function EconomyTable({ rows }: { rows: TeamProfile["economy"] }) {
  const byKey = new Map(
    rows.map((row) => [`${row.side}:${row.buy_type}`, row]),
  );

  return (
    <section className="panel economy-panel motion-reveal">
      <h3>{t("ui.economy_title")}</h3>
      <table className="table">
        <thead>
          <tr>
            <th>{t("ui.economy_title")}</th>
            <th>#</th>
            <th>{t("metric.win_rate")}</th>
          </tr>
        </thead>
        <tbody>
          {SIDE_ORDER.map((side) => (
            <Fragment key={side}>
              <tr className="group-row">
                <td colSpan={3}>{t(`side.${side}`)}</td>
              </tr>
              {BUY_TYPES.map((buy) => {
                const row = byKey.get(`${side}:${buy}`);
                return (
                  <tr key={buy}>
                    <td>{t(`buy.${buy}`)}</td>
                    <td>{row ? fmtInt(row.rounds) : "—"}</td>
                    <td>{fmtPct(row?.win_rate)}</td>
                  </tr>
                );
              })}
            </Fragment>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** The former team page's archive lives below the map's roster, closed by default. */
export default function TeamDetails({ team, tacticsContent, heatmapContent, detailsOpen, onDetailsToggle }: {
  team: TeamProfile; tacticsContent?: ReactNode; heatmapContent?: ReactNode; detailsOpen?: boolean; onDetailsToggle?: (open: boolean) => void;
}) {
  const lang = useLang();
  const [side, setSide] = useState<Side>("T");
  const [range, setRange] = useState<TimeRange>("all");
  const index = useData(getIndex, []);
  const [params] = useSearchParams();
  const matchId = params.get("match");
  useEffect(() => { if (matchId) setRange("all"); }, [matchId]);
  const matches = [...team.matches].sort(newestMatch);
  const visible = matches.filter((match) => inTimeRange(match, range, index.data?.data_through));
  const patterns = useData(() => getCTPatterns(team.map), [team.map]);
  const recipeCount = new Set((team.tactics?.T.recipes ?? []).map(r => r.value)).size;
  const clusterCount = patterns.data?.clusters.length ?? 0;
  const coverage = [recipeCount ? `收录 ${fmtInt(recipeCount)} 套进攻套路` : "", clusterCount ? `${fmtInt(clusterCount)} 类 CT 阵型` : ""].filter(Boolean).join(" · ");
  const basis = team.insights?.length ? t("tactics.summary_basis", { n: fmtInt(team.insights.length) }) : "";
  const wins = team.matches.filter((match) => match.score_for > match.score_against).length;
  const losses = team.matches.filter((match) => match.score_for < match.score_against).length;
  return <div className="hub-archive-cards">
    <details className="hub-details hub-archive-card hub-team-matches" open={params.has("match") ? true : undefined}>
      <summary><strong>{t("round4.archive_matches", { n: fmtInt(team.matches.length), w: fmtInt(wins), l: fmtInt(losses) })}</strong><small>{matches[0] ? `${matches[0].opponent ?? "—"} · ${fmtInt(matches[0].score_for)} : ${fmtInt(matches[0].score_against)}` : t("heatmap.no_data")}</small></summary>
      <p className="muted">{t("round3.round_bars_caption")}</p>
      <MatchTimeFilter value={range} onChange={setRange} />
      <ul className="match-list">{visible.length ? visible.map((match) => {
        const outcome = match.score_for > match.score_against ? "win" : match.score_for < match.score_against ? "loss" : "draw";
        return <li key={match.demo_id} className={`match is-${outcome}${params.get("match") === match.demo_id ? " is-selected" : ""}`} data-date={match.date ?? ""} id={`match-${match.demo_id}`} title={match.demo_id}>
          <span className="match-outcome" aria-label={t(`hub.${outcome}`)}>{outcome === "win" ? "W" : outcome === "loss" ? "L" : "D"}</span>
          <span className="match-opponent">{match.opponent ?? "—"}<small className="match-context"><MatchDate match={match} /></small></span>
          <span className="match-score">{fmtInt(match.score_for)} : {fmtInt(match.score_against)}</span>
          {match.winprob_available ? <MatchWinprob map={team.map} demoId={match.demo_id} teamSlug={team.slug} /> : null}
        </li>;
      }) : <li className="empty">{t("heatmap.no_data")}</li>}</ul>
    </details>
    <details className="hub-details hub-archive-card hub-team-basis" open={detailsOpen} onToggle={(event) => onDetailsToggle?.(event.currentTarget.open)}>
      <summary><strong>{t("round4.archive_details")}</strong><small>{coverage || [basis, ctSetupLabel(team.tactics?.CT.setups_20s[0]?.value)].filter(Boolean).join(" · ")}</small></summary>
      {tacticsContent}
      <ul className="team-insights-rest">{(team.insights ?? []).map((insight) => <li key={`${insight.side}:${insight.id}`}>{insight.text[lang]}</li>)}</ul>
      <Segmented className="tabs" role="tablist" aria-label={t("ui.nav_teams")}>{SIDE_ORDER.map((value) => <button
        key={value} type="button" role="tab" id={`tab-${value}`} aria-selected={side === value} aria-controls="team-side-panel" tabIndex={side === value ? 0 : -1}
        onClick={() => setSide(value)} onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === "Home" ? "T" : event.key === "End" ? "CT" : side === "T" ? "CT" : "T";
          setSide(next); document.getElementById(`tab-${next}`)?.focus();
        }}>{t(`side.${value}`)}</button>)}</Segmented>
      <div id="team-side-panel" role="tabpanel" aria-labelledby={`tab-${side}`} className={`side-panel side-${side.toLowerCase()}`}>
        {side === "T" ? <TSideView side={team.sides.T} /> : <CTSideView side={team.sides.CT} />}
      </div>
      <EconomyTable rows={team.economy} />
    </details>
    <details className="hub-details hub-archive-card hub-team-radar">
      <summary><strong>{t("round4.archive_heatmap")}</strong><small>{t("hub.sample", { matches: fmtInt(team.n_matches), maps: fmtInt(1) })} · T / CT</small></summary>
      <Link className="button button-ghost" to={`/heatmaps/${encodeURIComponent(team.slug)}?${new URLSearchParams({ map: team.map })}`}>{t("round4.archive_heatmap")} →</Link>
      {heatmapContent}
    </details>
  </div>;
}
