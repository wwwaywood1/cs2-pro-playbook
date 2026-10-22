// Heatmap math for the team view. Pure functions except toDataUrl (needs a DOM canvas).
// Mirrors playbook/heatmap.py and scripts/heatmap_preview.py: layers are combined as
// shares of their own totals (seconds, shots and grenades are different units), each
// player is drawn in his colour from light (little) to deep (a lot).

import type { HeatGrid, HeatLayer, HeatPhase, Side } from "./types";

const HEAT_LAYERS: HeatLayer[] = [
  "presence",
  "holding",
  "shots",
  "kills",
  "deaths",
  "smoke",
  "flash",
  "molotov",
  "he",
];
export const HEAT_PHASES: HeatPhase[] = ["early", "mid", "post"];
export const UTILITY_LAYERS: HeatLayer[] = ["smoke", "flash", "molotov", "he"];

export type Weights = Partial<Record<HeatLayer, number>>;
export type HeatView = "presence" | "holding" | "fights" | "utility";

/** The four views of the page. "utility" can be narrowed to one grenade type. */
export const VIEW_WEIGHTS: Record<HeatView, Weights> = {
  presence: { presence: 1 },
  holding: { holding: 1 },
  fights: { shots: 1, kills: 1, deaths: 1 },
  utility: { smoke: 1, flash: 1, molotov: 1, he: 1 },
};

interface PlayerColor {
  key: string; // i18n key suffix: heatmap.color.<key>
  light: string;
  deep: string;
}

/** Index = RosterEntry.color. 0 red, 1 blue, 2 purple, 3 green, 4 orange, then grey. */
const PLAYER_COLORS: PlayerColor[] = [
  { key: "red", light: "#fecaca", deep: "#b91c1c" },
  { key: "blue", light: "#bfdbfe", deep: "#1d4ed8" },
  { key: "purple", light: "#e9d5ff", deep: "#7e22ce" },
  { key: "green", light: "#bbf7d0", deep: "#15803d" },
  { key: "orange", light: "#fed7aa", deep: "#c2410c" },
  { key: "grey", light: "#e5e7eb", deep: "#4b5563" },
];

// Player ownership uses shades within its side's hue; T stays amber, CT stays blue.
const SIDE_PLAYER_COLORS = {
  T: ["#f5d487", "#e8b75a", "#ffb46b", "#dc9a38", "#bf792e", "#ad9065"],
  CT: ["#c7e7ff", "#8fcaff", "#6db6f2", "#519ee9", "#377fc5", "#6f94b8"],
};
export function playerColor(index: number, side?: Side): PlayerColor {
  const slot = Math.min(Math.max(0, index), PLAYER_COLORS.length - 1);
  return side ? { key: side === "T" ? "orange" : "blue", light: side === "T" ? "#ffdaa9" : "#c7e7ff", deep: SIDE_PLAYER_COLORS[side][slot] } : PLAYER_COLORS[slot];
}

const GAMMA = 0.6; // lift faint areas so all five players stay visible
const ALPHA_FLOOR = 0.12; // below this share of the player's peak: transparent
const ALPHA_MAX = 0.9;

interface GridShape {
  grid: number; // cells per side
  levels: number; // 1, or 2 for maps with a lower floor
}

export type Dense = Float32Array; // length levels * grid * grid

function size(shape: GridShape): number {
  return shape.levels * shape.grid * shape.grid;
}

/** Sum the chosen phases of one side into one dense grid per layer. */
export function denseLayers(
  data: HeatGrid,
  side: Side,
  phases: HeatPhase[],
  shape: GridShape,
): Partial<Record<HeatLayer, Dense>> {
  const out: Partial<Record<HeatLayer, Dense>> = {};
  const bySide = data.data[side];
  if (!bySide) return out;
  for (const phase of phases) {
    const layers = bySide[phase];
    if (!layers) continue;
    for (const layer of HEAT_LAYERS) {
      const flat = layers[layer];
      if (!flat || flat.length === 0) continue;
      const dense = out[layer] ?? (out[layer] = new Float32Array(size(shape)));
      for (let i = 0; i + 1 < flat.length; i += 2) {
        const cell = flat[i];
        if (cell >= 0 && cell < dense.length) dense[cell] += flat[i + 1];
      }
    }
  }
  return out;
}

/** Weighted sum of layer shares; a layer with no data contributes nothing. */
export function combine(
  layers: Partial<Record<HeatLayer, Dense>>,
  weights: Weights,
  shape: GridShape,
): Dense {
  const out = new Float32Array(size(shape));
  for (const layer of HEAT_LAYERS) {
    const w = weights[layer] ?? 0;
    const values = layers[layer];
    if (!w || !values) continue;
    let total = 0;
    for (let i = 0; i < values.length; i++) total += values[i];
    if (!(total > 0)) continue;
    const k = w / total;
    for (let i = 0; i < values.length; i++) out[i] += values[i] * k;
  }
  return out;
}

