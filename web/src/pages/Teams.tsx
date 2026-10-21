import { Stagger } from "../components/Motion";
import { PageContext, PageSurface, MetricStrip } from "../components/Page";
import { Link, useParams } from "react-router-dom";
import { ErrorNotice, Loading } from "../components/Status";
import { getMeta, getTeams, useData } from "../data";
import { fmtInt, fmtPct } from "../format";
import { t, useLang } from "../i18n";

export default function Teams() {
  useLang();
  const { map = "" } = useParams<{ map: string }>();
  const { data: meta } = useData(() => getMeta(map), [map]);
  const { data: teams, error, loading } = useData(() => getTeams(map), [map]);
  const title = meta?.display_name ?? map;

  return (
    <PageSurface className="teams-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">{map}</p>
          <h1>
            {title} · {t("ui.nav_teams")}
          </h1>
          <PageContext>{t("site.teams_context")}</PageContext>
        </div>
        {teams ? <p className="result-count">{teams.length}</p> : null}
      </header>
      {teams ? <MetricStrip items={[{ label: t("ui.nav_teams"), value: teams.length }, { label: t("site.reliable_teams"), value: teams.filter((team) => !team.low_sample).length }]} /> : null}

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorNotice error={error} />
      ) : !teams || teams.length === 0 ? (
        <div className="empty">—</div>
      ) : (
        <Stagger className="team-grid">
          {teams.map((team) => {
            const warning = t("ui.low_sample_warning", { n: team.n_matches });
            return (
              <Link
                key={team.slug}
                to={`/${map}/teams/${team.slug}`}
                className="team-card" data-motion-tilt
              >
                <div className="team-card-head">
                  <h2>{team.team}</h2>
                  {team.low_sample ? (
                    <span
                      className="tag-warn"
                      title={warning}
                      aria-label={warning}
                    >
                      !
                    </span>
                  ) : null}
                </div>

                <dl>
                  <div>
                    <dt>
                      {t("side.T")} {t("metric.win_rate")}
                    </dt>
                    <dd>{fmtPct(team.win_rate_T)}</dd>
                  </div>
                  <div>
                    <dt>
                      {t("side.CT")} {t("metric.win_rate")}
                    </dt>
                    <dd>{fmtPct(team.win_rate_CT)}</dd>
                  </div>
                  <div>
                    <dt>{t("ui.matches_title")}</dt>
                    <dd>{fmtInt(team.n_matches)}</dd>
                  </div>
                </dl>
              </Link>
            );
          })}
        </Stagger>
      )}
    </PageSurface>
  );
}
