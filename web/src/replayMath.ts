import type { ReplayRound } from "./types";

/** Export times start at freeze end, and plant time starts a new 40-second clock. */
export function roundClock(elapsed: number, plantTime?: number): string {
  const remaining = Math.max(0, Math.ceil(plantTime != null && elapsed >= plantTime ? 40 - (elapsed - plantTime) : 115 - elapsed));
  return `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`;
}
export function utilityEffect(nade: "smoke" | "molotov" | "flash" | "he", age: number, scale?: number) {
  const life = nade === "smoke" ? 18 : nade === "molotov" ? 7 : .7;
  return { life, active: age >= 0 && age < life, radius: scale && scale > 0 ? (nade === "smoke" ? 144 : nade === "molotov" ? 120 : 64) / scale : 0 };
}
export function framePosition(frames: ReplayRound["frames"], index: number, at: number): [number, number] | null {
  const second = Math.max(0, Math.min(Math.floor(at), frames.length - 1));
  const start = frames[second]?.[index];
  if (!start) return null;
  const end = frames[second + 1]?.[index] ?? start;
  const fraction = at - Math.floor(at);
  return [start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction];
}
/** Shortest arc through 0/360; reduced motion holds the current second's cone. */
export function frameYaw(yaw: ReplayRound["yaw"], index: number, at: number, interpolate = true): number | null {
  if (!yaw?.length) return null;
  const second = Math.max(0, Math.min(Math.floor(at), yaw.length - 1));
  const start = yaw[second]?.[index];
  if (start == null || !Number.isFinite(start)) return null;
  const end = yaw[second + 1]?.[index];
  if (!interpolate || end == null || !Number.isFinite(end)) return start;
  const delta = ((end - start + 180) % 360 + 360) % 360 - 180;
  return ((start + delta * (at - Math.floor(at))) % 360 + 360) % 360;
}
export function lastPosition(frames: ReplayRound["frames"], index: number | null, at: number): [number, number] | null {
  if (index == null) return null;
  for (let second = Math.min(Math.floor(at), frames.length - 1); second >= 0; second--) {
    const point = frames[second]?.[index];
    if (point) return point;
  }
  return null;
}
