import Num from "./Num";
import { useContext, useLayoutEffect, useRef } from "react";
import { fmtInt, fmtNum, fmtPct, fmtSeconds } from "../format";
import { MOTION_EASE, MOTION_TIMING, NumberEntrance, ReducedMotion } from "../motion";

export type NumberFormat = "number" | "integer" | "percent" | "seconds";
function formatNumber(value: number | null | undefined, format: NumberFormat): string {
  return format === "percent" ? fmtPct(value) : format === "integer" ? fmtInt(value) : format === "seconds" ? fmtSeconds(value) : fmtNum(value);
}
/** Reveal the complete final number; no rolling tracks or clipped glyphs. */
export default function CountUp({ value, text, format = "number" }: { value?: number | null; text?: string; format?: NumberFormat }) {
  const reduced = useContext(ReducedMotion);
  const entrance = useContext(NumberEntrance);
  const visual = useRef<HTMLSpanElement>(null);
  const previous = useRef("");
  const lastEntrance = useRef(entrance);
  const final = text ?? formatNumber(value, format);
  useLayoutEffect(() => {
    const node = visual.current;
    if (!node) return;
    node.dataset.rolling = "false";
    const old = previous.current;
    previous.current = final;
    const settling = entrance === "static" && lastEntrance.current !== "static";
    lastEntrance.current = entrance;
    const number = node.querySelector<HTMLElement>(".hub-number-final");
    if (reduced || settling || !/[0-9]/.test(final) || old === final || !number?.animate) return;
    node.dataset.rolling = "true";
    const animation = number.animate([
      { opacity: 0, filter: "blur(5px)", transform: "translateY(.08em)" },
      { opacity: 1, filter: "blur(0px)", transform: "translateY(0)" },
    ], { duration: MOTION_TIMING.count, delay: typeof entrance === "number" ? entrance : 0, easing: MOTION_EASE, fill: "both" });
    let cancelled = false;
    void animation.finished.then(() => {
      if (!cancelled) { node.dataset.rolling = "false"; animation.cancel(); }
    }, () => {});
    return () => { cancelled = true; animation.cancel(); node.dataset.rolling = "false"; };
  }, [final, reduced, entrance]);
  return <span className="hub-count" ref={visual} data-value={final} data-rolling="false">
    <span className="sr-only">{final}</span><span aria-hidden="true" className="hub-number-display"><span className="hub-number-final"><Num value={final} /></span></span>
  </span>;
}
