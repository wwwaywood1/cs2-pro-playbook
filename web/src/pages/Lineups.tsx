import PracticeCopy from "../components/PracticeCopy";
import { copyText, practiceBind } from "../practice";
import Num from "../components/Num";
import Segmented from "../components/Segmented";
import { Reveal, Stagger } from "../components/Motion";
import { PageContext, PageSurface, MetricStrip } from "../components/Page";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import GrenadeIcon from "../components/GrenadeIcon";
import { MapLinkHint, useMapLink } from "../mapLink";
import Radar from "../components/Radar";
import { ErrorNotice, Loading } from "../components/Status";
import { getLineups, getMeta, useData } from "../data";
import { fmtInt, fmtPct, fmtNum } from "../format";
import { motionScrollBehavior } from "../motion";
import { calloutLabel, t, useLang } from "../i18n";
import type { GrenadeType, Lane, Lineup, Side, Technique } from "../types";

const ALL_TYPES: GrenadeType[] = ["smoke", "flashbang", "molotov", "he"];
const LANE_OPTIONS: Lane[] = ["A", "MID", "B"];
const TECHNIQUES: Technique[] = ["jump", "run", "crouch", "walk", "stand"];
const SIDES: Side[] = ["T", "CT"];


export default function Lineups() {
  useLang();
  const { map = "" } = useParams<{ map: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedId = searchParams.get("id");
  const requestKey = `${map}:${requestedId ?? ""}`;
  const { data: meta } = useData(() => getMeta(map), [map]);
  const { data: lineupData, error, loading } = useData(
    async () => ({ map, rows: await getLineups(map) }), [map],
  );
  const lineups = lineupData?.map === map ? lineupData.rows : null;

  const urlLanding = searchParams.get("landing");
  // Expand/filter immediately; HashRouter commits the shareable URL in a transition.
  // Track the last URL separately so unrelated renders cannot undo a local pick,
  // while Back/Forward and map changes still restore the requested landing filter.
  const [landingPick, setLandingPick] = useState({ map, url: urlLanding, value: urlLanding });
  let landing = landingPick.value;
  if (landingPick.map !== map || landingPick.url !== urlLanding) {
    landing = urlLanding;
    setLandingPick({ map, url: urlLanding, value: urlLanding });
  }
  const clusterIds = useMemo(() => landing ? new Set(landing.split(",")) : null, [landing]);
  const [side, setSide] = useState<Side | "ALL">("ALL");
  const [types, setTypes] = useState<GrenadeType[]>(ALL_TYPES);
  const [lane, setLane] = useState<Lane | "ALL">("ALL");
  const [minThrows, setMinThrows] = useState(0);
  const [technique, setTechnique] = useState<Technique | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { bind } = useMapLink();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const cardRefs = useRef(new Map<string, HTMLElement>());
  const copyTimer = useRef<number | null>(null);
  const appliedRequest = useRef<string | null>(null);
  const scrolledRequest = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
    };
  }, []);

  const candidates = useMemo(() => {
    const rows = (lineups ?? []).filter(
      (lineup) =>
        (side === "ALL" || lineup.side === side) &&
        types.includes(lineup.type) &&
        (lane === "ALL" || lineup.land_lane === lane) &&
        lineup.n_throws >= minThrows &&
        (technique === "ALL" || lineup.technique === technique),
    );
    return rows.sort(
      (a, b) => b.n_throws - a.n_throws || a.id.localeCompare(b.id),
    );
  }, [lineups, side, types, lane, minThrows, technique]);

  const filtered = useMemo(() => candidates.filter((lineup) => !clusterIds || clusterIds.has(lineup.id)), [candidates, clusterIds]);
  const pickCluster = (ids: string[] | null) => {
    setLandingPick({ map, url: urlLanding, value: ids?.length ? ids.join(",") : null });
    if (ids?.length) setSelectedId(ids[0]);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (ids?.length) { next.set("landing", ids.join(",")); next.set("id", ids[0]); }
      else next.delete("landing");
      return next;
    }, { replace: true });
  };
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && clusterIds && !document.querySelector("dialog[open]")) { event.preventDefault(); pickCluster(null); }
    };
    document.addEventListener("keydown", escape);
    return () => document.removeEventListener("keydown", escape);
  }, [clusterIds]);

  useEffect(() => {
    if (!lineups) return;
    if (appliedRequest.current !== requestKey) {
      appliedRequest.current = requestKey;
      scrolledRequest.current = null;
      const target = lineups.find((lineup) => lineup.id === requestedId);
      if (target) {
        if (!filtered.some((lineup) => lineup.id === target.id)) {
          pickCluster(null);
          setSide("ALL");
          setTypes(ALL_TYPES);
          setMinThrows(1);
          setLane("ALL");
          setTechnique("ALL");
        }
        setSelectedId(target.id);
        return;
      }
    }
    if (filtered.length === 0) {
      if (selectedId !== null) setSelectedId(null);
      return;
    }
    if (!selectedId || !filtered.some((lineup) => lineup.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [lineups, requestKey, requestedId, filtered, selectedId]);

  useEffect(() => {
    if (!requestedId || selectedId !== requestedId ||
        scrolledRequest.current === requestKey) return;
    const card = cardRefs.current.get(requestedId);
    if (!card) return;
    const frame = window.requestAnimationFrame(() => {
      card.scrollIntoView({ behavior: motionScrollBehavior(), block: "nearest" });
      scrolledRequest.current = requestKey;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [requestKey, requestedId, selectedId, filtered]);

  const toggleType = (type: GrenadeType) => {
    setTypes((current) => {
      if (!current.includes(type)) return [...current, type];
      return current.length === 1 ? current : current.filter((item) => item !== type);
    });
  };

  const resetFilters = () => {
    pickCluster(null);
    setSide("ALL");
    setTypes(ALL_TYPES);
    setLane("ALL");
    setMinThrows(0);
    setTechnique("ALL");
  };

  const selectFromRadar = (id: string) => {
    setSelectedId(id);
    setSearchParams((current) => { const next = new URLSearchParams(current); next.set("id", id); return next; }, { replace: true });
    const card = cardRefs.current.get(id);
    if (card) card.scrollIntoView({ behavior: motionScrollBehavior(), block: "nearest" });
  };

  const handleCopy = async (lineup: Lineup) => {
    const fallback = document.getElementById(`practice-${lineup.id}`);
    const copied = await copyText(lineup.practice_cmd, fallback);
    if (!copied) return;
    setCopiedId(lineup.id);
    if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
    copyTimer.current = window.setTimeout(() => {
      setCopiedId((current) => (current === lineup.id ? null : current));
    }, 1500);
  };

  const title = meta?.display_name ?? map;

  return (
    <PageSurface className="lineups-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">{map}</p>
          <h1>
            {title} · {t("ui.nav_lineups")}
          </h1>
          <PageContext>{t("site.lineups_context")}</PageContext>
        </div>
        {lineups ? <MetricStrip items={[{ label: t("site.results"), value: filtered.length }, { label: t("ui.nav_lineups"), value: lineups.length }]} /> : null}
      </header>
      <MapLinkHint />
      <section className="filters">
        <div className="filter-group" role="group" aria-label={t("ui.filter_side")}>
          <span className="filter-label">{t("ui.filter_side")}</span>
          <Segmented className="segmented">
            <button
              type="button"
              className={side === "ALL" ? "is-active" : ""}
              aria-pressed={side === "ALL"}
              onClick={() => setSide("ALL")}
            >
              {t("ui.filter_all")}
            </button>
            {SIDES.map((value) => (
              <button
                key={value}
                type="button"
                className={side === value ? "is-active" : ""}
                data-side={value}
                aria-pressed={side === value}
                onClick={() => setSide(value)}
              >
                {t(`side.${value}`)}
              </button>
            ))}
          </Segmented>
        </div>

        <div className="filter-group" role="group" aria-label={t("ui.filter_type")}>
          <span className="filter-label">{t("ui.filter_type")}</span>
          <div className="chips">
            {ALL_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                className={`chip chip-${type}`}
                aria-pressed={types.includes(type)}
                onClick={() => toggleType(type)}
              >
                <GrenadeIcon type={type} />{t(`grenade.${type}`)}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-group" role="group" aria-label={t("ui.filter_lane")}>
          <span className="filter-label">{t("ui.filter_lane")}</span>
          <Segmented className="segmented">
            <button
              type="button"
              className={lane === "ALL" ? "is-active" : ""}
              aria-pressed={lane === "ALL"}
              onClick={() => setLane("ALL")}
            >
              {t("ui.filter_all")}
            </button>
            {LANE_OPTIONS.map((value) => (
              <button
                key={value}
                type="button"
                className={lane === value ? "is-active" : ""}
                aria-pressed={lane === value}
                onClick={() => setLane(value)}
              >
                {t(`lane.${value}`)}
              </button>
            ))}
          </Segmented>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-technique">
            {t("ui.filter_technique")}
          </label>
          <select
            id="filter-technique"
            value={technique}
            onChange={(event) =>
              setTechnique(event.target.value as Technique | "ALL")
            }
          >
            <option value="ALL">{t("ui.filter_all")}</option>
            {TECHNIQUES.map((value) => (
              <option key={value} value={value}>
                {t(`round2.throw_${value}`)}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group" role="group" aria-label={t("ui.filter_min_throws")}>
          <span className="filter-label">{t("ui.filter_min_throws")}</span>
          <Segmented className="segmented" id="filter-tiers">
            {([0, 10, 50] as const).map((minimum, index) => <button key={minimum} type="button" aria-pressed={minThrows === minimum} className={minThrows === minimum ? "is-active" : ""} onClick={() => setMinThrows(minimum)}>{t(`round2.${["tier_all", "tier_common", "tier_must"][index]}`)}</button>)}
          </Segmented>
        </div>

        <div className="filter-group filter-actions">
          <button type="button" className="button button-ghost" onClick={resetFilters}>
            ↺ {t("ui.filter_all")}
          </button>
        </div>
      </section>

      {loading ? (
        <Loading />
      ) : error ? (
        <ErrorNotice error={error} />
      ) : (
        <div className="lineups-layout">
          <aside className="radar-panel">
            <Reveal className="motion-radar"><Radar
              map={map}
              lineups={candidates}
              pickedIds={clusterIds}
              onPick={pickCluster}
              selectedId={selectedId}
              onSelect={selectFromRadar}
            /></Reveal>
          </aside>

          <Stagger className="lineup-list">
            {filtered.length === 0 ? (
              <div className="empty">—</div>
            ) : (
              filtered.map((lineup) => {
                const selected = lineup.id === selectedId;
                const copied = lineup.id === copiedId;
                return (
                  <article
                    key={lineup.id}
                    ref={(node) => {
                      if (node) cardRefs.current.set(lineup.id, node);
                      else cardRefs.current.delete(lineup.id);
                    }}
                    className={`lineup-card${selected ? " is-selected" : ""}`} data-motion-tilt={selected || undefined}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) {
                        event.preventDefault();
                        setSelectedId(lineup.id);
                      }
                    }}
                    {...bind(`lineup:${lineup.id}`)}
                    onClick={() => setSelectedId(lineup.id)}
                  >
                    <div className="lineup-top">
                      <span className={`badge badge-${lineup.type}`}>
                        <GrenadeIcon type={lineup.type} />{t(`grenade.${lineup.type}`)}
                      </span>
                      <span className={`chip chip-side-${lineup.side.toLowerCase()}`}>
                        {t(`side.${lineup.side}`)}
                      </span>
                      <span className="chip">{t(`round2.throw_${lineup.technique}`)}</span>
                    </div>

                    <h3 className="lineup-route">
                      <span>{calloutLabel(map, lineup.throw_place)}</span>
                      <span className="route-arrow" aria-hidden="true">
                        →
                      </span>
                      <span>{calloutLabel(map, lineup.land_place)}</span>
                    </h3>

                    <p className="lineup-meta">
                      {t("ui.times_thrown", {
                        n: fmtInt(lineup.n_throws),
                        m: fmtInt(lineup.n_matches),
                      })}
                    </p>

                    <dl className="lineup-stats">
                      <div>
                        <dt>{t("ui.throwers")}</dt>
                        <dd>
                          {lineup.throwers.length > 0
                            ? lineup.throwers.join(", ")
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>{t("ui.round_win_rate")}</dt>
                        <dd><Num value={fmtPct(lineup.round_win_rate)} /></dd>
                      </div>
                      <div>
                        <dt tabIndex={0} title={t("round2.pop_tip")}>{t("round2.pop_tip")} ⓘ</dt>
                        <dd>{lineup.median_pop_t_s == null ? "—" : t("round2.pop_time", { s: fmtNum(lineup.median_pop_t_s, 1) })}</dd>
                      </div>
                    </dl>

                    <div className="practice-row">
                      <button
                        type="button"
                        className="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          void handleCopy(lineup);
                        }}
                      >
                        {copied ? t("ui.copied") : t("ui.copy_cmd")}
                      </button>
                      <PracticeCopy command={practiceBind(lineup)} label={t("round5.bind_copy")} tip={t("round5.bind_tip")} />
                      <span className="hint">{t("ui.practice_hint")}</span>
                    </div>

                    <code id={`practice-${lineup.id}`} className="practice-cmd">
                      {lineup.practice_cmd}
                    </code>
                  </article>
                );
              })
            )}
          </Stagger>
        </div>
      )}
    </PageSurface>
  );
}
