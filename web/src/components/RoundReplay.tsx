import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { getReplay, useData } from "../data";
import { fmtInt, fmtNum, fmtSeconds } from "../format";
import { t, useLang } from "../i18n";
import { useReducedMotion } from "../motion";
import type { ReplayRound } from "../types";
import { Loading } from "./Status";
import { GrenadeGlyph } from "./GrenadeIcon";
import "../replay.css";

export function ReplayButton({ map, demoId, round }: { map: string; demoId: string; round: number }) {
  const location = useLocation();
  const navigate = useNavigate();
  return <button type="button" className="button button-ghost replay-open" onClick={() => {
    const query = new URLSearchParams(location.search);
    query.set("replay", `${demoId}:${round}`);
    // Hub already carries map; tactics carries it in the pathname.
    if (location.pathname === "/teams-hub") query.set("map", map);
    navigate({ pathname: location.pathname, search: `?${query}` }, { state: { ...location.state, replayOpened: `${demoId}:${round}` } });
  }}>{t("round4.replay_open", { round: fmtInt(round) })}</button>;
}

export default function RoundReplay() {
  useLang();
  const location = useLocation();
  const navigate = useNavigate();
  const query = new URLSearchParams(location.search);
  const value = query.get("replay");
  const match = value?.match(/^(.+):(\d+)$/);
  const map = query.get("map") || location.pathname.split("/")[1];
  function close() {
    if (location.state?.replayOpened === value) { navigate(-1); return; }
    const next = new URLSearchParams(location.search);
    next.delete("replay");
    navigate({ pathname: location.pathname, search: next.toString() ? `?${next}` : "" }, { replace: true });
  }
  if (!value) return null;
  return createPortal(<ReplayModal map={map} demoId={match?.[1] ?? ""} round={Number(match?.[2] ?? 0)} close={close} />, document.body);
}

function ReplayModal({ map, demoId, round, close }: { map: string; demoId: string; round: number; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useLayoutEffect(() => {
    const previous = document.activeElement as HTMLElement | SVGElement | null;
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    const overflowPriority = document.body.style.getPropertyPriority("overflow");
    document.body.style.setProperty("overflow", "hidden");
    element?.showModal();
    return () => { element?.close(); if (overflow) document.body.style.setProperty("overflow", overflow, overflowPriority); else document.body.style.removeProperty("overflow"); if (previous?.isConnected) previous.focus({ preventScroll: true }); };
  }, []);
  useLayoutEffect(() => {
    // A selected player may disappear when the round changes; keep focus in the dialog.
    if (dialog.current && !dialog.current.contains(document.activeElement)) {
      dialog.current.querySelector<HTMLButtonElement>(".replay-close")?.focus();
    }
  }, [map, demoId, round]);
  return <dialog ref={dialog} className="round-replay" aria-labelledby="replay-title" onCancel={(event) => { event.preventDefault(); close(); }}
    onKeyDown={(event) => {
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); }
      if (event.key !== "Tab") return;
      const focusable = [...event.currentTarget.querySelectorAll<HTMLElement | SVGElement>(
        "button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex='-1'])",
      )].filter((element) => element.getClientRects().length > 0);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || !event.currentTarget.contains(document.activeElement))) {
        event.preventDefault(); last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first?.focus();
      }
    }}>
    <header><h2 id="replay-title">{t("round4.replay_title")}</h2><button type="button" className="button button-ghost replay-close" onClick={close}>{t("round4.replay_close")}</button></header>
    <ReplayContent key={`${map}:${demoId}:${round}`} map={map} demoId={demoId} round={round} />
  </dialog>;
}

// Remount requests and playback together; useData ignores responses after cleanup.
function ReplayContent({ map, demoId, round }: { map: string; demoId: string; round: number }) {
  const { data, loading, error } = useData(() => demoId && round > 0
    ? getReplay(map, demoId, round) : Promise.reject(new Error("回合地址无效")), [map, demoId, round]);
  return loading ? <Loading /> : error || !data ? <p role="alert">{t("hub.load_error")}</p> : <>
    <p className="replay-title-match">{data.teams.T}（T） · {data.teams.CT}（CT） · 第 {fmtInt(data.round_num)} 回合 · 胜方：{data.teams[data.winner]}</p>
    <ReplayViewer replay={data} />
  </>;
}

