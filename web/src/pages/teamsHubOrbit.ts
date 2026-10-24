export const ORBIT_CARD_SIZE = { width: 168, height: 216 };

export type OrbitNodeSize = { width: number; height: number };

// Stable clockwise pool order and ambient colours, independent of match count.
export const ORBIT_POOL = [
  ["de_dust2", "Dust II", "rgba(217,155,67,.22)"],
  ["de_mirage", "Mirage", "rgba(225,95,65,.22)"],
  ["de_ancient", "Ancient", "rgba(34,197,94,.22)"],
  ["de_anubis", "Anubis", "rgba(234,179,8,.24)"],
  ["de_inferno", "Inferno", "rgba(249,115,22,.22)"],
  ["de_nuke", "Nuke", "rgba(56,189,248,.22)"],
  ["de_cache", "Cache", "rgba(148,163,184,.10)"],
] as const;
export const EMPTY_MAP_GLOW = ORBIT_POOL[6][2];

// Fit the *whole* rotating ellipse, including depth and hover, in the stage.
// For adjacent nodes, a collision is possible iff both separation components
// fall below the rectangle extents. The ellipse inequality below excludes that
// for every phase, rather than checking only the initial seven positions.
export function orbitLayout(width: number, height: number, nodes: OrbitNodeSize[], phase = 0) {
  const reserve = 1.05 * 1.08;
  const gap = 16;
  const maxWidth = Math.max(1, ...nodes.map((node) => node.width));
  const maxHeight = Math.max(1, ...nodes.map((node) => node.height));
  const chord = 2 * Math.sin(Math.PI / Math.max(2, nodes.length));
  const radii = (scale: number) => ({
    rx: Math.max(1, (width - maxWidth * reserve * scale) / 2 - gap),
    ry: Math.max(1, (height - maxHeight * reserve * scale) / 2 - gap),
  });
  const fits = (scale: number) => {
    const { rx, ry } = radii(scale);
    return ((maxWidth * reserve * scale + gap) / (chord * rx)) ** 2
      + ((maxHeight * reserve * scale + gap) / (chord * ry)) ** 2 <= 1;
  };
  let low = 0, high = 1;
  for (let i = 0; i < 24; i++) {
    const middle = (low + high) / 2;
    if (fits(middle)) low = middle; else high = middle;
  }
  const scale = low;
  const { rx, ry } = radii(scale);
  return { minHeight: 0, scale, points: nodes.map((_, index) => {
    const angle = -Math.PI / 2 + phase + index * 2 * Math.PI / nodes.length;
    return { x: width / 2 + rx * Math.cos(angle), y: height / 2 + ry * Math.sin(angle),
      scale: scale * (1 + .05 * Math.sin(angle)) };
  }) };
}

export function orbitRate(rate: number | null | undefined) {
  return rate == null ? "neutral" : rate >= .6 ? "strong" : rate >= .5 ? "neutral" : "weak";
}

/** Restrict both sample totals and ranking to the seven rendered pool nodes. */
export function orbitStats<T extends { map: string; n_matches: number; map_win_rate?: number | null }>(maps: T[], minMatches: number | undefined) {
  const shown = maps.filter((map) => ORBIT_POOL.some(([id]) => id === map.map));
  const ranked = shown.filter((map) => minMatches != null && map.n_matches >= minMatches && map.map_win_rate != null)
    .sort((a, b) => (b.map_win_rate ?? 0) - (a.map_win_rate ?? 0) || a.map.localeCompare(b.map));
  return { matches: shown.reduce((sum, map) => sum + map.n_matches, 0),
    best: ranked[0]?.map, worst: ranked.length > 1 ? ranked[ranked.length - 1].map : undefined };
}
