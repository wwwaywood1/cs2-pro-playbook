import { calloutLabel } from "./i18n";
import type { HeatmapBaseline, PlayerSideSummary } from "./types";
import type { HeatmapMarker } from "./components/HeatmapCanvas";

export type PlaceMarker = HeatmapMarker & { level: number };

/** Prefer map-wide observed callout anchors; older exports retain hold/utility linking. */
export function heatmapMarkers(map: string, baseline: HeatmapBaseline, summaries: PlayerSideSummary[], color: string): PlaceMarker[] {
  const places = new Map<string, PlaceMarker>();
  const add = (place: string | null, level: number, x: number | null, y: number | null) => {
    if (!place || x === null || y === null || !Number.isFinite(x) || !Number.isFinite(y)) return;
    const key = `${place}:${level}`;
    if (!places.has(key)) places.set(key, { id: `place:${place}`, level, x, y, color, title: calloutLabel(map, place), small: true });
  };
  for (const position of baseline.place_positions ?? []) add(position.place, position.level, position.radar_x, position.radar_y);
  for (const summary of summaries) {
    for (const hold of summary.holds) add(hold.place, hold.level, hold.radar_x, hold.radar_y);
    for (const spot of summary.utility.spots) add(spot.place, spot.level, spot.radar_x, spot.radar_y);
  }
  return [...places.values()];
}

/** Preview a linked place on its recorded floor, then restore the chosen floor on leave. */
export function linkedLevel(activeId: string | null, markers: PlaceMarker[], chosen: number) {
  return markers.find((marker) => marker.id === activeId && marker.level === chosen)?.level
    ?? markers.find((marker) => marker.id === activeId)?.level ?? chosen;
}
