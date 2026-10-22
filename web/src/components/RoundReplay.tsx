import { framePosition, lastPosition, roundClock, utilityEffect } from "../replayMath";
import Segmented from "./Segmented";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLocation, useNavigate } from "react-router-dom";
import { getMeta, getReplay, getTactics, useData } from "../data";
import { fmtInt, fmtNum, fmtSignedNum } from "../format";
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
  const location = useLocation();
  const recipeId = new URLSearchParams(location.search).get("recipe");
  const recipes = useData(() => recipeId ? getTactics(map) : Promise.resolve(null), [map, recipeId]);
  const commit = recipes.data?.recipes.find((recipe) => recipe.id === recipeId)?.median_commit_s;
  const { data, loading, error } = useData(() => demoId && round > 0
    ? getReplay(map, demoId, round) : Promise.reject(new Error("回合地址无效")), [map, demoId, round]);
  return loading ? <Loading /> : error || !data ? <p role="alert">{t("hub.load_error")}</p> : <>
    <p className="replay-title-match">{data.teams.T}（T） · {data.teams.CT}（CT） · 第 {fmtInt(data.round_num)} 回合 · 胜方：{data.teams[data.winner]}</p>
    <ReplayViewer replay={data} commit={commit} />
  </>;
}

function ReplayViewer({ replay, commit }: { replay: ReplayRound; commit?: number }) {
  const metadata = useData(() => getMeta(replay.map), [replay.map]);
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
  const events = [...replay.events].sort((a, b) => a.t - b.t);
  const plant = events.find((event) => event.kind === "plant");
  const firstEntryKill = events.find((event) => event.kind === "kill" && event.by != null && event.victim != null
    && replay.players[event.by]?.side === "T" && replay.players[event.victim]?.side === "CT");
  const hitTime = Number.isFinite(commit) ? commit : firstEntryKill?.t;
  const seek = (seconds: number) => { setPlaying(false); setTime(Math.max(0, Math.min(duration, seconds))); };
  const jumpNextKill = () => { const next = events.find((event) => event.kind === "kill" && event.t > time + .05); if (next) seek(next.t); };
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
        setTime((previous) => Math.max(0, Math.min(duration, previous + (event.key === "ArrowRight" ? 3 : -3))));
      } else if (event.key.toLowerCase() === "k") { event.preventDefault(); jumpNextKill(); }
      else if (event.key.toLowerCase() === "g" && hitTime != null) { event.preventDefault(); seek(hitTime); }
      else if (event.key.toLowerCase() === "p" && plant) { event.preventDefault(); seek(plant.t); }
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [time, duration, replay, hitTime]);
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
  const clock = roundClock(time, plant?.t);
  const unit = 1024 / radarWidth;
  const anchors = events.filter((event) => event.kind !== "util" || event.nade === "smoke");
  const eventLabel = (event: typeof events[number]) => event.kind === "kill"
    ? `${event.by == null ? "—" : replay.players[event.by]?.name ?? "—"} [${event.weapon}${event.headshot ? ` · ${t("round5.killfeed_hs")}` : ""}] ${event.victim == null ? "—" : replay.players[event.victim]?.name ?? "—"}`
    : event.kind === "plant" ? `${t("round4.replay_legend_plant")} ${event.site}` : t(`grenade.${event.nade === "flash" ? "flashbang" : event.nade}`);
  const eventSymbol = (event: typeof events[number]) => event.kind === "kill" ? "×" : event.kind === "plant" ? "▣" : "◌";
  const wp = replay.wp_t.map((value, index) => ({ value, index })).filter(({ value }) => Number.isFinite(value));
  const control = (replay.t_control ?? []).map((value, index) => ({ value, index }));
  const xAt = (seconds: number) => Math.max(0, Math.min(600, seconds / Math.max(1, duration) * 600));
  return <div className="replay-layout">
