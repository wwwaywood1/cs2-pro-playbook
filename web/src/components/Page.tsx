import { useRef, type HTMLAttributes } from "react";
import { ReducedMotion, useMotionPointer, useReducedMotion } from "../motion";
import { t } from "../i18n";
import CountUp from "./CountUp";
import { Stagger } from "./Motion";

export function PageSurface({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  const host = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  useMotionPointer(host, reduced);
  return <ReducedMotion.Provider value={reduced}><div {...props} ref={host} className={`site-page ${className}`} /></ReducedMotion.Provider>;
}
export function PageContext({ children }: { children: string }) { return <p className="page-context">{children}</p>; }
export function MetricStrip({ items }: { items: { label: string; value: number | null | undefined }[] }) {
  return <Stagger as="dl" className="key-strip">{items.map(({ label, value }) => <div key={label} data-motion-tilt><dt>{label}</dt><dd><CountUp value={value} format="integer" /></dd></div>)}</Stagger>;
}
export function SampleStrip({ matches, players, maps }: { matches?: number; players?: number; maps?: number }) {
  const items = [];
  if (matches !== undefined) items.push({ label: t("ui.matches_title"), value: matches });
  if (players !== undefined) items.push({ label: t("ui.nav_players"), value: players });
  if (maps !== undefined) items.push({ label: t("ui.nav_maps"), value: maps });
  return <MetricStrip items={items} />;
}
