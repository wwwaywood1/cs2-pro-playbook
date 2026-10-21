import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";

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
  // Refresh the native-pixel cap after zoom or moving between different-DPR screens.
  // Run before the transfer effect measures its destination.
  useLayoutEffect(() => {
    const root = host.current;
    if (!root) return;
    let resolution: MediaQueryList | undefined;
    const update = () => {
      resolution?.removeEventListener("change", update);
      const dpr = window.devicePixelRatio || 1;
      root.style.setProperty("--hub-dpr", String(dpr));
      resolution = window.matchMedia(`(resolution: ${dpr}dppx)`);
      resolution.addEventListener("change", update);
    };
    update();
    window.addEventListener("resize", update);
    return () => {
      resolution?.removeEventListener("change", update);
      window.removeEventListener("resize", update);
      root.style.removeProperty("--hub-dpr");
    };
  }, [host]);
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