<div className="hud-radar-frame">    <svg ref={radar} className="replay-radar" viewBox="0 0 1024 1024" role="group" aria-label={t("round4.replay_title")}>
      <image href={`${import.meta.env.BASE_URL}radars/${replay.map}.png`} width="1024" height="1024" />
      <g className="replay-effects">{events.map((event, index) => {
        if (event.kind !== "util" || !event.at || event.t > time) return null;
        const age = time - event.t;
        const { life, active, radius } = utilityEffect(event.nade, age, metadata.data?.radar.scale);
        if (!active) return null;
        // Physical effects require the map scale; a point glyph is the honest fallback.
        return <g key={index} transform={`translate(${event.at[0]} ${event.at[1]})`} className={`replay-effect replay-effect-${event.nade}`}>
          <title>{event.nade === "smoke" ? t("round5.smoke_left", { s: Math.ceil(life - age) }) : eventLabel(event)}</title>
          {radius ? <><circle r={radius} fill={event.nade === "smoke" ? "#bec5ce" : event.nade === "molotov" ? "#ff853d" : "#fff"} opacity={event.nade === "flash" ? .8 * (1 - age / life) : .3} />
            <circle r={radius} fill="none" stroke={event.nade === "smoke" ? "#dbe1e8" : "#ffae64"} strokeWidth="2" vectorEffect="non-scaling-stroke" pathLength="1" strokeDasharray={`${1 - age / life} 1`} transform="rotate(-90)" /></>
            : <g transform="translate(-16 -16)"><GrenadeGlyph type={event.nade} /></g>}
        </g>;
      })}</g>
      {replay.players.map((player, index) => {
        const death = events.find((event) => event.kind === "kill" && event.victim === index && event.t <= time);
        if (death) return null;
        const point = framePosition(replay.frames, index, time);
        if (!point) return null;
        const [x, y] = point;
        return <g key={index} className="replay-player-marker" onPointerEnter={() => setHovered(index)} onPointerLeave={() => setHovered(null)}>
          <circle className="replay-player" cx={x} cy={y} r={4.5 * unit} fill={player.side === "T" ? "#efad55" : "#62b5ff"}
            tabIndex={0} role="button" aria-pressed={selected === index} aria-label={`${player.name} · ${player.side}`}
            onFocus={() => setHovered(index)} onBlur={() => setHovered(null)} onClick={() => setSelected((previous) => previous === index ? null : index)}
            onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); setSelected((previous) => previous === index ? null : index); } }} />
          <text className="replay-player-abbr" x={Math.min(970, x + 7 * unit)} y={y + 3 * unit} fontSize={10 * unit}>{player.name.slice(0, 4)}</text>
          {hovered === index || selected === index ? <text className="replay-player-name" x={Math.max(100, Math.min(924, x))} y={y < 40 ? y + 30 : y - 18} textAnchor="middle">{player.name}</text> : null}
        </g>;
      })}
      {events.map((event, index) => {
        if (event.t > time) return null;
        const age = time - event.t;
        const point = event.at ?? (event.kind === "kill" ? lastPosition(replay.frames, event.victim, event.t) : null);
        if (!point) return null;
        const [x, y] = point;
        if (event.kind === "kill") {
          const attacker = lastPosition(replay.frames, event.by, event.t);
          return <g key={index}><g transform={`translate(${x} ${y})`} className="replay-kill"><title>{eventLabel(event)}</title><path d={`M ${-5 * unit} ${-5 * unit} L ${5 * unit} ${5 * unit} M ${-5 * unit} ${5 * unit} L ${5 * unit} ${-5 * unit}`} /></g>
            {attacker && age <= 1.5 ? <line className="replay-kill-line" x1={attacker[0]} y1={attacker[1]} x2={x} y2={y} opacity={1 - age / 1.5} /> : null}</g>;
        }
        if (event.kind === "plant") return <g key={index} transform={`translate(${x} ${y})`} className="replay-plant"><title>{eventLabel(event)}</title><rect x="-15" y="-15" width="30" height="30" rx="4" /><text textAnchor="middle" y="6">{event.site}</text></g>;
        return null;
      })}
    </svg></div>
    <div className="replay-sidebar">
    <section className="replay-events" aria-label="回合事件"><h3>回合事件</h3><ol>{events.filter((event) => event.t <= time).slice().reverse().map((event, index) => <li className={event.kind === "kill" ? "replay-killfeed" : ""} key={`${event.t}:${index}`}><button type="button" onClick={() => seek(event.t)}><time>{fmtNum(event.t, 1)}s</time> {eventLabel(event)}{event.kind === "kill" && event.wpa != null && Number.isFinite(event.wpa) ? <span className="replay-kill-wpa" title="击杀者阵营的模型胜率变化（百分点）"> WPA {fmtSignedNum(event.wpa * 100, 1)}%</span> : null}</button></li>)}</ol></section>
    <div className="replay-controls">
      <button type="button" className="button" onClick={togglePlayback}>{t(playing ? "round4.replay_pause" : "round4.replay_play")}</button>
      <Segmented className="segmented" role="group" aria-label="回放速度">{[1, 2, 4].map((value) => <button key={value} type="button" aria-pressed={speed === value} onClick={() => setSpeed(value)}>{t("round4.replay_speed", { x: value })}</button>)}</Segmented>
      <output className="replay-clock" aria-label={t("round5.clock_elapsed", { s: fmtNum(time, 1) })}>{t("round5.clock", { clock })}<small>{t("round5.clock_elapsed", { s: fmtNum(time, 1) })}</small></output>
    </div>
    <div className="replay-timeline"><input className="replay-scrubber" type="range" min="0" max={duration} step="0.1" value={time} aria-label={t("round5.clock_elapsed", { s: fmtNum(time, 1) })} onChange={(event) => seek(Number(event.target.value))} />
      <div className="replay-anchors">{anchors.map((event, index) => <button type="button" key={index} data-kind={event.kind} style={{ left: `${xAt(event.t) / 6}%` }} aria-label={`${fmtNum(event.t, 1)}s · ${eventLabel(event)}`} title={eventLabel(event)} onClick={() => seek(event.t)}>{eventSymbol(event)}</button>)}</div>
    </div>
    <figure className="replay-wp"><figcaption>{t("round4.replay_wp")}</figcaption>{wp.length ? <svg viewBox="-8 -8 616 100" role="group" aria-label={t("round4.replay_wp")}>
      <line x1="0" x2="600" y1="35" y2="35" stroke="#526077" strokeDasharray="4 4" />
      <polyline points={wp.map(({ value, index }) => `${xAt(index)},${65 - Math.max(0, Math.min(1, value!)) * 60}`).join(" ")} fill="none" stroke="#efad55" strokeWidth="2" />
      {anchors.map((event, index) => <g key={index} role="button" tabIndex={0} aria-label={`${fmtNum(event.t, 1)}s · ${eventLabel(event)}`} onClick={() => seek(event.t)} onKeyDown={(key) => { if (key.key === "Enter" || key.key === " ") { key.preventDefault(); seek(event.t); } }}><title>{eventLabel(event)}</title><circle cx={xAt(event.t)} cy="80" r="7" fill={event.kind === "kill" ? "#ff8b84" : event.kind === "plant" ? "#efad55" : "#a3b4c5"} /></g>)}
      <line className="replay-playhead" x1={xAt(time)} x2={xAt(time)} y1="0" y2="70" stroke="#fff" strokeWidth="2" />
    </svg> : <p className="muted">{t("heatmap.no_data")}</p>}</figure>
    {control.some(({ value }) => value != null) ? <figure className="replay-control"><figcaption>T 控图</figcaption><svg viewBox="-8 -4 616 34" role="img" aria-label="T 控图 · 存活双方到可行走格子的距离占比"><title>T 控图 · 按距离估算；不计墙体与视野</title>
      <line x1="0" x2="600" y1="13" y2="13" stroke="#526077" strokeDasharray="4 4" />
      <path d={control.map(({ value, index }, i) => value == null || !Number.isFinite(value) ? "" : `${i === 0 || control[i - 1].value == null ? "M" : "L"}${xAt(index)},${25 - Math.max(0, Math.min(1, value)) * 24}`).join(" ")} fill="none" stroke="#9faebd" strokeWidth="1.25" />
      <line x1={xAt(time)} x2={xAt(time)} y1="0" y2="26" stroke="#fff" strokeWidth="1" />
    </svg></figure> : null}
    <p className="muted replay-legend"><span style={{ color: "#efad55" }}>● T</span> · <span style={{ color: "#62b5ff" }}>● CT</span> · × {t("round4.replay_legend_kill")} · {t("round4.replay_legend_util")} · ▣ {t("round4.replay_legend_plant")}</p>
    <div className="replay-jumps"><button className="button button-ghost" type="button" onClick={jumpNextKill} disabled={!events.some((event) => event.kind === "kill" && event.t > time + .05)}>{t("round5.next_kill")}</button><button className="button button-ghost" type="button" disabled={hitTime == null} onClick={() => hitTime != null && seek(hitTime)} title={commit == null ? "首个 T 方击杀时刻" : "本套路进点时间中位数"}>{t("round5.jump_hit")}</button><button className="button button-ghost" type="button" disabled={!plant} onClick={() => plant && seek(plant.t)}>{t("round5.jump_plant")}</button></div>
    <p className="muted replay-keys">{t("round5.keys_hint")}</p>
    </div></div>;
}
