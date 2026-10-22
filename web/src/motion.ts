import { createContext, useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

export const MOTION_QUERY = "(prefers-reduced-motion: reduce)";
export const ReducedMotion = createContext(false);
export const NumberEntrance = createContext<number | "static">(0);
export const MOTION_EASE = "cubic-bezier(.2,.8,.2,1)";
export const MOTION_TIMING = { exit: 320, count: 560, digit: 22 };

/** Check at the action, so a live preference change also affects imperative scrolls. */
export function motionScrollBehavior(): ScrollBehavior {
  return window.matchMedia(MOTION_QUERY).matches ? "instant" : "smooth";
}

export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia(MOTION_QUERY).matches);
  useEffect(() => {
    const query = window.matchMedia(MOTION_QUERY);
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return reduced;
}

/** Retain the outgoing tree until its exit finishes; latest destination wins. */
export function useMotionRoute<T>(route: T, key: string, reduced: boolean,
  direction: (next: T, previous: T) => number = forward, duration = MOTION_TIMING.exit) {
  const [shown, setShown] = useState({ route, key, direction: 1 });
  const host = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (key === shown.key) return;
    const sign = direction(route, shown.route);
    const reveal = () => setShown({ route, key, direction: sign });
    const element = host.current;
    if (reduced || !element?.animate) { reveal(); return; }
    let cancelled = false;
    const animation = element.animate([
      { opacity: 1, transform: "translateX(0) scale(1)", filter: "blur(0px)" },
      { opacity: 0, transform: `translateX(${-sign * 48}px) scale(.985)`, filter: "blur(8px)" },
    ], { duration, easing: MOTION_EASE, fill: "forwards" });
    void animation.finished.then(() => { if (!cancelled) reveal(); }, () => {});
    return () => { cancelled = true; animation.cancel(); };
    // Same-key query/locale changes must not restart a pending route exit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, shown.key, reduced, direction, duration]);
  return { ...shown, host };
}
function forward() { return 1; }

/** One delegated, idle-free spring loop; React never rerenders on pointer movement. */
export function useMotionPointer(host: RefObject<HTMLElement>, reduced: boolean) {
  useEffect(() => {
    const root = host.current;
    if (!root || reduced) return;
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    type Spring = { value: number; target: number; velocity: number };
    const springs = new Map<HTMLElement, Map<string, Spring>>();
    let frame = 0;
    let last = 0;
    let card: HTMLElement | null = null;
    let stage: HTMLElement | null = null;
    let panel: HTMLElement | null = null;
    let pointerFrame = 0;
    let pointer: { target: Element | null; x: number; y: number } | null = null;
    const tick = (time: number) => {
      const dt = Math.min((time - (last || time - 16)) / 1000, .032);
      last = time;
      let moving = false;
      for (const [element, values] of springs) {
        if (!element.isConnected) { springs.delete(element); continue; }
        for (const [name, spring] of values) {
          spring.velocity += ((spring.target - spring.value) * 190 - spring.velocity * 25) * dt;
          spring.value += spring.velocity * dt;
          const active = Math.abs(spring.target - spring.value) > .005 || Math.abs(spring.velocity) > .005;
          if (!active) { spring.value = spring.target; spring.velocity = 0; }
          moving ||= active;
          element.style.setProperty(name, String(spring.value));
        }
      }
      frame = moving ? requestAnimationFrame(tick) : 0;
      if (!frame) last = 0;
    };
    const set = (element: HTMLElement | null, values: Record<string, number>) => {
      if (!element) return;
      let entry = springs.get(element);
      if (!entry) { entry = new Map(); springs.set(element, entry); }
      for (const [name, target] of Object.entries(values)) {
        const spring = entry.get(name);
        if (spring) spring.target = target;
        else entry.set(name, { value: name.endsWith("-x") || name.endsWith("-y") ? 50 : 0, target, velocity: 0 });
      }
      if (!frame) frame = requestAnimationFrame(tick);
    };
    const resetCard = () => set(card, { "--tilt-h": 0, "--tilt-v": 0, "--magnet-h": 0, "--magnet-v": 0, "--shine-alpha": 0 });
    const resetStage = () => set(stage, { "--depth-h": 0, "--depth-v": 0 });
    const leave = () => {
      cancelAnimationFrame(pointerFrame);
      pointerFrame = 0;
      pointer = null;
      resetCard(); resetStage(); set(panel, { "--spot-alpha": 0 });
      card = stage = panel = null;
    };
    const updatePointer = () => {
      pointerFrame = 0;
      if (!pointer) return;
      const { target, x: clientX, y: clientY } = pointer;
      pointer = null;
      if (!target?.isConnected) { leave(); return; }
      const nextCard = target?.closest<HTMLElement>("[data-motion-tilt], .hub-map-card, .hub-player-card, .hub-kpis .stat, .hub-primary") ?? null;
      const nextStage = target?.closest<HTMLElement>("[data-motion-parallax], [data-hub-parallax]") ?? null;
      const nextPanel = target?.closest<HTMLElement>("[data-motion-spotlight], .hub-player-bio, .hub-panel") ?? null;
      // Read each box once, together, before changing any style or spring target.
      const rects = new Map<HTMLElement, DOMRect>();
      for (const element of [nextCard, nextStage, nextPanel]) {
        if (element && !rects.has(element)) rects.set(element, element.getBoundingClientRect());
      }
      if (nextCard !== card) { resetCard(); card = nextCard; }
      if (nextStage !== stage) { resetStage(); stage = nextStage; }
      if (nextPanel !== panel) { set(panel, { "--spot-alpha": 0 }); panel = nextPanel; }
      if (card) {
        const rect = rects.get(card)!;
        const x = Math.max(-1, Math.min(1, (clientX - rect.left) / (rect.width || 1) * 2 - 1));
        const y = Math.max(-1, Math.min(1, (clientY - rect.top) / (rect.height || 1) * 2 - 1));
        const magnetic = card.classList.contains("hub-primary");
        set(card, { "--tilt-h": x * 4, "--tilt-v": -y * 4, "--shine-x": (x + 1) * 50, "--shine-y": (y + 1) * 50,
          "--shine-alpha": 1, "--magnet-h": magnetic ? x * 8 : 0, "--magnet-v": magnetic ? y * 8 : 0 });
      }
      if (stage) {
        const rect = rects.get(stage)!;
        set(stage, { "--depth-h": ((clientX - rect.left) / (rect.width || 1) * 2 - 1) * 12,
          "--depth-v": ((clientY - rect.top) / (rect.height || 1) * 2 - 1) * 12 });
      }
      if (panel) {
        const rect = rects.get(panel)!;
        set(panel, { "--spot-x": (clientX - rect.left) / (rect.width || 1) * 100,
          "--spot-y": (clientY - rect.top) / (rect.height || 1) * 100, "--spot-alpha": 1 });
      }
    };
    const move = (event: PointerEvent) => {
      if (!fine.matches || event.pointerType !== "mouse") return;
      pointer = { target: event.target instanceof Element ? event.target : null, x: event.clientX, y: event.clientY };
      if (!pointerFrame) pointerFrame = requestAnimationFrame(updatePointer);
    };
    const visibility = () => { if (document.hidden) leave(); };
    root.addEventListener("pointermove", move, { passive: true });
    root.addEventListener("pointerleave", leave);
    root.addEventListener("pointercancel", leave);
    window.addEventListener("blur", leave);
    document.addEventListener("visibilitychange", visibility);
    fine.addEventListener("change", leave);
    return () => {
      cancelAnimationFrame(frame);
      cancelAnimationFrame(pointerFrame);
      root.removeEventListener("pointermove", move);
      root.removeEventListener("pointerleave", leave);
      root.removeEventListener("pointercancel", leave);
      window.removeEventListener("blur", leave);
      document.removeEventListener("visibilitychange", visibility);
      fine.removeEventListener("change", leave);
      for (const [element, values] of springs) for (const name of values.keys()) element.style.removeProperty(name);
    };
  }, [host, reduced]);
}

