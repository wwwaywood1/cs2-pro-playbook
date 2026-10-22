import GrenadeIcon, { GrenadeGlyph } from "./GrenadeIcon";
import { useEffect, useMemo, useState } from "react";
import { calloutLabel, t } from "../i18n";
import type { GrenadeType, Lineup } from "../types";

const TYPES: GrenadeType[] = ["smoke", "flashbang", "molotov", "he"];

interface RadarProps {
  map: string;
  lineups: Lineup[];
  selectedId: string | null;
  hoveredId?: string | null;
  onSelect: (id: string) => void;
}

export default function Radar({ map, lineups, selectedId, hoveredId, onSelect }: RadarProps) {
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
    return [...places.entries()].map(([key, rows]) => ({
      key, rows, x: median(rows.map((row) => row.land.radar_x)), y: median(rows.map((row) => row.land.radar_y)),
      weight: rows.reduce((sum, row) => sum + row.n_throws, 0),
      lineup: [...rows].sort((a, b) => b.n_throws - a.n_throws || a.id.localeCompare(b.id))[0],
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
          const label = `${calloutLabel(map, cell.lineup.land_place)} · ${cell.weight}`;
          const expand = () => { setSelectedPlace(cell.key); onSelect(cell.lineup.id); };
          return <g key={cell.key} className="landing-cluster" role="button" tabIndex={0}
            aria-label={label} onClick={expand} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); expand(); } }}>
            <title>{label}</title>
            <circle cx={cell.x} cy={cell.y} r={Math.min(42, 14 + Math.sqrt(cell.weight))} />
            <text x={cell.x} y={cell.y + 5} textAnchor="middle">{cell.weight}</text>
          </g>;
        })}
        {lineups.filter((lineup) => placeKey(lineup) === selectedPlace || lineup.id === activeId).map((lineup) => {
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
