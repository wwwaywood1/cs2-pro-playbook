import { useMapLink } from "../mapLink";
import GrenadeIcon, { GrenadeGlyph } from "./GrenadeIcon";
import { useEffect, useMemo, useState } from "react";
import { calloutLabel, t } from "../i18n";
import type { GrenadeType, Lineup } from "../types";

const TYPES: GrenadeType[] = ["smoke", "flashbang", "molotov", "he"];

interface RadarProps {
  map: string;
  lineups: Lineup[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export default function Radar({ map, lineups, selectedId, onSelect }: RadarProps) {
  const { activeId: linkedId, bind } = useMapLink();
  const hoveredId = linkedId?.startsWith("lineup:") ? linkedId.slice(7) : null;
  const [imageOk, setImageOk] = useState(true);
  const activeId = lineups.some((lineup) => lineup.id === hoveredId) ? hoveredId : selectedId;
  const [selectedPlace, setSelectedPlace] = useState<string | null>(null);
  const placeKey = (lineup: Lineup) => lineup.land_place || lineup.land_region || lineup.land_lane || "";
  const clusters = useMemo(() => {
    const places = new Map<string, Lineup[]>();
    for (const lineup of lineups) {
      if (!Number.isFinite(lineup.land.radar_x) || !Number.isFinite(lineup.land.radar_y)) continue;
      const key = placeKey(lineup);
      const rows = places.get(key) ?? [];
      rows.push(lineup); places.set(key, rows);
    }
    const median = (values: number[]) => {
      const sorted = [...values].sort((a, b) => a - b);
      const middle = Math.floor(sorted.length / 2);
      return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    };
    const cells = [...places.entries()].map(([key, rows]) => ({
      key, rows, x: median(rows.map((row) => row.land.radar_x)), y: median(rows.map((row) => row.land.radar_y)),
    }));
    // Merge colliding count bubbles; every filtered lineup belongs to exactly one bubble.
    const radius = (count: number) => Math.min(52, 22 + Math.sqrt(count) * 3);
    let merged = true;
    while (merged) {
      merged = false;
      outer: for (let i = 0; i < cells.length; i++) for (let j = i + 1; j < cells.length; j++) {
        const a = cells[i], b = cells[j];
        if (Math.hypot(a.x - b.x, a.y - b.y) >= radius(a.rows.length) + radius(b.rows.length) + 12) continue;
        const count = a.rows.length + b.rows.length;
        a.x = (a.x * a.rows.length + b.x * b.rows.length) / count;
        a.y = (a.y * a.rows.length + b.y * b.rows.length) / count;
        a.rows = [...a.rows, ...b.rows];
        a.key += `|${b.key}`;
        cells.splice(j, 1);
        merged = true;
        break outer;
      }
    }
    return cells.map((cell) => ({ ...cell, weight: cell.rows.length, radius: radius(cell.rows.length),
      lineup: [...cell.rows].sort((a, b) => b.n_throws - a.n_throws || a.id.localeCompare(b.id))[0],
    }));
  }, [lineups]);

  useEffect(() => {
    setImageOk(true);
  }, [map]);
  useEffect(() => { setSelectedPlace(null); }, [map, lineups]);

  return (
    <div className="radar-panel-inner">
      <svg className="radar" viewBox="0 0 1024 1024" role="group" aria-label={map}>
        <rect className="radar-bg" x="0" y="0" width="1024" height="1024" />
        {imageOk ? (
          <image
            href={`${import.meta.env.BASE_URL}radars/${map}.png`}
            x="0"
            y="0"
            width="1024"
            height="1024"
            preserveAspectRatio="xMidYMid meet"
            onError={() => setImageOk(false)}
          />
        ) : null}

        <defs>
          {TYPES.map((type) => (
            <marker
              key={type}
              id={`arrowhead-${type}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className={`arrowhead arrowhead-${type}`} />
            </marker>
          ))}
        </defs>

        {clusters.filter((cell) => cell.key !== selectedPlace).map((cell) => {
          const label = `${[...new Set(cell.rows.map((row) => calloutLabel(map, row.land_place)))].join(" / ")} · ${t("round4.cluster_count", { n: cell.weight })}`;
          const expand = () => { setSelectedPlace(cell.key); onSelect(cell.lineup.id); };
          return <g key={cell.key} className="landing-cluster" role="button" tabIndex={0}
            {...bind(`lineup:${cell.rows.find((row) => row.id === hoveredId)?.id ?? cell.lineup.id}`)}
            aria-label={label} onClick={expand} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); expand(); } }}>
            <circle className="map-link-ring" cx={cell.x} cy={cell.y} r={cell.radius + 6} />
            <title>{label}</title>
            <circle cx={cell.x} cy={cell.y} r={cell.radius} />
            <text x={cell.x} y={cell.y + 7} textAnchor="middle" style={{ fontSize: 22, fontWeight: 800, fill: "#f5f8ff" }}>{cell.weight}</text>
          </g>;
        })}
        {lineups.filter((lineup) => clusters.find((cell) => cell.key === selectedPlace)?.rows.some((row) => row.id === lineup.id) || lineup.id === activeId).map((lineup) => {
          const selected = lineup.id === activeId;
          const dimmed = activeId != null && !selected;
          const x = lineup.throw.radar_x, y = lineup.throw.radar_y;
          const dx = lineup.land.radar_x - x, dy = lineup.land.radar_y - y;
          const arc = `M ${x} ${y} Q ${x + dx / 2 - dy * .16} ${y + dy / 2 + dx * .16} ${x + dx} ${y + dy}`;
          const className = [
            "arrow-group",
            `arrow-${lineup.type}`,
            selected ? "is-selected" : "",
            dimmed ? "is-dimmed" : "",
          ]
            .filter(Boolean)
            .join(" ");

          return (
            <g
              key={lineup.id}
              {...bind(`lineup:${lineup.id}`)}
              className={className}
              role="button"
              tabIndex={0}
              aria-pressed={selected}
              aria-label={`${t(`grenade.${lineup.type}`)} · ${calloutLabel(map, lineup.throw_place)} → ${calloutLabel(map, lineup.land_place)}`}
              onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(lineup.id); } }}
              onClick={() => onSelect(lineup.id)}
            >
              <title>{`${calloutLabel(map, lineup.throw_place)} → ${calloutLabel(
                map,
                lineup.land_place,
              )}`}</title>
              <circle className="map-link-ring" cx={lineup.land.radar_x} cy={lineup.land.radar_y} r="30" />
              <path className="arrow-hit" d={arc} />
              <path className="arrow-line" d={arc} pathLength={1} markerEnd={`url(#arrowhead-${lineup.type})`} />
              <circle className="land-dot" cx={lineup.land.radar_x} cy={lineup.land.radar_y} r={selected ? 17 : 9} />
              <circle
                className="throw-dot"
                cx={lineup.throw.radar_x}
                cy={lineup.throw.radar_y}
                r={selected ? 9 : 5.5}
              />
              {selected && Number.isFinite(lineup.throw.yaw) ? <g className="throw-direction">
                <title>{t("round2.throw_dir_tip")}</title>
                <line x1={x} y1={y} x2={x + Math.cos(lineup.throw.yaw * Math.PI / 180) * 56} y2={y - Math.sin(lineup.throw.yaw * Math.PI / 180) * 56} markerEnd={`url(#arrowhead-${lineup.type})`} />
              </g> : null}
              <svg x={lineup.land.radar_x - 24} y={lineup.land.radar_y - 24} width="48" height="48" viewBox="0 0 32 32" aria-hidden="true">
                <GrenadeGlyph type={lineup.type} />
              </svg>
            </g>
          );
        })}
      </svg>

      <p className="radar-hint">{t("round2.throw_dir_tip")}</p>
      {selectedPlace !== null ? <button type="button" className="button button-ghost radar-reset" onClick={() => setSelectedPlace(null)}>{t("round2.tier_all")}</button> : null}
      <div className="radar-legend">
        {TYPES.map((type) => (
          <span key={type} className="grenade-label">
            <GrenadeIcon type={type} />{t(`grenade.${type}`)}
          </span>
        ))}
      </div>
    </div>
  );
}
