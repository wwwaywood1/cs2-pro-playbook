import { useLayoutEffect, useRef } from "react";
import { useLocation, useOutlet } from "react-router-dom";
import { ReducedMotion, useReducedMotion } from "../motion";

export default function RouteTransition() {
  const { pathname } = useLocation();
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
  return <ReducedMotion.Provider value={reduced}><div key={pathname} className="route-scene">
    {outlet}
  </div></ReducedMotion.Provider>;
}
