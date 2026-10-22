import type { ReactNode } from "react";

/** Keep formatted numbers intact while reducing the visual weight of their unit. */
export default function Num({ value, unit }: { value: ReactNode; unit?: string }) {
  const match = !unit && typeof value === "string" ? value.match(/^([+−-]?[\d,.]+)\s*(%|s|秒|回合)$/u) : null;
  return <span className="hud-num">{match ? match[1] : value}{unit || match ? <span className="hud-unit">{unit ?? match?.[2]}</span> : null}</span>;
}
