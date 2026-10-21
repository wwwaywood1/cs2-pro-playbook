import type { GrenadeType } from "../types";

export type GrenadeIconType = GrenadeType | "flash" | "incendiary";

/** Grenade colours, shared with map coverage and legends. */
export const GRENADE_COLORS: Record<"smoke" | "molotov" | "flash" | "he", string> = {
  smoke: "#c5ced6",
  molotov: "#ff8a2a",
  flash: "#f4dc5a",
  he: "#a3c45a",
};

function kind(type: GrenadeIconType): keyof typeof GRENADE_COLORS {
  if (type === "molotov" || type === "incendiary") return "molotov";
  if (type === "flash" || type === "flashbang") return "flash";
  if (type === "smoke") return "smoke";
  return "he";
}

/*
 * Original side-view silhouettes in the spirit of a game HUD: one flat colour, details cut out
 * (evenodd), true-to-object proportions, a thin dark halo (stroke painted under the fill) so the
 * shape holds on bright radar floors. 32-unit grid, objects stand on y = 31.
 */
const PATHS: Record<keyof typeof GRENADE_COLORS, string> = {
  // M18-style canister: cap, body with top and bottom vent holes, spoon along the right side, pin ring
  smoke:
    "M12.5 6.2 H19.5 V8.6 H12.5 Z " +
    "M11 9 H21 V30.2 Q21 31 20.2 31 H11.8 Q11 31 11 30.2 Z " +
    "M12.6 11 H14.2 V12.6 H12.6 Z M15.2 11 H16.8 V12.6 H15.2 Z M17.8 11 H19.4 V12.6 H17.8 Z " +
    "M12.6 27.4 H14.2 V29 H12.6 Z M15.2 27.4 H16.8 V29 H15.2 Z M17.8 27.4 H19.4 V29 H17.8 Z " +
    "M11 15.2 H21 V16 H11 Z " +
    "M19.5 6.4 L23.4 7.2 Q24 7.4 23.9 8 L22.9 22.5 L21.7 22.4 L22.5 8.6 L19.5 8 Z " +
    "M8.6 4.4 A2.7 2.7 0 1 0 8.61 4.4 Z M8.6 5.6 A1.5 1.5 0 1 1 8.59 5.6 Z M10.9 6.6 H12.6 V7.6 H10.9 Z",
  // M84-style flashbang: slim tube with slotted sides, spoon, pin ring
  flash:
    "M13.4 6.4 H18.6 V8.8 H13.4 Z " +
    "M12.6 9 H19.4 V30.3 Q19.4 31 18.7 31 H13.3 Q12.6 31 12.6 30.3 Z " +
    "M14.1 11.2 H15.3 V16.8 H14.1 Z M16.7 11.2 H17.9 V16.8 H16.7 Z " +
    "M14.1 18.8 H15.3 V24.4 H14.1 Z M16.7 18.8 H17.9 V24.4 H16.7 Z " +
    "M12.6 26.4 H19.4 V27.2 H12.6 Z " +
    "M18.6 6.6 L22.2 7.4 Q22.8 7.6 22.7 8.2 L21.6 21 L20.4 20.9 L21.3 8.8 L18.6 8.2 Z " +
    "M10.4 4.4 A2.7 2.7 0 1 0 10.41 4.4 Z M10.4 5.6 A1.5 1.5 0 1 1 10.39 5.6 Z M12.6 6.8 H13.5 V7.8 H12.6 Z",
  // M67-style fragmentation: smooth sphere, fuze neck, curved spoon, pin ring
  he:
    "M16 12.4 A9.3 9.3 0 1 0 16.01 12.4 Z " +
    "M13.2 8.4 H18.8 V12.8 H13.2 Z " +
    "M18.8 8.6 L22.6 9.6 Q23.6 10 23.4 11 Q22.9 14.6 21.2 16.4 L20.3 15.6 Q21.6 13.9 22 11.2 L18.8 10.4 Z " +
    "M10 6.8 A2.7 2.7 0 1 0 10.01 6.8 Z M10 8 A1.5 1.5 0 1 1 9.99 8 Z M12.2 9.4 H13.2 V10.4 H12.2 Z",
  // Molotov: bottle with rag tied at the neck and a flame
  molotov:
    "M14 11.2 H18 V14.6 L21.2 18.4 Q21.8 19.1 21.8 20 V30.2 Q21.8 31 21 31 H11 Q10.2 31 10.2 30.2 V20 Q10.2 19.1 10.8 18.4 L14 14.6 Z " +
    "M12 22.6 H20 V27.2 H12 Z " +
    "M13.3 10 H18.7 V11.6 H13.3 Z M18.4 10.6 L21.4 13.4 L20.6 14.2 L17.9 11.6 Z " +
    "M16.2 0.8 Q21 4.6 19.4 8.2 Q18.6 9.8 16 9.8 Q13.2 9.8 12.7 7.6 Q12.3 5.4 14.6 3.4 Q14.4 5.6 15.8 6 Q15 3.4 16.2 0.8 Z " +
    "M16 5.2 Q17.8 6.9 17 8.3 Q16.6 8.9 16 8.9 Q15.3 8.9 15.1 8.2 Q14.9 7.3 16 5.2 Z",
};

export function GrenadeGlyph({ type }: { type: GrenadeIconType }) {
  const k = kind(type);
  return (
    <path
      d={PATHS[k]}
      fill={GRENADE_COLORS[k]}
      fillRule="evenodd"
      stroke="rgba(6, 9, 13, 0.85)"
      strokeWidth={1.4}
      strokeLinejoin="round"
      paintOrder="stroke"
    />
  );
}

export default function GrenadeIcon({ type, size = 16 }: { type: GrenadeIconType; size?: number }) {
  return (
    <svg className="grenade-icon" width={size} height={size} viewBox="5.5 0 21 32" aria-hidden="true" focusable="false">
      <GrenadeGlyph type={type} />
    </svg>
  );
}
