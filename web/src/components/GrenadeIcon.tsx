import type { GrenadeType } from "../types";

type GrenadeIconType = GrenadeType | "flash" | "incendiary";

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
  // M18-style canister: short and wide, vent holes, label band, spoon flush with the body, pin ring
  smoke:
    "M11.4 9.6 H20.6 V12 H11.4 Z " +
    "M8.8 12.2 H23.2 V29.8 Q23.2 31 22 31 H10 Q8.8 31 8.8 29.8 Z " +
    "M10.6 14 H12.6 V16 H10.6 Z M13.6 14 H15.6 V16 H13.6 Z M16.6 14 H18.6 V16 H16.6 Z M19.6 14 H21.6 V16 H19.6 Z " +
    "M10.6 20 H21.4 V25 H10.6 Z " +
    "M20.6 9.8 L24.4 10.6 Q25.2 10.9 25.1 11.7 L24.3 24 H23.2 V12.4 L20.6 11.8 Z " +
    "M7.4 7.6 A2.7 2.7 0 1 0 7.41 7.6 Z M7.4 8.8 A1.5 1.5 0 1 1 7.39 8.8 Z M9.7 9.9 H11.4 V10.9 H9.7 Z",
  // M84-style flashbang: slim tube with slotted sides and burst rays above the cap, spoon, pin ring
  flash:
    "M13.4 6.4 H18.6 V8.8 H13.4 Z " +
    "M12.6 9 H19.4 V30.3 Q19.4 31 18.7 31 H13.3 Q12.6 31 12.6 30.3 Z " +
    "M14.1 11.2 H15.3 V16.8 H14.1 Z M16.7 11.2 H17.9 V16.8 H16.7 Z " +
    "M14.1 18.8 H15.3 V24.4 H14.1 Z M16.7 18.8 H17.9 V24.4 H16.7 Z " +
    "M12.6 26.4 H19.4 V27.2 H12.6 Z " +
    "M18.6 6.6 L22.2 7.4 Q22.8 7.6 22.7 8.2 L21.6 21 L20.4 20.9 L21.3 8.8 L18.6 8.2 Z " +
    "M10.4 4.4 A2.7 2.7 0 1 0 10.41 4.4 Z M10.4 5.6 A1.5 1.5 0 1 1 10.39 5.6 Z M12.6 6.8 H13.5 V7.8 H12.6 Z " +
    "M15.4 0.4 H16.6 V4.6 H15.4 Z M19.6 1.2 L20.6 1.9 L18.6 5.2 L17.6 4.5 Z M23.4 4.6 L23.9 5.7 L20.4 7 L20 5.9 Z",
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
