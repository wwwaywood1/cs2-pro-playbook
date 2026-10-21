import type { GrenadeType } from "../types";

export type GrenadeIconType = GrenadeType | "flash" | "incendiary";

/** Original 32-unit artwork, shared by inline labels and radar markers. */
export function GrenadeGlyph({ type }: { type: GrenadeIconType }) {
  if (type === "smoke") return <g stroke="#26313d" strokeWidth="1.5" strokeLinejoin="round">
    <path d="M5 16C0 14 2 8 6 8C5 2 14 1 16 6C22 2 28 6 26 11C32 13 29 19 24 19H7Z" fill="#d4dae0" />
    <rect x="10" y="14" width="13" height="16" rx="3" fill="#8d9aa7" />
    <path d="M12 19H21M12 25H21M14 14V11H21" fill="none" />
  </g>;
  if (type === "molotov" || type === "incendiary") return <g stroke="#462b1b" strokeWidth="1.5" strokeLinejoin="round">
    <path d="M18 17C13 11 22 8 21 1C31 8 32 17 24 21Z" fill="#ff8b35" />
    <path d="M22 17C19 13 24 11 24 8C28 14 27 17 25 19Z" fill="#ffe296" stroke="none" />
    <path d="M10 8L16 10L14 16L16 22L12 30L3 26L7 18L10 15Z" fill="#829852" />
    <path d="M9 9L11 5L18 8L16 12M6 21L14 24" fill="#e6cf9c" />
  </g>;
  if (type === "flash" || type === "flashbang") return <g stroke="#6b5a21" strokeWidth="1.5" strokeLinejoin="round">
    <path d="M18 1L21 8L29 4L26 12L32 16L25 19L29 27L21 24L17 32L14 24L5 28L9 20L1 16L10 12L6 4L14 8Z" fill="#ffe58c" />
    <rect x="12" y="12" width="9" height="16" rx="2" fill="#fffbea" />
    <path d="M14 12V9H21M14 17H19M14 22H19" fill="none" />
  </g>;
  return <g stroke="#d5ddbd" strokeWidth="1.5" strokeLinejoin="round">
    <circle cx="23" cy="6" r="4" fill="none" />
    <path d="M13 10V5H20L24 15" fill="none" />
    <circle cx="15" cy="21" r="10" fill="#3f593b" />
    <path d="M7 17H23M6 23H24M12 12V30M18 12V30" stroke="#233b26" />
  </g>;
}

export default function GrenadeIcon({ type, size = 16 }: { type: GrenadeIconType; size?: number }) {
  return <svg className="grenade-icon" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
    <GrenadeGlyph type={type} />
  </svg>;
}
