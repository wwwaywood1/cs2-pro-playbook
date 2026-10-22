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
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    for (const button of element.querySelectorAll('button')) observer.observe(button);
    measure();
    return () => observer.disconnect();
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
