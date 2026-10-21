import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

/** One delegated, idle-free spring loop; React never rerenders on pointer movement. */
export function useHubPointer(host: RefObject<HTMLDivElement>, reduced: boolean) {
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
      resetCard(); resetStage(); set(panel, { "--spot-alpha": 0 });
      card = stage = panel = null;
    };
    const move = (event: PointerEvent) => {
      if (!fine.matches || event.pointerType !== "mouse") return;
      const target = event.target instanceof Element ? event.target : null;
      const nextCard = target?.closest<HTMLElement>(".hub-map-card, .hub-player-card, .hub-kpis .stat, .hub-primary") ?? null;
      const nextStage = target?.closest<HTMLElement>("[data-hub-parallax]") ?? null;
      const nextPanel = target?.closest<HTMLElement>(".hub-player-bio, .hub-panel") ?? null;
      if (nextCard !== card) { resetCard(); card = nextCard; }
      if (nextStage !== stage) { resetStage(); stage = nextStage; }
      if (nextPanel !== panel) { set(panel, { "--spot-alpha": 0 }); panel = nextPanel; }
      if (card) {
        const rect = card.getBoundingClientRect();
        const x = Math.max(-1, Math.min(1, (event.clientX - rect.left) / rect.width * 2 - 1));
        const y = Math.max(-1, Math.min(1, (event.clientY - rect.top) / rect.height * 2 - 1));
        const magnetic = card.classList.contains("hub-primary");
        set(card, { "--tilt-h": x * 4, "--tilt-v": -y * 4, "--shine-x": (x + 1) * 50, "--shine-y": (y + 1) * 50,
          "--shine-alpha": 1, "--magnet-h": magnetic ? x * 8 : 0, "--magnet-v": magnetic ? y * 8 : 0 });
      }
      if (stage) {
        const rect = stage.getBoundingClientRect();
        set(stage, { "--depth-h": ((event.clientX - rect.left) / rect.width * 2 - 1) * 12,
          "--depth-v": ((event.clientY - rect.top) / rect.height * 2 - 1) * 12 });
      }
      if (panel) {
        const rect = panel.getBoundingClientRect();
        set(panel, { "--spot-x": (event.clientX - rect.left) / rect.width * 100,
          "--spot-y": (event.clientY - rect.top) / rect.height * 100, "--spot-alpha": 1 });
      }
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

type PortraitOrigin = { rect: DOMRect; src: string; time: number };
let origin: PortraitOrigin | undefined;
export function rememberPortrait(button: HTMLButtonElement, reduced: boolean) {
  origin = undefined;
  const image = button.querySelector<HTMLImageElement>(".hub-portrait img");
  if (!reduced && image?.complete && image.naturalWidth) origin = { rect: image.getBoundingClientRect(), src: image.currentSrc, time: performance.now() };
}

const seenPlayers = new Set<string>();
function hasSeen(id: string) {
  try { return seenPlayers.has(id) || sessionStorage.getItem(`hub-intro:${id}`) === "1"; }
  catch { return seenPlayers.has(id); }
}
function markSeen(id: string) {
  seenPlayers.add(id);
  try { sessionStorage.setItem(`hub-intro:${id}`, "1"); } catch { /* In-memory fallback. */ }
}

/** Input skips choreography without swallowing navigation, focus, or control actions. */
export function usePlayerEntrance(id: string, reduced: boolean, host: RefObject<HTMLDivElement>) {
  const [entrance, setEntrance] = useState<"full" | "short" | "settled">(() => reduced ? "settled" : hasSeen(id) ? "short" : "full");
  const skip = () => {
    if (document.activeElement?.classList.contains("hub-intro-skip")) host.current?.querySelector<HTMLElement>("#hub-heading")?.focus();
    setEntrance("settled");
  };
  useEffect(() => {
    markSeen(id);
    if (reduced) { setEntrance("settled"); return; }
    if (entrance === "settled") return;
    const timer = window.setTimeout(skip, entrance === "full" ? 2500 : 600);
    window.addEventListener("click", skip, true);
    window.addEventListener("keydown", skip, true);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("click", skip, true);
      window.removeEventListener("keydown", skip, true);
    };
  }, [id, entrance, reduced]);
  const transfer = useRef(origin);
  useLayoutEffect(() => {
    const from = transfer.current;
    if (origin === from) origin = undefined;
    if (reduced) transfer.current = undefined;
    const portrait = host.current?.querySelector<HTMLElement>(".hub-portrait-motion");
    if (reduced || !from || performance.now() - from.time > 2000 || !portrait || !portrait.animate) return;
    // offset geometry excludes the route entrance transform, unlike client rects.
    let left = -window.scrollX;
    let top = -window.scrollY;
    let element: HTMLElement | null = portrait;
    while (element) { left += element.offsetLeft; top += element.offsetTop; element = element.offsetParent as HTMLElement | null; }
    const to = { left, top, width: portrait.offsetWidth, height: portrait.offsetHeight };
    if (!to.width || !to.height) return;
    // Transform-based FLIP of the same transparent asset; the real portrait sits beneath it.
    const ghost = document.createElement("img");
    ghost.src = from.src;
    ghost.alt = "";
    ghost.setAttribute("aria-hidden", "true");
    ghost.className = "hub-portrait-transfer";
    Object.assign(ghost.style, { position: "fixed", pointerEvents: "none", zIndex: "1000", objectFit: "contain",
      left: `${to.left}px`, top: `${to.top}px`, width: `${to.width}px`, height: `${to.height}px`, transformOrigin: "0 0" });
    document.body.append(ghost);
    const animation = ghost.animate([
      { transform: `translate(${from.rect.left - to.left}px, ${from.rect.top - to.top}px) scale(${from.rect.width / to.width}, ${from.rect.height / to.height})`, opacity: 1 },
      { transform: "translate(0, 0) scale(1)", opacity: 1, offset: .8 },
      { transform: "translate(0, 0) scale(1)", opacity: 0 },
    ], { duration: 600, easing: "cubic-bezier(.2,.8,.2,1)", fill: "both" });
    const remove = () => { animation.cancel(); ghost.remove(); };
    const finish = () => { transfer.current = undefined; remove(); };
    void animation.finished.then(finish, () => ghost.remove());
    window.addEventListener("pointerdown", finish, true);
    window.addEventListener("click", finish, true);
    window.addEventListener("keydown", finish, true);
    window.addEventListener("scroll", finish, true);
    window.addEventListener("resize", finish);
    return () => {
      remove();
      window.removeEventListener("pointerdown", finish, true);
      window.removeEventListener("click", finish, true);
      window.removeEventListener("keydown", finish, true);
      window.removeEventListener("scroll", finish, true);
      window.removeEventListener("resize", finish);
    };
  }, [host, reduced]);
  return { entrance, skip };
}