function ReplayViewer({ replay }: { replay: ReplayRound }) {
  const reduced = useReducedMotion();
  const [playing, setPlaying] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [speed, setSpeed] = useState(1);
  const [time, setTime] = useState(0);
  const [hovered, setHovered] = useState<number | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const radar = useRef<SVGSVGElement>(null);
  const [radarWidth, setRadarWidth] = useState(1024);
  const duration = Math.max(0, replay.duration);
  useLayoutEffect(() => {
    const element = radar.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setRadarWidth(entry.contentRect.width || 1024));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const togglePlayback = () => {
    if (time >= duration) setTime(0);
    setPlaying((previous) => !previous);
  };
  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target;
      if (target instanceof Element && target.closest("textarea, select, [contenteditable='true'], input:not([type='range'])")) return;
      if (event.key === " ") {
        event.preventDefault();
        if (!event.repeat) togglePlayback();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        setPlaying(false);
        setTime((previous) => Math.max(0, Math.min(duration, previous + (event.key === "ArrowRight" ? 1 : -1))));
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [time, duration]);
  useEffect(() => { if (reduced) setPlaying(false); }, [reduced]);
  useEffect(() => {
    if (!playing || duration <= 0) return;
    let frame = 0;
    let last = performance.now();
    const step = (now: number) => {
      const delta = Math.min(.25, (now - last) / 1000) * speed;
      last = now;
      setTime((previous) => Math.min(duration, previous + delta));
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [playing, speed, duration]);
  useEffect(() => { if (time >= duration) setPlaying(false); }, [time, duration]);
  const second = Math.floor(time);
  const fraction = time - second;
  const before = replay.frames[Math.min(second, replay.frames.length - 1)] ?? [];
  const after = replay.frames[Math.min(second + 1, replay.frames.length - 1)] ?? [];
  const wp = replay.wp_t.map((value, index) => ({ value, index })).filter(({ value }) => Number.isFinite(value));
  const xAt = (seconds: number) => Math.max(0, Math.min(600, seconds / Math.max(1, duration) * 600));
  return <>
    <svg ref={radar} className="replay-radar" viewBox="0 0 1024 1024" role="group" aria-label={t("round4.replay_title")}>
      <image href={`${import.meta.env.BASE_URL}radars/${replay.map}.png`} width="1024" height="1024" />
      {replay.players.map((player, index) => {
        const start = before[index];
        if (!start || replay.events.some((event) => event.kind === "kill" && event.victim === index && event.t <= time)) return null;
        const end = after[index] ?? start;
        const x = start[0] + (end[0] - start[0]) * fraction;
        const y = start[1] + (end[1] - start[1]) * fraction;
        return <g key={index} className="replay-player-marker" onPointerEnter={() => setHovered(index)} onPointerLeave={() => setHovered(null)}>
          <circle className="replay-player" cx={x} cy={y} r={4.5 * 1024 / radarWidth} fill={player.side === "T" ? "#efad55" : "#62b5ff"}
            tabIndex={0} role="button" aria-pressed={selected === index} aria-label={`${player.name} · ${player.side}`}
            onFocus={() => setHovered(index)} onBlur={() => setHovered(null)} onClick={() => setSelected((previous) => previous === index ? null : index)}
            onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); setSelected((previous) => previous === index ? null : index); } }} />
          {hovered === index || selected === index ? <text className="replay-player-name" x={Math.max(100, Math.min(924, x))} y={y < 40 ? y + 30 : y - 18} textAnchor="middle">{player.name}</text> : null}
        </g>;
      })}
      {replay.events.map((event, index) => {
        if (!event.at || event.t > time) return null;
        const age = time - event.t;
        if (event.kind === "util" && age > 3) return null;
        const [x, y] = event.at;
        if (event.kind === "kill") return <g key={index} transform={`translate(${x} ${y})`} className="replay-kill"><title>{t("round4.replay_legend_kill")} · {event.by === null ? "—" : replay.players[event.by]?.name} → {event.victim === null ? "—" : replay.players[event.victim]?.name}</title><path d="M -7 -7 L 7 7 M -7 7 L 7 -7" /></g>;
        if (event.kind === "plant") return <g key={index} transform={`translate(${x} ${y})`} className="replay-plant"><title>{t("round4.replay_legend_plant")} · {event.site}</title><rect x="-15" y="-15" width="30" height="30" rx="4" /><text textAnchor="middle" y="6">{event.site}</text></g>;
        return <g key={index} opacity={Math.max(0, 1 - age / 3)} transform={`translate(${x - 18} ${y - 18}) scale(1.125)`}><title>{t("round4.replay_legend_util")} · {t(`grenade.${event.nade === "flash" ? "flashbang" : event.nade}`)}</title><GrenadeGlyph type={event.nade} /></g>;
      })}
    </svg>
    <div className="replay-controls">
      <button type="button" className="button" onClick={togglePlayback}>{t(playing ? "round4.replay_pause" : "round4.replay_play")}</button>
      <div className="segmented" role="group" aria-label="回放速度">{[1, 2, 4].map((value) => <button key={value} type="button" aria-pressed={speed === value} onClick={() => setSpeed(value)}>{t("round4.replay_speed", { x: value })}</button>)}</div>
      <output>{t("round4.replay_time", { s: fmtNum(time, 1) })} / {fmtSeconds(duration)}</output>
    </div>
    <input className="replay-scrubber" type="range" min="0" max={duration} step="0.1" value={time} aria-label={t("round4.replay_time", { s: fmtNum(time, 1) })} onChange={(event) => { setPlaying(false); setTime(Number(event.target.value)); }} />
    <figure className="replay-wp"><figcaption>{t("round4.replay_wp")}</figcaption>{wp.length ? <svg viewBox="0 0 600 70" role="img" aria-label={t("round4.replay_wp")}>
      <line x1="0" x2="600" y1="35" y2="35" stroke="#526077" strokeDasharray="4 4" />
      <polyline points={wp.map(({ value, index }) => `${xAt(index)},${65 - Math.max(0, Math.min(1, value)) * 60}`).join(" ")} fill="none" stroke="#efad55" strokeWidth="2" />
      <line className="replay-playhead" x1={xAt(time)} x2={xAt(time)} y1="0" y2="70" stroke="#fff" strokeWidth="2" />
    </svg> : <p className="muted">{t("heatmap.no_data")}</p>}</figure>
    <p className="muted replay-legend"><span style={{ color: "#efad55" }}>● T</span> · <span style={{ color: "#62b5ff" }}>● CT</span> · × {t("round4.replay_legend_kill")} · {t("round4.replay_legend_util")} · ▣ {t("round4.replay_legend_plant")}</p>
    <p className="muted">{t("round4.replay_tip")}</p>
  </>;
}
