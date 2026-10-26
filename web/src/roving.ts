import type { KeyboardEvent } from "react";

/**
 * One Tab stop per chart: the items of a chart share a roving tabindex and arrow keys move
 * between them (WAI-ARIA "roving tabindex"). Items carry data-roving={index}; only the
 * current one has tabIndex 0. Returns the new index, or null for keys it does not handle.
 */
export function moveRoving(event: KeyboardEvent<Element>, index: number, count: number): number | null {
  if (!count) return null;
  const next = event.key === "ArrowRight" || event.key === "ArrowDown" ? (index + 1) % count
    : event.key === "ArrowLeft" || event.key === "ArrowUp" ? (index - 1 + count) % count
      : event.key === "Home" ? 0 : event.key === "End" ? count - 1 : null;
  if (next === null) return null;
  event.preventDefault();
  event.stopPropagation();
  event.currentTarget.querySelector<HTMLElement | SVGElement>(`[data-roving="${next}"]`)?.focus();
  return next;
}