/** Separable gaussian blur, per level, sigma in cells (0 = no blur). */
export function blur(values: Dense, shape: GridShape, sigma: number): Dense {
  if (!(sigma > 0)) return values.slice();
  const radius = Math.max(1, Math.ceil(sigma * 3));
  const kernel = new Float32Array(2 * radius + 1);
  let ksum = 0;
  for (let i = -radius; i <= radius; i++) {
    const v = Math.exp(-(i * i) / (2 * sigma * sigma));
    kernel[i + radius] = v;
    ksum += v;
  }
  for (let i = 0; i < kernel.length; i++) kernel[i] /= ksum;

  const { grid, levels } = shape;
  const out = new Float32Array(values.length);
  const tmp = new Float32Array(grid * grid);
  for (let lvl = 0; lvl < levels; lvl++) {
    const off = lvl * grid * grid;
    for (let r = 0; r < grid; r++) {
      for (let c = 0; c < grid; c++) {
        let acc = 0;
        for (let k = -radius; k <= radius; k++) {
          const cc = c + k;
          if (cc >= 0 && cc < grid) acc += values[off + r * grid + cc] * kernel[k + radius];
        }
        tmp[r * grid + c] = acc;
      }
    }
    for (let r = 0; r < grid; r++) {
      for (let c = 0; c < grid; c++) {
        let acc = 0;
        for (let k = -radius; k <= radius; k++) {
          const rr = r + k;
          if (rr >= 0 && rr < grid) acc += tmp[rr * grid + c] * kernel[k + radius];
        }
        out[off + r * grid + c] = acc;
      }
    }
  }
  return out;
}

function hexRgb(hex: string): [number, number, number] {
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
}

function shade(color: PlayerColor, v: number): [number, number, number] {
  const a = hexRgb(color.light);
  const b = hexRgb(color.deep);
  return [a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v, a[2] + (b[2] - a[2]) * v];
}

function levelMax(values: Dense, off: number, n: number): number {
  let m = 0;
  for (let i = 0; i < n; i++) if (values[off + i] > m) m = values[off + i];
  return m;
}

/**
 * RGBA bytes (grid x grid) of one player on one level: his colour from light to deep,
 * scaled to his own peak (so a player who plays one spot and one who roams both show).
 */
export function playerRgba(values: Dense, shape: GridShape, level: number, color: PlayerColor): Uint8ClampedArray {
  const n = shape.grid * shape.grid;
  const off = level * n;
  const px = new Uint8ClampedArray(n * 4);
  const max = levelMax(values, off, n);
  if (!(max > 0)) return px;
  for (let i = 0; i < n; i++) {
    const v = Math.pow(Math.min(1, Math.max(0, values[off + i] / max)), GAMMA);
    const [r, g, b] = shade(color, v);
    px[i * 4] = r;
    px[i * 4 + 1] = g;
    px[i * 4 + 2] = b;
    px[i * 4 + 3] = Math.round(Math.min(ALPHA_MAX, Math.max(0, (v - ALPHA_FLOOR) * 1.6)) * 255);
  }
  return px;
}

/**
 * "Who owns this area": every cell takes the colour of the player with the largest
 * value there (each player first scaled to his own peak), shaded by that value.
 */
export function ownerRgba(
  players: { values: Dense; color: PlayerColor }[],
  shape: GridShape,
  level: number,
): Uint8ClampedArray {
  const n = shape.grid * shape.grid;
  const off = level * n;
  const px = new Uint8ClampedArray(n * 4);
  const maxes = players.map((p) => levelMax(p.values, off, n));
  for (let i = 0; i < n; i++) {
    let best = -1;
    let bestV = 0;
    players.forEach((p, k) => {
      const v = maxes[k] > 0 ? p.values[off + i] / maxes[k] : 0;
      if (v > bestV) {
        bestV = v;
        best = k;
      }
    });
    if (best < 0) continue;
    const v = Math.pow(Math.min(1, bestV), GAMMA);
    const [r, g, b] = shade(players[best].color, v);
    px[i * 4] = r;
    px[i * 4 + 1] = g;
    px[i * 4 + 2] = b;
    px[i * 4 + 3] = Math.round(Math.min(0.85, Math.max(0, (v - ALPHA_FLOOR) * 1.6)) * 255);
  }
  return px;
}

/** PNG data URL of grid x grid RGBA bytes; draw it stretched over the 1024x1024 radar. */
export function toDataUrl(rgba: Uint8ClampedArray, grid: number): string {
  const canvas = document.createElement("canvas");
  canvas.width = grid;
  canvas.height = grid;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const image = ctx.createImageData(grid, grid);
  image.data.set(rgba);
  ctx.putImageData(image, 0, 0);
  return canvas.toDataURL("image/png");
}

/** Per-round total of some layers for the chosen phases (captions: "72 s / round"). */
export function perRound(data: HeatGrid, side: Side, phases: HeatPhase[], layers: HeatLayer[]): number | null {
  const bySide = data.per_round[side];
  if (!bySide) return null;
  let total = 0;
  let any = false;
  const sources = phases.length === HEAT_PHASES.length ? (["all"] as const) : phases;
  for (const phase of sources) {
    for (const layer of layers) {
      const v = bySide[phase]?.[layer];
      if (v !== undefined) {
        total += v;
        any = true;
      }
    }
  }
  return any ? total : null;
}
