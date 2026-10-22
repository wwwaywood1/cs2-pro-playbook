import { fmtInt } from "../format";
import { useEffect } from "react";
import { t } from "../i18n";
import type { HeatmapTeamIndexEntry } from "../types";

interface MapSwitcherProps {
  maps: HeatmapTeamIndexEntry["maps"];
  map: string;
  onChange: (map: string) => void;
}

export default function MapSwitcher({ maps, map, onChange }: MapSwitcherProps) {
  const index = Math.max(0, maps.findIndex((item) => item.map === map));
  const current = maps[index];
  const disabled = maps.length < 2;

  useEffect(() => {
    if (disabled) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
          event.shiftKey || (event.key !== "ArrowLeft" && event.key !== "ArrowRight")) return;
      const target = event.target;
      if (target instanceof Element && target.closest(
        "input, textarea, select, [contenteditable]:not([contenteditable='false']), [role='slider'], [role='tablist']",
      )) return;
      event.preventDefault();
      const delta = event.key === "ArrowLeft" ? -1 : 1;
      onChange(maps[(index + delta + maps.length) % maps.length].map);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [disabled, index, maps, onChange]);

  if (!current) return null;
  const move = (delta: number) => onChange(maps[(index + delta + maps.length) % maps.length].map);
  return (
    <div className="hm-switcher">
      <button type="button" disabled={disabled} onClick={() => move(-1)} aria-label={t("heatmap.prev_map")}>
        ←
      </button>
      <div aria-live="polite">
        <strong>{current.display_name}</strong>
        <span>{t("heatmap.map_caption", {
          matches: fmtInt(current.n_matches), t: fmtInt(current.rounds.T), ct: fmtInt(current.rounds.CT),
        })}</span>
      </div>
      <button type="button" disabled={disabled} onClick={() => move(1)} aria-label={t("heatmap.next_map")}>
        →
      </button>
    </div>
  );
}
