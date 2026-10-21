import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import LowSampleBanner from "../components/LowSampleBanner";
import Stat from "../components/Stat";
import { ErrorNotice, Loading } from "../components/Status";
import { getTeam, useData } from "../data";
import { fmtInt, fmtPct, fmtSeconds } from "../format";
import { t, useLang } from "../i18n";
import "../tactics.css";
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

function SetupTables({ side }: { side: TSide | CTSide }) {
  const [helpOpen, setHelpOpen] = useState(false);
  const phases = [
    { key: "15s", rows: side.setups_15s },
    { key: "30s", rows: side.setups_30s },
  ];

  return (
    <section className="panel panel-span-2">
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
                    <code>{row.value}</code>
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
      <div className="two-col">
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
      </div>
    </>
  );
}

function CTSideView({ side }: { side: CTSide }) {
  return (
    <>
      <CommonStats side={side} />
      <div className="two-col">
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
      </div>
    </>
  );
}

function EconomyTable({ rows }: { rows: TeamProfile["economy"] }) {
  const byKey = new Map(
    rows.map((row) => [`${row.side}:${row.buy_type}`, row]),
  );

  return (
    <section className="panel economy-panel">
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

export default function Team() {
  const lang = useLang();
  const { map = "", slug = "" } = useParams<{ map: string; slug: string }>();
  const { data: team, error, loading } = useData(
    () => getTeam(map, slug),
    [map, slug],
  );
  const [side, setSide] = useState<Side>("T");

  if (loading) return <Loading />;
  if (error || !team) {
    return <ErrorNotice error={error ?? new Error("Team profile is empty")} />;
  }

  return (
    <div className="team-page">
      <LowSampleBanner n_matches={team.n_matches} low_sample={team.low_sample} />

      <header className="page-head">
        <div>
          <p className="eyebrow">{map}</p>
          <h1>{team.team}</h1>
          <p className="muted">
            {t("ui.matches_title")} · {fmtInt(team.n_matches)}
          </p>
        </div>
        <Link
          to={`/heatmaps/${encodeURIComponent(slug)}?${new URLSearchParams({ map })}`}
          className="button button-ghost"
        >
          {t("heatmap.title")}
        </Link>
        <Link to={`/${map}/teams`} className="button button-ghost">
          {t("ui.nav_teams")}
        </Link>
      </header>

      {team.insights?.length ? (
        <section className="panel team-insights">
          <h3>{t("tactics.insights")}</h3>
          <ul className="team-insights-top">
            {team.insights.slice(0, 3).map((insight) => (
              <li key={`${insight.side}:${insight.id}`}>{insight.text[lang]}</li>
            ))}
          </ul>
          {team.insights.length > 3 && <details>
            <summary>{t("tactics.expand_insights", { n: fmtInt(team.insights.length - 3) })}</summary>
            <ul className="team-insights-rest">{team.insights.slice(3).map((insight) => (
              <li key={`${insight.side}:${insight.id}`}>{insight.text[lang]}</li>
            ))}</ul>
          </details>}
        </section>
      ) : null}

      <section className="panel">
        <h3>{t("ui.matches_title")}</h3>
        <ul className="match-list">
          {team.matches.length === 0 ? (
            <li className="empty">—</li>
          ) : (
            team.matches.map((match) => {
              const outcome =
                match.score_for > match.score_against
                  ? " is-win"
                  : match.score_for < match.score_against
                    ? " is-loss"
                    : "";
              return (
                <li
                  key={match.demo_id}
                  className={`match${outcome}`}
                  title={match.demo_id}
                >
                  <span className="match-opponent">{match.opponent ?? "—"}</span>
                  <span className="match-score">
                    {match.score_for} : {match.score_against}
                  </span>
                </li>
              );
            })
          )}
        </ul>
      </section>

      <div className="tabs" role="tablist" aria-label={t("ui.nav_teams")}>
        {SIDE_ORDER.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            id={`tab-${value}`}
            aria-selected={side === value}
            aria-controls="team-side-panel"
            onClick={() => setSide(value)}
          >
            {t(`side.${value}`)}
          </button>
        ))}
      </div>

      <div
        id="team-side-panel"
        role="tabpanel"
        aria-labelledby={`tab-${side}`}
        className={`side-panel side-${side.toLowerCase()}`}
      >
        {side === "T" ? (
          <TSideView side={team.sides.T} />
        ) : (
          <CTSideView side={team.sides.CT} />
        )}
      </div>

      <EconomyTable rows={team.economy} />
    </div>
  );
}
