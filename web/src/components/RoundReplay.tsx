import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { getReplay, useData } from "../data";
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
  }}>{t("round4.replay_open", { round })}</button>;
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
  return createPortal(<ReplayModal key={`${map}:${value}`} map={map} demoId={match?.[1] ?? ""} round={Number(match?.[2] ?? 0)} close={close} />, document.body);
}

function ReplayModal({ map, demoId, round, close }: { map: string; demoId: string; round: number; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const { data, loading, error } = useData(() => demoId && round > 0
    ? getReplay(map, demoId, round) : Promise.reject(new Error("回合地址无效")), [map, demoId, round]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element?.showModal();
    return () => { element?.close(); document.body.style.overflow = overflow; previous?.focus(); };
  }, []);
  return <dialog ref={dialog} className="round-replay" aria-labelledby="replay-title" onCancel={(event) => { event.preventDefault(); close(); }}
    onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); } }}>
    <header><h2 id="replay-title">{t("round4.replay_title")}{data ? <span className="replay-title-match">{data.teams.T}（T） · {data.teams.CT}（CT） · 第 {data.round_num} 回合 · 胜方：{data.teams[data.winner]}</span> : null}</h2><button type="button" className="button button-ghost replay-close" onClick={close}>{t("round4.replay_close")}</button></header>
    {loading ? <Loading /> : error || !data ? <p role="alert">{t("hub.load_error")}</p> : <ReplayViewer replay={data} />}
  </dialog>;
}

function ReplayViewer({ replay }: { replay: ReplayRound }) {
  const reduced = useReducedMotion();
  const [playing, setPlaying] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [speed, setSpeed] = useState(1);
  const [time, setTime] = useState(0);
  const duration = Math.max(0, replay.duration);
  useEffect(() => { if (reduced) setPlaying(false); }, [reduced]);
  useEffect(() => {
    if (!playing) return;
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
  const wp = replay.wp_t.filter((value) => Number.isFinite(value));
  const xAt = (seconds: number) => Math.max(0, Math.min(600, seconds / Math.max(1, duration) * 600));
  return <>
    <svg className="replay-radar" viewBox="0 0 1024 1024" role="group" aria-label={t("round4.replay_title")}>
      <image href={`${import.meta.env.BASE_URL}radars/${replay.map}.png`} width="1024" height="1024" />
      {replay.players.map((player, index) => {
        const start = before[index];
        if (!start || replay.events.some((event) => event.kind === "kill" && event.victim === index && event.t <= time)) return null;
        const end = after[index] ?? start;
        const x = start[0] + (end[0] - start[0]) * fraction;
        const y = start[1] + (end[1] - start[1]) * fraction;
        return <circle key={index} className="replay-player" cx={x} cy={y} r="10" fill={player.side === "T" ? "#efad55" : "#62b5ff"} tabIndex={0} aria-label={`${player.name} · ${player.side}`}><title>{player.name} · {player.side}</title></circle>;
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
      <button type="button" className="button" onClick={() => { if (time >= duration) setTime(0); setPlaying(!playing); }}>{t(playing ? "round4.replay_pause" : "round4.replay_play")}</button>
      <div className="segmented" role="group" aria-label="回放速度">{[1, 2, 4].map((value) => <button key={value} type="button" aria-pressed={speed === value} onClick={() => setSpeed(value)}>{t("round4.replay_speed", { x: value })}</button>)}</div>
      <output>{t("round4.replay_time", { s: time.toFixed(1) })} / {duration}</output>
    </div>
    <input className="replay-scrubber" type="range" min="0" max={duration} step="0.1" value={time} aria-label={t("round4.replay_time", { s: time.toFixed(1) })} onChange={(event) => { setPlaying(false); setTime(Number(event.target.value)); }} />
    <figure className="replay-wp"><figcaption>{t("round4.replay_wp")}</figcaption>{wp.length ? <svg viewBox="0 0 600 70" role="img" aria-label={t("round4.replay_wp")}>
      <line x1="0" x2="600" y1="35" y2="35" stroke="#526077" strokeDasharray="4 4" />
      <polyline points={wp.map((value, index) => `${xAt(index)},${65 - Math.max(0, Math.min(1, value)) * 60}`).join(" ")} fill="none" stroke="#efad55" strokeWidth="2" />
      <line className="replay-playhead" x1={xAt(time)} x2={xAt(time)} y1="0" y2="70" stroke="#fff" strokeWidth="2" />
    </svg> : <p className="muted">{t("heatmap.no_data")}</p>}</figure>
    <p className="muted replay-legend"><span style={{ color: "#efad55" }}>● T</span> · <span style={{ color: "#62b5ff" }}>● CT</span> · × {t("round4.replay_legend_kill")} · {t("round4.replay_legend_util")} · ▣ {t("round4.replay_legend_plant")}</p>
    <p className="muted">{t("round4.replay_tip")}</p>
  </>;
}
