// Heatmap math for the site. Pure functions except toDataUrl (needs a DOM canvas).
// Mirrors playbook/heatmap.py: each layer is turned into a share of its own total
// before weighting, because seconds, shots and grenades are not comparable units.

import type { HeatData, HeatLayer, HeatPhase, Side } from "./types";

export const HEAT_LAYERS: HeatLayer[] = [
  "presence",
  "holding",
  "shots",
  "util_throw",
  "util_land",
  "kills",
  "deaths",
];
export const HEAT_PHASES: HeatPhase[] = ["early", "mid", "post"];

export type Weights = Partial<Record<HeatLayer, number>>;
export const DEFAULT_WEIGHTS: Weights = { presence: 1, shots: 1, util_throw: 1 };

export interface GridShape {
  grid: number; // cells per side
  levels: number; // 1, or 2 for maps with a lower floor
}

export type Dense = Float32Array; // length levels * grid * grid

function size(shape: GridShape): number {
  return shape.levels * shape.grid * shape.grid;
}

/** Sum the chosen phases of one side into one dense grid per layer. */
export function denseLayers(
  data: HeatData,
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

/** Normalise so the weights sum to 1 (keeps "subject minus baseline" comparable). */
export function normalisedWeights(weights: Weights): Weights {
  let sum = 0;
  for (const layer of HEAT_LAYERS) sum += Math.max(0, weights[layer] ?? 0);
  if (sum <= 0) return {};
  const out: Weights = {};
  for (const layer of HEAT_LAYERS) {
    const w = Math.max(0, weights[layer] ?? 0);
    if (w) out[layer] = w / sum;
  }
  return out;
}

export function difference(a: Dense, b: Dense): Dense {
  const out = new Float32Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = a[i] - b[i];
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

export type ColorMode = "sequential" | "diverging";

// Sequential: transparent -> purple -> orange -> pale yellow ("inferno"-like).
const SEQ: [number, number, number][] = [
  [40, 11, 84],
  [120, 28, 109],
  [187, 55, 84],
  [237, 105, 37],
  [251, 180, 26],
  [252, 255, 164],
];
const NEG: [number, number, number] = [59, 130, 246]; // less than baseline
const POS: [number, number, number] = [239, 68, 68]; // more than baseline

function ramp(t: number): [number, number, number] {
  const x = Math.min(1, Math.max(0, t)) * (SEQ.length - 1);
  const i = Math.min(SEQ.length - 2, Math.floor(x));
  const f = x - i;
  const a = SEQ[i];
  const b = SEQ[i + 1];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

/**
 * RGBA bytes (grid x grid) for one level. Sequential scales to the level's maximum;
 * diverging scales to the largest absolute value. Alpha grows with intensity so the
 * radar stays visible where nothing happens.
 */
export function toRgba(values: Dense, shape: GridShape, level: number, mode: ColorMode): Uint8ClampedArray {
  const { grid } = shape;
  const off = level * grid * grid;
  const n = grid * grid;
  let lim = 0;
  for (let i = 0; i < n; i++) {
    const v = mode === "diverging" ? Math.abs(values[off + i]) : values[off + i];
    if (v > lim) lim = v;
  }
  const px = new Uint8ClampedArray(n * 4);
  if (!(lim > 0)) return px;
  for (let i = 0; i < n; i++) {
    const v = values[off + i] / lim;
    let rgb: [number, number, number];
    let alpha: number;
    if (mode === "diverging") {
      rgb = v >= 0 ? POS : NEG;
      alpha = Math.min(0.85, Math.abs(v) * 1.6);
    } else {
      rgb = ramp(v);
      alpha = Math.min(0.85, Math.max(0, v) * 1.6);
    }
    px[i * 4] = rgb[0];
    px[i * 4 + 1] = rgb[1];
    px[i * 4 + 2] = rgb[2];
    px[i * 4 + 3] = Math.round(alpha * 255);
  }
  return px;
}

/** PNG data URL (grid x grid pixels); draw it stretched over the 1024x1024 radar. */
export function toDataUrl(values: Dense, shape: GridShape, level: number, mode: ColorMode): string {
  const canvas = document.createElement("canvas");
  canvas.width = shape.grid;
  canvas.height = shape.grid;
  const ctx = canvas.getContext("2d");
  if (!ctx) return "";
  const image = ctx.createImageData(shape.grid, shape.grid);
  image.data.set(toRgba(values, shape, level, mode));
  ctx.putImageData(image, 0, 0);
  return canvas.toDataURL("image/png");
}

/** Per-round total of one layer for the chosen phases (for captions like "11.2 shots / round"). */
export function perRound(data: HeatData, side: Side, phases: HeatPhase[], layer: HeatLayer): number | null {
  const bySide = data.per_round[side];
  if (!bySide) return null;
  if (phases.length === HEAT_PHASES.length) return bySide.all?.[layer] ?? null;
  let total = 0;
  let any = false;
  for (const phase of phases) {
    const v = bySide[phase]?.[layer];
    if (v !== undefined) {
      total += v;
      any = true;
    }
  }
  return any ? total : null;
}
