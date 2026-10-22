import { createContext, useContext, useState, type FocusEvent, type ReactNode } from "react";
import { t } from "./i18n";
import "./map-link.css";

type Target = { scope: string; id: string } | null;
type MapLink = {
  activeId: string | null;
  bind: (id: string) => {
    "data-map-link": string;
    "data-map-state": "active" | "dimmed" | undefined;
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onFocus: () => void;
    onBlur: (event: FocusEvent<Element>) => void;
  };
};
const MapLinks = createContext<MapLink | null>(null);

/** Pointer and keyboard focus coexist. Route changes invalidate stale targets without
 * remounting pages (the hub relies on keeping its slide transition state). */
export function MapLinkProvider({ scope, initialId = null, children }: { scope: string; initialId?: string | null; children: ReactNode }) {
  const [pointer, setPointer] = useState<Target>(null);
  const [focus, setFocus] = useState<Target>(null);
  const [latest, setLatest] = useState<"pointer" | "focus">("pointer");
  const pointerId = pointer?.scope === scope ? pointer.id : null;
  const focusId = focus?.scope === scope ? focus.id : null;
  const activeId = (latest === "focus" ? focusId ?? pointerId : pointerId ?? focusId) ?? initialId;
  const bind: MapLink["bind"] = (id) => ({
    "data-map-link": id,
    "data-map-state": activeId ? activeId === id ? "active" : "dimmed" : undefined,
    onMouseEnter: () => { setPointer({ scope, id }); setLatest("pointer"); },
    onMouseLeave: () => setPointer((current) => current?.scope === scope && current.id === id ? null : current),
    onFocus: () => { setFocus({ scope, id }); setLatest("focus"); },
    onBlur: (event) => {
      if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return;
      setFocus((current) => current?.scope === scope && current.id === id ? null : current);
    },
  });
  return <MapLinks.Provider value={{ activeId, bind }}>{children}</MapLinks.Provider>;
}

export function useMapLink() {
  const links = useContext(MapLinks);
  if (!links) throw new Error("useMapLink requires MapLinkProvider");
  return links;
}

export function MapLinkHint() {
  return <p className="map-link-hint muted">{t("round3.hover_hint")}</p>;
}
