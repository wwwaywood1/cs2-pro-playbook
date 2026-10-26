import { useLayoutEffect, useRef } from "react";
import { useLocation, useOutlet } from "react-router-dom";
import { ReducedMotion, useReducedMotion } from "../motion";
import ErrorBoundary from "./ErrorBoundary";

export default function RouteTransition() {
  const { pathname, search } = useLocation();
  const outlet = useOutlet();
  const reduced = useReducedMotion();
  const previous = useRef(pathname);
  useLayoutEffect(() => {
    if (previous.current === pathname) return;
    previous.current = pathname;
    document.getElementById("main-content")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  // Commit the new outlet immediately. Retaining the outgoing tree would let its
  // useSearchParams effects rewrite the destination URL during a delayed exit.
  // Only pathname changes restart the short CSS fade/slide; filters stay mounted.
  // A failing page is contained here, so the nav, footer and palette stay usable;
  // the replay overlay is not part of the route and is not reset by this boundary.
  const routeKey = `${pathname}?${new URLSearchParams(search).toString().replace(/(^|&)replay=[^&]*/g, "")}`;
  return <ReducedMotion.Provider value={reduced}><div key={pathname} className="route-scene">
    <ErrorBoundary resetKey={routeKey}>{outlet}</ErrorBoundary>
  </div></ReducedMotion.Provider>;
}
