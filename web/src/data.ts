import { useEffect, useState, type DependencyList } from "react";
import type {
  HeatmapBaseline,
  HeatmapTeamIndexEntry,
  Lineup,
  MapMeta,
  PlayerProfile,
  PlayerQuotes,
  AssetSlots,
  SiteIndex,
  TacticsFile,
  TeamHeatmap,
  TeamProfile,
  TeamSummary,
  WinprobTimeline,
  ReplayRound,
} from "./types";

const base = import.meta.env.BASE_URL;
const cache = new Map<string, Promise<unknown>>();

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${base}${path}`);
  if (!response.ok) {
    throw new Error(`Could not load ${path} (HTTP ${response.status}).`);
  }
  return (await response.json()) as T;
}

function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  const existing = cache.get(key) as Promise<T> | undefined;
  if (existing) return existing;
  const request = load().catch((error: unknown) => {
    cache.delete(key);
    throw error;
  });
  cache.set(key, request);
  return request;
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

export function getIndex(): Promise<SiteIndex> {
  return cached("index", () => fetchJson<SiteIndex>("data/index.json"));
}

export function getMeta(map: string): Promise<MapMeta> {
  return cached(`meta:${map}`, () => fetchJson<MapMeta>(`data/${segment(map)}/meta.json`));
}

export function getTeams(map: string): Promise<TeamSummary[]> {
  return cached(`teams:${map}`, () =>
    fetchJson<TeamSummary[]>(`data/${segment(map)}/teams.json`),
  );
}

export function getTeam(map: string, slug: string): Promise<TeamProfile> {
  return cached(`team:${map}:${slug}`, () =>
    fetchJson<TeamProfile>(`data/${segment(map)}/teams/${segment(slug)}.json`),
  );
}

export function getPlayers(map: string): Promise<PlayerProfile[]> {
  return cached(`players:${map}`, () =>
    fetchJson<PlayerProfile[]>(`data/${segment(map)}/players.json`),
  );
}

export function getPlayerQuotes(): Promise<PlayerQuotes> {
  return cached("player-quotes", () => fetchJson<PlayerQuotes>("data/player_quotes.json"));
}

export function getAssetSlots(): Promise<AssetSlots> {
  return cached("asset-slots", () => fetchJson<AssetSlots>("data/asset_slots.json"));
}

export function getLineups(map: string): Promise<Lineup[]> {
  return cached(`lineups:${map}`, () =>
    fetchJson<Lineup[]>(`data/${segment(map)}/lineups.json`),
  );
}

export function getTactics(map: string): Promise<TacticsFile> {
  return cached(`tactics:${map}`, () => fetchJson<TacticsFile>(`data/${segment(map)}/tactics.json`));
}

/** Optional showcase export. Older/static sites may return an HTML fallback for missing files. */
export function getWinprob(map: string, demoId: string): Promise<WinprobTimeline | null> {
  return cached(`winprob:${map}:${demoId}`, async () => {
    const response = await fetch(`${base}data/${segment(map)}/winprob/${segment(demoId)}.json`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`Could not load win probability (HTTP ${response.status}).`);
    if (!response.headers.get("content-type")?.includes("json")) return null;
    const timeline = await response.json() as WinprobTimeline;
    return timeline?.demo_id === demoId && timeline.wp_t && typeof timeline.wp_t === "object" ? timeline : null;
  });
}

export function getHeatmapTeams(): Promise<HeatmapTeamIndexEntry[]> {
  return cached("hm-teams", () => fetchJson<HeatmapTeamIndexEntry[]>("data/heatmap_teams.json"));
}

export function getHeatmapBaseline(map: string): Promise<HeatmapBaseline> {
  return cached(`hm-base:${map}`, () =>
    fetchJson<HeatmapBaseline>(`data/${segment(map)}/heatmaps/baseline.json`),
  );
}

export function getTeamHeatmap(map: string, slug: string): Promise<TeamHeatmap> {
  return cached(`hm-team:${map}:${slug}`, () =>
    fetchJson<TeamHeatmap>(`data/${segment(map)}/heatmaps/teams/${segment(slug)}.json`),
  );
}

interface DataState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

/**
 * Fetch-on-deps hook. `load` is called whenever `deps` change and is deliberately
 * left out of the effect dependency list so that inline arrow functions are safe.
 */
export function useData<T>(load: () => Promise<T>, deps: DependencyList): DataState<T> {
  const [state, setState] = useState<DataState<T>>({
    data: null,
    error: null,
    loading: true,
  });

  useEffect(() => {
    let active = true;
    setState({ data: null, error: null, loading: true });
    load().then(
      (data) => {
        if (active) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (!active) return;
        setState({
          data: null,
          error: error instanceof Error ? error : new Error(String(error)),
          loading: false,
        });
      },
    );
    return () => {
      active = false;
    };
  }, deps);

  return state;
}

export function getReplayIndex(map: string): Promise<Record<string, number[]>> {
  return cached(`replay-index:${map}`, async () => {
    const response = await fetch(`${base}data/${segment(map)}/replay/index.json`);
    if (response.status === 404 || !response.headers.get("content-type")?.includes("json")) return {};
    if (!response.ok) throw new Error(`Could not load replay index (HTTP ${response.status}).`);
    return response.json();
  });
}

export function getReplay(map: string, demoId: string, round: number): Promise<ReplayRound> {
  return cached(`replay:${map}:${demoId}:${round}`, () =>
    fetchJson<ReplayRound>(`data/${segment(map)}/replay/${segment(demoId)}/${round}.json`));
}
