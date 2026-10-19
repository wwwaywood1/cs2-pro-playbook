import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import Stat from "../components/Stat";
import { ErrorNotice, Loading } from "../components/Status";
import { getMeta, getPlayers, useData } from "../data";
import { fmtInt, fmtMetric, fmtNum, fmtPct } from "../format";
import { t, useLang } from "../i18n";
import type { PlayerProfile, RoleHint, Share } from "../types";

function hintTooltip(hint: RoleHint): string {
  const basis = `${t(`metric.${hint.metric}`)}: ${fmtMetric(hint.metric, hint.value)}`;
  const median =
    hint.team_median !== undefined
      ? ` (⌀ ${fmtMetric(hint.metric, hint.team_median)})`
      : "";
  return `${t(`role_desc.${hint.role}`)} · ${basis}${median}`;
}

function Lanes({ shares }: { shares: Share[] }) {
  const top = shares.slice(0, 2);
  if (top.length === 0) return <span className="muted">—</span>;
  return (
    <span className="lane-row">
      {top.map((item) => (
        <span key={item.value} className="lane-chip">
          {t(`lane.${item.value}`)}
          <span className="muted">{fmtPct(item.share)}</span>
        </span>
      ))}
    </span>
  );
}

export default function Players() {
  useLang();
  const { map = "" } = useParams<{ map: string }>();
  const { data: meta } = useData(() => getMeta(map), [map]);
  const { data: players, error, loading } = useData(() => getPlayers(map), [map]);

  const groups = useMemo(() => {
    const byTeam = new Map<string, PlayerProfile[]>();
    for (const player of players ?? []) {
      const list = byTeam.get(player.team);
      if (list) list.push(player);
      else byTeam.set(player.team, [player]);
    }
    return [...byTeam.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([team, list]) => ({
        team,
        players: [...list].sort(
          (a, b) =>
            (b.kpr ?? -1) - (a.kpr ?? -1) || a.name.localeCompare(b.name),
        ),
      }));
  }, [players]);

  const title = meta?.display_name ?? map;

  return (
    <div className="players-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">{map}</p>
          <h1>
            {title} · {t("ui.nav_players")}
          </h1>
        </div>
        {players ? <p className="result-count">{players.length}</p> : null}
      </header>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorNotice error={error} />
      ) : groups.length === 0 ? (
        <div className="empty">—</div>
      ) : (
        groups.map((group) => (
          <section key={group.team} className="team-block">
            <h2>{group.team}</h2>
            <div className="player-grid">
              {group.players.map((player) => (
                <article key={player.steamid} className="player-card">
                  <div className="player-head">
                    <h3>{player.name}</h3>
                    <span className="muted" title={t("ui.matches_title")}>
                      n={fmtInt(player.n_matches)}
                    </span>
                  </div>

                  <div className="stat-grid">
                    <Stat label={t("metric.kpr")} value={fmtNum(player.kpr, 2)} />
                    <Stat
                      label={t("metric.opening_success")}
                      value={fmtPct(player.opening_success)}
                    />
                    <Stat
                      label={t("metric.awp_share")}
                      value={fmtPct(player.awp_share)}
                    />
                    <Stat
                      label={t("metric.util_pr")}
                      value={fmtNum(player.util_pr, 2)}
                    />
                  </div>

                  <div className="player-roles">
                    <span className="section-label">{t("ui.roles_title")}</span>
                    {player.role_hints.length === 0 ? (
                      <span className="muted">—</span>
                    ) : (
                      player.role_hints.map((hint) => (
                        <span
                          key={`${hint.role}:${hint.metric}`}
                          className="chip role-chip"
                          title={hintTooltip(hint)}
                          tabIndex={0}
                        >
                          {t(`role.${hint.role}`)}
                        </span>
                      ))
                    )}
                  </div>

                  <div className="player-lanes">
                    <div className="player-lane">
                      <span>{t("side.T")}</span>
                      <Lanes shares={player.T.lanes_15s} />
                    </div>
                    <div className="player-lane">
                      <span>{t("side.CT")}</span>
                      <Lanes shares={player.CT.lanes_15s} />
                    </div>
                  </div>
                  <Link
                    to={`/heatmaps/${encodeURIComponent(player.team.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""))}?${new URLSearchParams({ map, players: player.steamid })}`}
                    className="button button-ghost"
                  >
                    {t("heatmap.title")}
                  </Link>
                </article>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
