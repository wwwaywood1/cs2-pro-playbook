export const ORBIT_CARD_SIZE = { width: 196, height: 252 };
// Matches the stacked hero logo/name/count in teams-hub.css.
// The map preview stays below the stage so it cannot enlarge the exclusion box.
export const ORBIT_CORE_SIZE = { width: 300, height: 260 };

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

// Equal-distance travel around a rounded rectangle uses the wide stage corners.
// Cache the full-phase fit: rAF only interpolates the fitted path, never refits it.
const SAMPLES = 2048;
let cached: { key: string; scale: number; path: { x: number; y: number }[] } | undefined;
export function orbitLayout(width: number, height: number, nodes: OrbitNodeSize[], phase = 0) {
  const reserve = 1.05 * 1.08, gap = 16;
  const maxWidth = Math.max(1, ...nodes.map(node => node.width));
  const maxHeight = Math.max(1, ...nodes.map(node => node.height));
  const key = `${width}:${height}:${maxWidth}:${maxHeight}:${nodes.length}`;
  const pointAt = (path: { x: number; y: number }[], turn: number) => {
    const position = ((turn % 1 + 1) % 1) * SAMPLES;
    const index = Math.floor(position), fraction = position - index;
    const a = path[index], b = path[(index + 1) % SAMPLES];
    return { x: a.x + (b.x - a.x) * fraction, y: a.y + (b.y - a.y) * fraction };
  };
  if (cached?.key !== key) {
    const candidate = (scale: number) => {
      const cardWidth = maxWidth * reserve * scale, cardHeight = maxHeight * reserve * scale;
      const rx = Math.max(1, (width - cardWidth) / 2 - gap);
      const ry = Math.max(1, (height - cardHeight) / 2 - gap);
      // Polygonal superellipse (power 4), reparameterised by distance measured
      // in card-width/card-height units. This avoids bunching at the short axis.
      const outline = Array.from({ length: 257 }, (_, i) => {
        const angle = -Math.PI / 2 + i / 256 * 2 * Math.PI;
        const c = Math.cos(angle), s = Math.sin(angle);
        return { x: rx * Math.sign(c) * Math.sqrt(Math.abs(c)), y: ry * Math.sign(s) * Math.sqrt(Math.abs(s)), distance: 0 };
      });
      for (let i = 1; i < outline.length; i++) {
        outline[i].distance = outline[i - 1].distance + Math.hypot(
          (outline[i].x - outline[i - 1].x) / (cardWidth + gap),
          (outline[i].y - outline[i - 1].y) / (cardHeight + gap));
      }
      const length = outline[256].distance;
      let segment = 1;
      const path = Array.from({ length: SAMPLES }, (_, i) => {
        const distance = i / SAMPLES * length;
        while (outline[segment].distance < distance) segment++;
        const a = outline[segment - 1], b = outline[segment];
        const f = (distance - a.distance) / (b.distance - a.distance);
        return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
      });
      // A pair can move at most this far between a sampled phase and its
      // nearest neighbour. Reserve it to cover *continuous* phases, not just
      // the samples. The same bound covers interpolation and core clearance.
      const margin = length * Math.max(cardWidth + gap, cardHeight + gap) / SAMPLES;
      let fits = true;
      for (let step = 0; fits && step < SAMPLES; step++) {
        const points = nodes.map((_, i) => pointAt(path, step / SAMPLES + i / nodes.length));
        for (let i = 0; fits && i < points.length; i++) {
          const a = points[i];
          if (Math.max(Math.abs(a.x) - (cardWidth + ORBIT_CORE_SIZE.width) / 2,
                       Math.abs(a.y) - (cardHeight + ORBIT_CORE_SIZE.height) / 2) < gap + margin) fits = false;
          for (let j = i + 1; fits && j < points.length; j++) {
            const b = points[j];
            if (Math.max(Math.abs(a.x - b.x) - cardWidth, Math.abs(a.y - b.y) - cardHeight) < gap + margin) fits = false;
          }
        }
      }
      return { fits, path };
    };
    let low = 0, high = 1;
    for (let i = 0; i < 20; i++) {
      const middle = (low + high) / 2;
      if (candidate(middle).fits) low = middle; else high = middle;
    }
    cached = { key, scale: low, path: candidate(low).path };
  }
  const { scale, path } = cached;
  return { minHeight: 0, scale, points: nodes.map((_, index) => {
    const turn = phase / (2 * Math.PI) + index / nodes.length;
    const point = pointAt(path, turn);
    return { x: width / 2 + point.x, y: height / 2 + point.y,
      scale: scale * (1 + .05 * Math.sin(-Math.PI / 2 + turn * 2 * Math.PI)) };
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
