import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { MOTION_EASE } from "../motion";

type Route = { team: string; map: string; player: string };
type Transition = { finished: Promise<void>; ready: Promise<void>; skipTransition(): void };
type TransitionDocument = Document & { startViewTransition?: (update: () => void) => Transition };
const keyOf = (route: Route) => JSON.stringify([route.team, route.map, route.player]);
const depth = (route: Route) => route.player ? 3 : route.map ? 2 : route.team ? 1 : 0;

/** Observe the router, so browser history gets the same transition as clicks/Escape. */
export function useHubRoute(route: Route, reduced: boolean) {
  const key = keyOf(route);
  const [shown, setShown] = useState({ route, key, direction: 1, shared: false });
  const host = useRef<HTMLDivElement>(null);
  const returnMap = useRef(route.map);
  const running = useRef<Transition | null>(null);
  useEffect(() => () => running.current?.skipTransition(), []);
  if (route.map) returnMap.current = route.map;
  useLayoutEffect(() => {
    if (key === shown.key) return;
    running.current?.skipTransition();
    const direction = depth(route) < depth(shown.route) ? -1 : 1;
    const doc = document as TransitionDocument;
    const shared = !!doc.startViewTransition && !reduced && route.team === shown.route.team && !!route.team
      && !route.player && !shown.route.player && !!route.map !== !!shown.route.map;
    let cancelled = false;
    const reveal = () => { if (!cancelled) setShown({ route, key, direction, shared }); };
    if (shared) {
      host.current?.style.setProperty("view-transition-name", "team-hub-stage");
      const node = document.getElementById(`hub-map-${route.map || shown.route.map}`);
      node?.style.setProperty("view-transition-name", "team-map-header");
      let committed = false;
      const transition = doc.startViewTransition!(() => { committed = true; flushSync(reveal); });
      running.current = transition;
      // A newer route can supersede a pending snapshot. A skipped animation is
      // harmless; never leave a rejected ready promise or a stale route behind.
      void transition.ready.catch(() => {});
      void transition.finished.catch(() => {});
      return () => { cancelled = true; if (!committed) transition.skipTransition(); };
    }
    const element = host.current;
    if (reduced || !element?.animate) { reveal(); return; }
    const animation = element.animate([
      { opacity: 1, transform: "translateX(0) scale(1)", filter: "blur(0px)" },
      { opacity: 0, transform: `translateX(${-direction * 48}px) scale(.985)`, filter: "blur(8px)" },
    ], { duration: 320, easing: MOTION_EASE, fill: "forwards" });
    void animation.finished.then(reveal, () => {});
    return () => { cancelled = true; animation.cancel(); };
  }, [key, shown.key, reduced]);
  return { ...shown, host, returnMap: returnMap.current };
}
