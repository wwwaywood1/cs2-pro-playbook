import { useLayoutEffect, useRef, useState, type HTMLAttributes } from "react";

/** Shared single-choice track. Existing buttons retain their labels and URL actions. */
export default function Segmented({ children, className = "", onKeyDown, ...props }: HTMLAttributes<HTMLDivElement>) {
  const host = useRef<HTMLDivElement>(null);
  const [highlight, setHighlight] = useState({ x: 0, y: 0, width: 0, height: 0 });
  useLayoutEffect(() => {
    const element = host.current;
    if (!element) return;
    const measure = () => {
      const selected = element.querySelector<HTMLButtonElement>('button[aria-pressed="true"], button[aria-selected="true"]');
      const next = selected ? { x: selected.offsetLeft, y: selected.offsetTop, width: selected.offsetWidth, height: selected.offsetHeight } : { x: 0, y: 0, width: 0, height: 0 };
      setHighlight((old) => old.x === next.x && old.y === next.y && old.width === next.width && old.height === next.height ? old : next);
    };
    let frame = 0;
    let disposed = false;
    const schedule = () => {
      if (disposed) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(element);
    for (const button of element.querySelectorAll('button')) observer.observe(button);
    measure();
    // max-content tracks can move without resizing; fonts can change button
    // advances after the first layout. Recheck once the final layout is ready.
    schedule();
    void document.fonts.ready.then(schedule);
    document.fonts.addEventListener("loadingdone", schedule);
    window.addEventListener("resize", schedule);
    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.fonts.removeEventListener("loadingdone", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [children]);
  return <div role="group" {...props} ref={host} className={`segmented hud-segmented ${className}`} onKeyDown={(event) => {
    onKeyDown?.(event);
    if (event.defaultPrevented || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (index < 0 || !buttons.length) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus(); buttons[next].click();
  }}><span aria-hidden="true" className="segment-highlight" style={{ width: highlight.width, height: highlight.height, transform: `translate(${highlight.x}px, ${highlight.y}px)` }} />{children}</div>;
}
