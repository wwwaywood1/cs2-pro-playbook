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
  const clustered = lineups.length > 50;
  const clusters = useMemo(() => {
    const cells = new Map<string, { x: number; y: number; weight: number; count: number; lineup: Lineup }>();
    for (const lineup of lineups) {
      const { radar_x: x, radar_y: y } = lineup.land;
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      const key = `${Math.floor(x / 64)}:${Math.floor(y / 64)}`;
      const weight = Math.max(1, lineup.n_throws);
      const cell = cells.get(key);
      if (cell) {
        cell.x += x * weight; cell.y += y * weight; cell.weight += weight; cell.count++;
        if (lineup.n_throws > cell.lineup.n_throws) cell.lineup = lineup;
      } else cells.set(key, { x: x * weight, y: y * weight, weight, count: 1, lineup });
    }
    return [...cells.entries()];
  }, [lineups]);

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

        {clustered ? clusters.map(([key, cell]) => <g key={key} className="landing-cluster" role="button" tabIndex={0}
          aria-label={`落点聚合 · ${cell.count} 组 · ${cell.weight} 次投掷；查看最常用道具`}
          onClick={() => onSelect(cell.lineup.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(cell.lineup.id); } }}>
          <title>{`${cell.count} 组道具 · ${cell.weight} 次投掷；点击查看最常用道具`}</title>
          <circle cx={cell.x / cell.weight} cy={cell.y / cell.weight} r={Math.min(36, 12 + Math.sqrt(cell.weight))} />
          <text x={cell.x / cell.weight} y={cell.y / cell.weight + 5} textAnchor="middle">{cell.count}</text>
        </g>) : null}
        {lineups.filter((lineup) => !clustered || lineup.id === activeId).map((lineup) => {
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
              <svg x={lineup.land.radar_x - 24} y={lineup.land.radar_y - 24} width="48" height="48" viewBox="0 0 32 32" aria-hidden="true">
                <GrenadeGlyph type={lineup.type} />
              </svg>
            </g>
          );
        })}
      </svg>

      <p className="radar-hint">{clustered ? "落点聚合（数字为道具组数） · 悬停 / 聚焦卡片查看轨迹" : "悬停 / 聚焦卡片查看轨迹"} · 圆点：起投点 · 图标：爆开点</p>
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
