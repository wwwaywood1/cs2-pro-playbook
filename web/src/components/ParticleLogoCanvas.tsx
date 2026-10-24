import { useEffect, useRef, useState } from "react";
import { assetUrl } from "../data";
import { teamPalette } from "../theme";
import TeamShield from "./TeamShield";
import "./particle-logo.css";

const LOGO_SIZE = 168;
const CANVAS_SIZE = 220;
const INSET = (CANVAS_SIZE - LOGO_SIZE) / 2;
const CORE_LIMIT = 1880;
const DUST_COUNT = 20;

type Particle = { x: number; y: number; radius: number; phase: number; color: string };
type Props = { slug: string; name: string; available: boolean };

/** Samples the supplied team PNG; the real image/shield remains the static fallback. */
export default function ParticleLogoCanvas({ slug, name, available }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const host = useRef<HTMLSpanElement>(null);
  const pointer = useRef<{ x: number; y: number } | null>(null);
  const [failedSource, setFailedSource] = useState("");
  const [animated, setAnimated] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const source = assetUrl(`logos/teams/${slug}.png`);
  const supplied = available && failedSource !== source;

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  useEffect(() => {
    setAnimated(false);
    const node = canvas.current;
    const container = host.current;
    if (!node || !container) return;
    node.dataset.sampledSource = "";
    node.dataset.samplingDone = "false";
    node.dataset.paused = "true";
    node.dataset.particleCount = "0";
    if (!supplied || reduced) return;
    const context = node.getContext("2d");
    if (!context) return;
    const dpr = Math.min(2, Math.max(1, window.devicePixelRatio || 1));
    node.width = CANVAS_SIZE * dpr;
    node.height = CANVAS_SIZE * dpr;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);
    const palette = teamPalette(slug);
    // Spirit's supplied mark is white. Keep each other team in its primary hue.
    const primary = slug === "spirit" ? "#f8fafc" : palette.primary;
    const rgb = primary.slice(1).match(/../g)!.map(value => parseInt(value, 16));
    const tint = () => {
      const luminance = .86 + Math.random() * .24;
      return `rgb(${rgb.map(value => Math.round(luminance > 1 ? value + (255 - value) * (luminance - 1) : value * luminance)).join(",")})`;
    };
    let particles: Particle[] = [];
    let frame = 0;
    let elapsed = 0;
    let previousTime = 0;
    let visible = false;
    let disposed = false;
    let loaded = false;

    const draw = (time: number) => {
      frame = 0;
      if (disposed || document.hidden || !visible || !loaded) return;
      elapsed += previousTime ? Math.min(50, time - previousTime) : 0;
      previousTime = time;
      context.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
      for (const particle of particles) {
        let x = particle.x + Math.sin(elapsed * 0.0009 + particle.phase) * .65;
        let y = particle.y + Math.cos(elapsed * 0.0007 + particle.phase) * .65;
        if (pointer.current) {
          const dx = x - pointer.current.x;
          const dy = y - pointer.current.y;
          const distance = Math.hypot(dx, dy);
          if (distance > 0 && distance < 45) {
            const force = (1 - distance / 45) * 2;
            x += dx / distance * force;
            y += dy / distance * force;
          }
        }
        context.fillStyle = particle.color;
        context.globalAlpha = .65 + Math.sin(elapsed * .001 + particle.phase) * .12;
        context.beginPath();
        context.arc(x, y, particle.radius, 0, Math.PI * 2);
        context.fill();
      }
      for (let index = 0; index < DUST_COUNT; index++) {
        const progress = (elapsed * 0.00006 + index / DUST_COUNT) % 1;
        const angle = index * 2.39996 + elapsed * 0.000025;
        const radius = 70 + progress * 35;
        context.fillStyle = primary;
        context.globalAlpha = (1 - progress) * .16;
        context.beginPath();
        context.arc(110 + Math.cos(angle) * radius, 110 + Math.sin(angle) * radius, .6 + (index % 3) * .2, 0, Math.PI * 2);
        context.fill();
      }
      context.globalAlpha = 1;
      frame = window.requestAnimationFrame(draw);
    };
    const syncAnimation = () => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      previousTime = 0;
      node.dataset.paused = String(document.hidden || !visible || !loaded);
      if (!disposed && !document.hidden && visible && loaded) frame = window.requestAnimationFrame(draw);
    };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      syncAnimation();
    });
    observer.observe(container);
    document.addEventListener("visibilitychange", syncAnimation);
    const image = new Image();
    image.onload = () => {
      if (disposed) return;
      const sample = document.createElement("canvas");
      sample.width = sample.height = LOGO_SIZE;
      const sampling = sample.getContext("2d", { willReadFrequently: true });
      if (!sampling) return;
      const scale = Math.min(LOGO_SIZE / image.naturalWidth, LOGO_SIZE / image.naturalHeight);
      const width = image.naturalWidth * scale;
      const height = image.naturalHeight * scale;
      sampling.drawImage(image, (LOGO_SIZE - width) / 2, (LOGO_SIZE - height) / 2, width, height);
      try {
        const pixels = sampling.getImageData(0, 0, LOGO_SIZE, LOGO_SIZE).data;
        type Point = { x: number; y: number };
        const edges: Point[] = [], interior: Point[] = [];
        const opaque = (x: number, y: number) => x >= 0 && y >= 0 && x < LOGO_SIZE && y < LOGO_SIZE && pixels[(y * LOGO_SIZE + x) * 4 + 3] > 80;
        for (let y = 0; y < LOGO_SIZE; y++) {
          for (let x = 0; x < LOGO_SIZE; x++) {
            if (!opaque(x, y)) continue;
            const point = { x: x + INSET, y: y + INSET };
            const edge = !opaque(x - 2, y) || !opaque(x + 2, y) || !opaque(x, y - 2) || !opaque(x, y + 2);
            if (edge && (x + y) % 2 === 0) edges.push(point);
            else if (x % 3 === 0 && y % 3 === 0) interior.push(point);
          }
        }
        const pick = (points: Point[], limit: number) => {
          const count = Math.min(limit, points.length);
          return Array.from({ length: count }, (_, index) => points[Math.floor(index * points.length / count)]);
        };
        const edgePoints = pick(edges, Math.max(CORE_LIMIT - interior.length, Math.floor(CORE_LIMIT * .65)));
        const points = [...edgePoints, ...pick(interior, CORE_LIMIT - edgePoints.length)];
        const count = points.length;
        particles = points.map(point => ({
          ...point, radius: .8 + Math.random() * .6, phase: Math.random() * Math.PI * 2,
          color: tint(),
        }));
        if (!count) return;
        node.dataset.particleCount = String(count + DUST_COUNT);
        loaded = true;
        node.dataset.sampledSource = source;
        node.dataset.samplingDone = "true";
        setAnimated(true);
        syncAnimation();
      } catch {
        // An unreadable image still works as the visible static logo.
      }
    };
    image.onerror = () => { if (!disposed) setFailedSource(source); };
    image.src = source;
    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("visibilitychange", syncAnimation);
      image.onload = image.onerror = null;
    };
  }, [slug, source, supplied, reduced]);

  return <span ref={host} className={`particle-logo${animated && !reduced ? " is-animated" : " is-static"}`} role="img" aria-label={`${name} logo`}
    data-logo-source={supplied ? "team-png" : "shield"} data-reduced-motion={String(reduced)}
    onPointerMove={(event) => {
      const bounds = event.currentTarget.getBoundingClientRect();
      pointer.current = { x: event.clientX - bounds.left + INSET, y: event.clientY - bounds.top + INSET };
    }} onPointerLeave={() => { pointer.current = null; }}>
    <span className="particle-logo-echo" aria-hidden="true">{supplied ? <img src={source} alt="" /> : <TeamShield name={name} />}</span>
    <span className="particle-logo-static" aria-hidden="true">{supplied ? <img src={source} alt="" onError={() => setFailedSource(source)} /> : <TeamShield name={name} />}</span>
    <canvas ref={canvas} className="particle-logo-canvas" width={CANVAS_SIZE} height={CANVAS_SIZE} aria-hidden="true" />
  </span>;
}
