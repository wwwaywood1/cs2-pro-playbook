import type { CSSProperties } from "react";

export type TeamPalette = { primary: string; secondary: string; tertiary: string };
export const TEAM_PALETTES: Record<string, TeamPalette> = {
  falcons: { primary: "#2ecc71", secondary: "#e8b75a", tertiary: "#9aafc7" },
  vitality: { primary: "#f8cf55", secondary: "#bcb0f4", tertiary: "#9cb8cf" },
  spirit: { primary: "#8cdeb0", secondary: "#efb580", tertiary: "#a6b7d4" },
  "natus-vincere": { primary: "#f5d547", secondary: "#b9b4f6", tertiary: "#9cb8cf" },
  g2: { primary: "#a9b9f6", secondary: "#f0b58c", tertiary: "#9fc6cd" },
  mouz: { primary: "#ff9696", secondary: "#e8c780", tertiary: "#9cb8cf" },
  "the-mongolz": { primary: "#75c9e8", secondary: "#e8b75a", tertiary: "#b4b9cd" },
};
export const DEFAULT_PALETTE: TeamPalette = { primary: "#f2b134", secondary: "#e8b75a", tertiary: "#a6b7c9" };
// Preserve the hub's existing fallback for teams outside its curated table.
const UNKNOWN_TEAM_PALETTE: TeamPalette = { ...DEFAULT_PALETTE, secondary: "#a8ccf0" };

export function teamTheme(slug: string): CSSProperties {
  const palette = TEAM_PALETTES[slug] ?? (slug ? UNKNOWN_TEAM_PALETTE : DEFAULT_PALETTE);
  return { "--accent": palette.primary, "--primary": palette.primary, "--secondary": palette.secondary,
    "--tertiary": palette.tertiary } as CSSProperties;
}
