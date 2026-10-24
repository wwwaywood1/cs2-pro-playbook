import { useLayoutEffect, useRef, type RefObject } from "react";
import { orbitLayout } from "./teamsHubOrbit";

const TARGET_OMEGA = .00012;

/** Sole owner of node geometry and ray endpoints, including static/resize paints. */
export function useOrbitalPhysicsEngine(host: RefObject<HTMLDivElement>, paused: boolean, reduced: boolean) {
  const phase = useRef(0);
  const velocity = useRef(TARGET_OMEGA);
  const brake = useRef(paused);
  const wake = useRef<() => void>(() => {});
  useLayoutEffect(() => { brake.current = paused; wake.current(); }, [paused]);
  useLayoutEffect(() => {
    const stage = host.current;
    if (!stage) return;
    const nodes = [...stage.querySelectorAll<HTMLElement>(".hub-orbit-node")];
    const rays = stage.querySelector<SVGSVGElement>(".hub-orbit-rays");
    const lines = nodes.map((_, index) => [...stage.querySelectorAll<SVGLineElement>(`.hub-orbit-rays g:nth-child(${index + 1}) line`)]);
    const mobile = window.matchMedia("(max-width: 899px)");
    let visible = true, frame = 0;
    let previous: number | undefined;
    let size = { width: 0, height: 0, nodes: nodes.map(() => ({ width: 0, height: 0 })) };
    const paint = () => {
      const { points } = orbitLayout(size.width, size.height, size.nodes, reduced ? 0 : phase.current);
      rays?.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
      nodes.forEach((node, index) => {
        const point = points[index];
        node.style.setProperty("--orbit-x", `${point.x}px`);
        node.style.setProperty("--orbit-y", `${point.y}px`);
        node.style.setProperty("--orbit-depth", String(point.scale));
        const dx = point.x - size.width / 2, dy = point.y - size.height / 2;
        const distance = Math.max(1, Math.hypot(dx, dy));
        lines[index].forEach((line) => {
          line.setAttribute("x1", String(size.width / 2 + dx / distance * 120));
          line.setAttribute("y1", String(size.height / 2 + dy / distance * 120));
          line.setAttribute("x2", String(point.x));
          line.setAttribute("y2", String(point.y));
        });
      });
      stage.dataset.phase = String(reduced ? 0 : phase.current);
      stage.dataset.omega = String(reduced ? 0 : velocity.current);
    };
    const allowed = () => !reduced && !document.hidden && visible && !mobile.matches;
    const tick = (time: number) => {
      frame = 0;
      if (!allowed()) { sync(); return; }
      const dt = previous == null ? 16.667 : Math.max(0, Math.min(50, time - previous));
      previous = time;
      const target = brake.current ? 0 : TARGET_OMEGA;
      // Time-normalised damping is identical on 60/120/144Hz displays.
      velocity.current += (target - velocity.current) * (1 - Math.pow(.92, dt / 16.667));
      if (brake.current && velocity.current < .0000005) velocity.current = 0;
      phase.current = (phase.current + velocity.current * dt) % (2 * Math.PI);
      paint();
      if (!brake.current || velocity.current) frame = requestAnimationFrame(tick);
      else stage.dataset.running = "false";
    };
    const sync = () => {
      paint();
      const running = allowed() && (!brake.current || velocity.current > 0);
      stage.dataset.running = String(running);
      if (running) {
        // Repeated observer deliveries must not reset an already running clock.
        if (!frame) frame = requestAnimationFrame(tick);
      } else {
        cancelAnimationFrame(frame);
        frame = 0; previous = undefined;
      }
    };
    const measure = () => {
      // Layout sizes exclude depth/hover transforms; reserve a pixel for rounding.
      size = { width: stage.clientWidth, height: stage.clientHeight,
        nodes: nodes.map(node => ({ width: node.offsetWidth + 1, height: node.offsetHeight + 1 })) };
      sync();
    };
    const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync(); });
    const resize = new ResizeObserver(measure);
    resize.observe(stage);
    nodes.forEach(node => resize.observe(node));
    observer.observe(stage);
    wake.current = sync;
    measure();
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("resize", measure);
    mobile.addEventListener("change", measure);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resize.disconnect();
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("resize", measure);
      mobile.removeEventListener("change", measure);
      wake.current = () => {};
    };
  }, [host, reduced]);
}
