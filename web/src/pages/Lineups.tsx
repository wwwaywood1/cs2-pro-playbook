import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import Radar from "../components/Radar";
import { ErrorNotice, Loading } from "../components/Status";
import { getLineups, getMeta, useData } from "../data";
import { fmtPct, fmtSeconds } from "../format";
import { calloutLabel, t, useLang } from "../i18n";
import type { GrenadeType, Lane, Lineup, Side, Technique } from "../types";

const ALL_TYPES: GrenadeType[] = ["smoke", "flashbang", "molotov", "he"];
const LANE_OPTIONS: Lane[] = ["A", "MID", "B"];
const TECHNIQUES: Technique[] = ["jump", "run", "crouch", "walk", "stand"];
const SIDES: Side[] = ["T", "CT"];

async function copyText(text: string, fallback: HTMLElement | null): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Permission denied or an insecure context: try the legacy path.
  }

  let area: HTMLTextAreaElement | null = null;
  try {
    area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "0";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, text.length);
    const copied = document.execCommand("copy");
    if (copied) return true;
  } catch {
    // Fall through to selecting the visible command for manual copying.
  } finally {
    area?.remove();
  }

  if (fallback) {
    const selection = window.getSelection();
    if (selection) {
      const range = document.createRange();
      range.selectNodeContents(fallback);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  }
  return false;
}

export default function Lineups() {
  useLang();
  const { map = "" } = useParams<{ map: string }>();
  const { data: meta } = useData(() => getMeta(map), [map]);
  const { data: lineups, error, loading } = useData(() => getLineups(map), [map]);

  const [side, setSide] = useState<Side | "ALL">("ALL");
  const [types, setTypes] = useState<GrenadeType[]>(ALL_TYPES);
  const [lane, setLane] = useState<Lane | "ALL">("ALL");
  const [minThrows, setMinThrows] = useState(2);
  const [technique, setTechnique] = useState<Technique | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const cardRefs = useRef(new Map<string, HTMLElement>());
  const copyTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (copyTimer.current !== null) window.clearTimeout(copyTimer.current);
    };
  }, []);

  const filtered = useMemo(() => {
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

  useEffect(() => {
    if (filtered.length === 0) {
      if (selectedId !== null) setSelectedId(null);
      return;
    }
    if (!selectedId || !filtered.some((lineup) => lineup.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  const toggleType = (type: GrenadeType) => {
    setTypes((current) => {
      if (!current.includes(type)) return [...current, type];
      return current.length === 1 ? current : current.filter((item) => item !== type);
    });
  };

  const resetFilters = () => {
    setSide("ALL");
    setTypes(ALL_TYPES);
    setLane("ALL");
    setMinThrows(2);
    setTechnique("ALL");
  };

  const updateMinThrows = (raw: string) => {
    const parsed = Number.parseInt(raw, 10);
    setMinThrows(Number.isFinite(parsed) ? Math.min(9999, Math.max(0, parsed)) : 0);
  };

  const selectFromRadar = (id: string) => {
    setSelectedId(id);
    const card = cardRefs.current.get(id);
    if (card) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
    <div className="lineups-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">{map}</p>
          <h1>
            {title} · {t("ui.nav_lineups")}
          </h1>
        </div>
        <p className="result-count">
          {loading ? "…" : `${filtered.length} / ${lineups?.length ?? 0}`}
        </p>
      </header>

      <section className="filters">
        <div className="filter-group" role="group" aria-label={t("ui.filter_side")}>
          <span className="filter-label">{t("ui.filter_side")}</span>
          <div className="segmented">
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
                aria-pressed={side === value}
                onClick={() => setSide(value)}
              >
                {t(`side.${value}`)}
              </button>
            ))}
          </div>
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
                {t(`grenade.${type}`)}
              </button>
            ))}
          </div>
        </div>

        <div className="filter-group" role="group" aria-label={t("ui.filter_lane")}>
          <span className="filter-label">{t("ui.filter_lane")}</span>
          <div className="segmented">
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
          </div>
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
                {t(`technique.${value}`)}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label" htmlFor="filter-min-throws">
            {t("ui.filter_min_throws")}
          </label>
          <input
            id="filter-min-throws"
            type="number"
            min={0}
            max={9999}
            inputMode="numeric"
            value={minThrows}
            onChange={(event) => updateMinThrows(event.target.value)}
          />
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
            <Radar
              map={map}
              lineups={filtered}
              selectedId={selectedId}
              onSelect={selectFromRadar}
            />
          </aside>

          <div className="lineup-list">
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
                    className={`lineup-card${selected ? " is-selected" : ""}`}
                    onClick={() => setSelectedId(lineup.id)}
                  >
                    <div className="lineup-top">
                      <span className={`badge badge-${lineup.type}`}>
                        {t(`grenade.${lineup.type}`)}
                      </span>
                      <span className={`chip chip-side-${lineup.side.toLowerCase()}`}>
                        {t(`side.${lineup.side}`)}
                      </span>
                      <span className="chip">{t(`technique.${lineup.technique}`)}</span>
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
                        n: lineup.n_throws,
                        m: lineup.n_matches,
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
                        <dd>{fmtPct(lineup.round_win_rate)}</dd>
                      </div>
                      <div>
                        <dt>{t("metric.median_pop_t_s")}</dt>
                        <dd>{fmtSeconds(lineup.median_pop_t_s)}</dd>
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
                      <span className="hint">{t("ui.practice_hint")}</span>
                    </div>

                    <code id={`practice-${lineup.id}`} className="practice-cmd">
                      {lineup.practice_cmd}
                    </code>
                  </article>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
