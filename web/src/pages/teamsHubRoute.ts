import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";

type Route = { team: string; map: string; player: string };
type Transition = { ready: Promise<void>; finished: Promise<void>; skipTransition(): void };
type TransitionDocument = Document & { startViewTransition?: (update: () => void) => Transition };
const keyOf = (route: Route) => JSON.stringify([route.team, route.map, route.player]);

/** Snapshot only the whole scene; no shared logo/title transfers or delayed exit. */
export function useHubRoute(route: Route, reduced: boolean) {
  const key = keyOf(route);
  const [shown, setShown] = useState({ route, key, native: false });
  const host = useRef<HTMLDivElement>(null);
  const running = useRef<Transition | null>(null);
  useEffect(() => () => running.current?.skipTransition(), []);
  useLayoutEffect(() => {
    if (key === shown.key) return;
    running.current?.skipTransition();
    const doc = document as TransitionDocument;
    let cancelled = false, committed = false;
    const reveal = (native: boolean) => {
      if (!cancelled) { committed = true; setShown({ route, key, native }); }
    };
    if (!reduced && doc.startViewTransition) {
      const transition = doc.startViewTransition(() => flushSync(() => reveal(true)));
      running.current = transition;
      void transition.ready.catch(() => {});
      void transition.finished.catch(() => {});
      return () => { if (!committed) { cancelled = true; transition.skipTransition(); } };
    }
    // Unsupported browsers commit the destination before a short opacity entrance.
    reveal(false);
  }, [key, shown.key, reduced]);
  useLayoutEffect(() => {
    const node = host.current;
    if (reduced || shown.native || !node?.animate) return;
    const animation = node.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: "linear" });
    return () => animation.cancel();
  }, [shown.key, shown.native, reduced]);
  return { route: shown.route, host };
}
