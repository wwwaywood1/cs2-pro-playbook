import { useEffect, useState } from "react";

interface HeatmapCanvasProps {
  map: string;
  level: number;
  overlays: { key: string; url: string }[];
  markers?: { x: number; y: number; color: string; title: string }[];
}

export default function HeatmapCanvas({
  map, level, overlays, markers = [],
}: HeatmapCanvasProps) {
  const source = `${import.meta.env.BASE_URL}radars/${map}${level === 1 ? "_lower" : ""}.png`;
  const [failedSource, setFailedSource] = useState<string | null>(null);
  useEffect(() => setFailedSource(null), [source]);

  return (
    <svg className="hm-radar" viewBox="0 0 1024 1024" role="img" aria-label={map}>
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
      {markers.map((marker, index) => (
        <circle
          key={`${marker.title}:${index}`} cx={marker.x} cy={marker.y} r="12"
          fill="none" stroke={marker.color} strokeWidth="3"
        >
          <title>{marker.title}</title>
        </circle>
      ))}
    </svg>
  );
}
