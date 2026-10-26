export const ORBIT_CARD_SIZE = { width: 196, height: 252 };
// Matches the stacked hero logo/name/count in teams-hub.css.
// The map preview stays below the stage so it cannot enlarge the exclusion box.
export const ORBIT_CORE_SIZE = { width: 230, height: 285 };

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
  const reserve = 1.06, gap = 10;
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
      // Extra vertical margin covers 1.08 hover emphasis and leaves at least 16px.
      // CSS adds 28px to the stage and recovers it above, preserving fitted size.
      const ry = Math.max(1, (height - cardHeight) / 2 - 24);
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

/** 95% Wilson score interval of a rate observed over n maps. */
export function wilson(rate: number, n: number, z = 1.959964): [number, number] {
  if (!(n > 0) || !Number.isFinite(rate)) return [0, 1];
  const p = Math.max(0, Math.min(1, rate));
  const z2 = z * z;
  const centre = (p + z2 / (2 * n)) / (1 + z2 / n);
  const half = z / (1 + z2 / n) * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n));
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

/** A map needs this many matches (and the export's reliability minimum) to earn a badge. */
export const BADGE_MIN_MATCHES = 8;

type BadgeMap = { map: string; n_matches: number; map_win_rate?: number | null; round_win_rate?: number | null };

/**
 * 王牌图 / 短板图 with evidence, not by the raw rate (7/8 must not beat 32/38):
 * best = highest Wilson lower bound, worst = lowest Wilson upper bound, over maps with
 * n >= max(BADGE_MIN_MATCHES, minMatches); ties break on round win rate, then map id.
 * No badge at all when the two 95% intervals overlap heavily, when the map rates tie,
 * when the round win rates contradict the order, or with fewer than two maps.
 * "Heavily" = the overlap exceeds half the mean margin of error of the two intervals,
 * which for independent proportions is roughly a difference at p ≈ .05 (Cumming &
 * Finch 2005); requiring no overlap at all would leave almost every team without badges.
 */
export function mapBadges<T extends BadgeMap>(maps: T[], minMatches: number | undefined): { best: string | undefined; worst: string | undefined } {
  const none = { best: undefined, worst: undefined };
  if (minMatches == null) return none;
  const threshold = Math.max(BADGE_MIN_MATCHES, minMatches);
  const rows = maps.filter((map) => map.n_matches >= threshold && map.map_win_rate != null && Number.isFinite(map.map_win_rate))
    .map((map) => {
      const [lower, upper] = wilson(map.map_win_rate!, map.n_matches);
      return { map: map.map, rate: map.map_win_rate!, rounds: map.round_win_rate ?? null, lower, upper };
    });
  if (rows.length < 2) return none;
  const rounds = (row: (typeof rows)[number]) => row.rounds ?? .5;
  const best = [...rows].sort((a, b) => b.lower - a.lower || rounds(b) - rounds(a) || a.map.localeCompare(b.map))[0];
  const worst = [...rows].sort((a, b) => a.upper - b.upper || rounds(a) - rounds(b) || a.map.localeCompare(b.map))[0];
  const margin = ((best.upper - best.lower) + (worst.upper - worst.lower)) / 4;
  if (best.map === worst.map || best.rate <= worst.rate || worst.upper - best.lower > margin / 2) return none;
  if (best.rounds != null && worst.rounds != null && best.rounds < worst.rounds) return none;
  return { best: best.map, worst: worst.map };
}

/** Restrict both sample totals and ranking to the seven rendered pool nodes. */
export function orbitStats<T extends BadgeMap>(maps: T[], minMatches: number | undefined) {
  const shown = maps.filter((map) => ORBIT_POOL.some(([id]) => id === map.map));
  return { matches: shown.reduce((sum, map) => sum + map.n_matches, 0), ...mapBadges(shown, minMatches) };
}
