import { useEffect, useState } from "react";
import { useMapLink } from "../mapLink";

export interface HeatmapMarker {
  id?: string;
  x: number;
  y: number;
  color: string;
  title: string;
  small?: boolean;
}

interface HeatmapCanvasProps {
  map: string;
  level: number;
  overlays: { key: string; url: string }[];
  markers?: HeatmapMarker[];
}

export default function HeatmapCanvas({
  map, level, overlays, markers = [],
}: HeatmapCanvasProps) {
  const source = `${import.meta.env.BASE_URL}radars/${map}${level === 1 ? "_lower" : ""}.png`;
  const [failedSource, setFailedSource] = useState<string | null>(null);
  useEffect(() => setFailedSource(null), [source]);

  return (
    <svg className="hm-radar" viewBox="0 0 1024 1024" role={markers.length ? "group" : "img"} aria-label={map}>
      <rect width="1024" height="1024" className="hm-radar-bg" />
      {failedSource !== source && (
        <image
          href={source} width="1024" height="1024"
          preserveAspectRatio="xMidYMid meet"
          onError={() => setFailedSource(source)}
        />
      )}
      {overlays.map((overlay) => (
        <image
          key={overlay.key} href={overlay.url} width="1024" height="1024"
          preserveAspectRatio="none" style={{ imageRendering: "auto" }}
        />
      ))}
      <HeatmapMarkers markers={markers} />
    </svg>
  );
}

export function HeatmapMarkers({ markers }: { markers: HeatmapMarker[] }) {
  const { bind } = useMapLink();
  return <>
      {markers.map((marker, index) => (
        <g key={`${marker.id ?? marker.title}:${index}`} {...(marker.id ? bind(marker.id) : {})}
          transform={`translate(${marker.x} ${marker.y})`} tabIndex={marker.id ? 0 : undefined} role="img" aria-label={marker.title}>
          <title>{marker.title}</title>
          <circle r="20" fill="transparent" />
          <circle className="map-link-ring" r="19" />
          <circle r={marker.small ? 5 : 12} fill={marker.small ? marker.color : "none"} stroke={marker.color} strokeWidth="3" />
          <text className="map-link-label" x="23" y="5">{marker.title}</text>
        </g>
      ))}
  </>;
}
