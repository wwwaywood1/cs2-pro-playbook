import { useContext, useLayoutEffect, useRef } from "react";
import { fmtInt, fmtNum, fmtPct, fmtSeconds } from "../format";
import { MOTION_EASE, MOTION_TIMING, NumberEntrance, ReducedMotion } from "../motion";

export type NumberFormat = "number" | "integer" | "percent" | "seconds";
function formatNumber(value: number | null | undefined, format: NumberFormat): string {
  return format === "percent" ? fmtPct(value) : format === "integer" ? fmtInt(value) : format === "seconds" ? fmtSeconds(value) : fmtNum(value);
}
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
    const settling = entrance === "static" && lastEntrance.current !== "static";
    lastEntrance.current = entrance;
    if (reduced || settling || !/[0-9]/.test(final) || old === final || !node.animate) { previous.current = final; return; }
    const tracks = [...node.querySelectorAll<HTMLElement>(".hub-digit-track")];
    if (!tracks.length) return;
    node.dataset.rolling = "true";
    const animations = tracks.map((track, index) => {
      const position = Number(track.dataset.position);
      const start = Number(old[position + old.length - final.length]) || 0;
      const end = 20 + Number(final[position]);
      return track.animate([
        { transform: `translateY(${-start}em)` }, { transform: `translateY(${-end}em)` },
      ], { duration: MOTION_TIMING.count, delay: (typeof entrance === "number" ? entrance : 0) + index * MOTION_TIMING.digit, easing: MOTION_EASE, fill: "both" });
    });
    let cancelled = false;
    void Promise.all(animations.map((animation) => animation.finished)).then(() => {
      if (!cancelled) { previous.current = final; node.dataset.rolling = "false"; animations.forEach((animation) => animation.cancel()); }
    }, () => {});
    return () => {
      cancelled = true;
      if (node.dataset.rolling === "true") {
        const digits = Array.from(final);
        tracks.forEach((track, index) => {
          const position = Number(track.dataset.position);
          const start = Number(old[position + old.length - final.length]) || 0;
          const end = 20 + Number(final[position]);
          const progress = animations[index].effect?.getComputedTiming().progress ?? 0;
          digits[position] = String(Math.floor(start + (end - start) * progress) % 10);
        });
        previous.current = digits.join("");
      }
      animations.forEach((animation) => animation.cancel());
    };
  }, [value, final, reduced, entrance]);
  return <span className="hub-count" ref={visual} data-value={final} data-rolling="false">
    <span className="sr-only">{final}</span><span aria-hidden="true" className="hub-number-display">
      <span className="hub-number-final">{final}</span><span className="hub-number-reels">{Array.from(final).map((character, position) => /[0-9]/.test(character) ?
        <span className="hub-digit" key={position}><span className="hub-digit-track" data-position={position}>{Array.from({ length: 30 }, (_, digit) => <span key={digit}>{digit % 10}</span>)}</span></span> :
        <span key={position}>{character}</span>)}</span>
    </span>
  </span>;
}
