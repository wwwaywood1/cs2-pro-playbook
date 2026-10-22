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
const UNKNOWN_TEAM_PALETTE: TeamPalette = { primary: "#d4e4f4", secondary: "#e2e8ee", tertiary: "#a6b7c9" };

export function teamTheme(slug: string): CSSProperties {
  const palette = TEAM_PALETTES[slug] ?? (slug ? UNKNOWN_TEAM_PALETTE : DEFAULT_PALETTE);
  return { "--accent": palette.primary, "--primary": palette.primary, "--secondary": slug ? "#e2e8ee" : palette.secondary,
    "--tertiary": slug ? "#a6b7c9" : palette.tertiary,
    ...(slug ? { "--side-t": "#e2e8ee", "--side-ct": "#a6b7c9", "--ct": "#a6b7c9" } : {}) } as CSSProperties;
}
