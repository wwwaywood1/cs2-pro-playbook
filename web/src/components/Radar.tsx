import GrenadeIcon, { GrenadeGlyph } from "./GrenadeIcon";
import { useEffect, useState } from "react";
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
  const [imageOk, setImageOk] = useState(true);

  useEffect(() => {
    setImageOk(true);
  }, [map]);

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

        {lineups.map((lineup) => {
          const selected = lineup.id === selectedId;
          const dimmed = selectedId !== null && !selected;
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
              <line
                className="arrow-hit"
                x1={lineup.throw.radar_x}
                y1={lineup.throw.radar_y}
                x2={lineup.land.radar_x}
                y2={lineup.land.radar_y}
              />
              <line
                className="arrow-line"
                markerEnd={`url(#arrowhead-${lineup.type})`}
                x1={lineup.throw.radar_x}
                y1={lineup.throw.radar_y}
                x2={lineup.land.radar_x}
                y2={lineup.land.radar_y}
              />
              <circle
                className="throw-dot"
                cx={lineup.throw.radar_x}
                cy={lineup.throw.radar_y}
                r={selected ? 9 : 5.5}
              />
              <svg x={lineup.land.radar_x - 24} y={lineup.land.radar_y - 24} width="48" height="48" viewBox="0 0 32 32" aria-hidden="true">
                <GrenadeGlyph type={lineup.type} />
              </svg>
            </g>
          );
        })}
      </svg>

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
