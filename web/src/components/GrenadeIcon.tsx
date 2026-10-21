import type { GrenadeType } from "../types";

export type GrenadeIconType = GrenadeType | "flash" | "incendiary";

/** Grenade colours, shared with map coverage and legends. */
export const GRENADE_COLORS: Record<"smoke" | "molotov" | "flash" | "he", string> = {
  smoke: "#b9c3cc",
  molotov: "#ff7a1a",
  flash: "#f2d649",
  he: "#8fb04c",
};

const INK = "#0b0f14"; // outline and cut-outs: dark, so the glyph reads on bright radar floors too

function kind(type: GrenadeIconType): keyof typeof GRENADE_COLORS {
  if (type === "molotov" || type === "incendiary") return "molotov";
  if (type === "flash" || type === "flashbang") return "flash";
  if (type === "smoke") return "smoke";
  return "he";
}

/**
 * Original 32-unit pictograms: flat single-colour silhouettes with straight edges, one shared
 * construction (upright body on the same baseline, spoon lever on the right, pin ring on the
 * left) so the four read as one set. Type is carried by silhouette and colour, never colour alone.
 */
export function GrenadeGlyph({ type }: { type: GrenadeIconType }) {
  const k = kind(type);
  const fill = GRENADE_COLORS[k];
  const line = { stroke: INK, strokeWidth: 1.4, strokeLinejoin: "miter" as const, strokeLinecap: "square" as const };

  if (k === "molotov") {
    return <g {...line}>
      {/* flame: two hard-edged tongues */}
      <path d="M15 1 L19 6 L18 2 L23 8 L19 11 H13 Z" fill={fill} />
      {/* rag + neck */}
      <path d="M14 11 H19 V15 H14 Z" fill="#e8d3a8" />
      {/* bottle: chamfered shoulders, square base */}
      <path d="M13 15 H20 L24 20 V30 H9 V20 Z" fill={fill} />
      <path d="M12 23 H21" fill="none" />
    </g>;
  }

  if (k === "he") {
    return <g {...line}>
      <circle cx="9" cy="6" r="2.6" fill="none" stroke={fill} strokeWidth={1.8} />
      <path d="M12 9 V6 H19 L24 16" fill="none" stroke={fill} strokeWidth={2} />
      <path d="M12 9 H20 V12 H12 Z" fill={fill} />
      {/* octagonal fragmentation body */}
      <path d="M11 12 H21 L26 17 V25 L21 30 H11 L6 25 V17 Z" fill={fill} />
      <path d="M6 21 H26 M16 12 V30" fill="none" />
    </g>;
  }

  if (k === "flash") {
    return <g {...line}>
      <circle cx="8" cy="5" r="2.6" fill="none" stroke={fill} strokeWidth={1.8} />
      <path d="M11 8 V5 H19 L23 13" fill="none" stroke={fill} strokeWidth={2} />
      {/* slim canister with perforations */}
      <path d="M11 8 H20 V30 H11 Z" fill={fill} />
      <path d="M13 12 H18 V14 H13 Z M13 17 H18 V19 H13 Z M13 22 H18 V24 H13 Z" fill={INK} stroke="none" />
      {/* burst ticks */}
      <path d="M23 18 H28 M22.5 24 L27 27 M22.5 12.5 L26 10" fill="none" stroke={fill} strokeWidth={2} />
    </g>;
  }

  // smoke: wide canister, vent band on top, two body bands
  return <g {...line}>
    <circle cx="7" cy="5" r="2.6" fill="none" stroke={fill} strokeWidth={1.8} />
    <path d="M10 8 V5 H19 L24 13" fill="none" stroke={fill} strokeWidth={2} />
    <path d="M9 8 H23 V30 H9 Z" fill={fill} />
    <path d="M11 10.5 H13 V12.5 H11 Z M15 10.5 H17 V12.5 H15 Z M19 10.5 H21 V12.5 H19 Z" fill={INK} stroke="none" />
    <path d="M9 15 H23 M9 25 H23" fill="none" />
  </g>;
}

export default function GrenadeIcon({ type, size = 16 }: { type: GrenadeIconType; size?: number }) {
  return <svg className="grenade-icon" width={size} height={size} viewBox="3 0.5 26 30.5" aria-hidden="true" focusable="false">
    <GrenadeGlyph type={type} />
  </svg>;
}
