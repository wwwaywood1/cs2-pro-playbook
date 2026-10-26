import { useEffect, useState, type DependencyList } from "react";
import type {
  HeatmapBaseline,
  HeatmapTeamIndexEntry,
  Lineup,
  LineupIndex,
  LineupRef,
  MapMeta,
  PlayerProfile,
  PlayerQuotes,
  AssetSlots,
  SearchIndex,
  SiteIndex,
  TacticsFile,
  TeamHeatmap,
  TeamProfile,
  TeamSummary,
  WinprobTimeline,
  ReplayRound,
} from "./types";

const base = import.meta.env.BASE_URL;
export function assetUrl(path: string): string { return `${base}${path.replace(/^\/+/, "")}`; }

export function getMapBackgrounds(): Promise<string[]> {
  return cached("map-backgrounds", () => fetchJson<string[]>("map-bg/manifest.json", Array.isArray));
}

/**
 * A data file that could not be used. `kind` drives the localized message
 * (components/Status.tsx); `path` and `status` stay available for diagnostics.
 * missing = HTTP 404, or the HTML fallback page a static host serves for a missing file.
 */
export type DataErrorKind = "missing" | "http" | "network" | "parse" | "shape";
export class DataError extends Error {
  constructor(readonly kind: DataErrorKind, readonly path: string, readonly status?: number) {
    super(`${kind}: ${path}${status ? ` (HTTP ${status})` : ""}`);
    this.name = "DataError";
  }
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const hasArrays = (...keys: string[]) => (value: unknown) => isObject(value) && keys.every((key) => Array.isArray(value[key]));
const hasObjects = (...keys: string[]) => (value: unknown) => isObject(value) && keys.every((key) => isObject(value[key]));
/** Every row must carry T and CT objects: a null side used to crash the players page. */
const playerRows = (value: unknown) => Array.isArray(value) && value.every((row) => isObject(row) && isObject(row.T) && isObject(row.CT));

async function fetchJson<T>(path: string, valid?: (value: unknown) => boolean): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`);
  } catch {
    throw new DataError("network", path);
  }
  if (response.status === 404) throw new DataError("missing", path, 404);
  if (!response.ok) throw new DataError("http", path, response.status);
  // GitHub Pages and vite preview answer a missing file with index.html (200).
  if (response.headers.get("content-type")?.includes("text/html")) throw new DataError("missing", path, response.status);
  let value: unknown;
  try {
    value = await response.json();
  } catch {
    throw new DataError("parse", path, response.status);
  }
  if (valid && !valid(value)) throw new DataError("shape", path, response.status);
  return value as T;
}

/**
 * Promise cache keyed by file. Large per-map files make a long browsing session grow
 * the heap, so settled entries are evicted least-recently-used beyond MAX_CACHED;
 * small site-wide files stay pinned. Failed loads are dropped so a retry refetches.
 */
const MAX_CACHED = 48;
const PINNED = new Set(["index", "hm-teams", "asset-slots", "player-quotes", "map-backgrounds", "search-index"]);
const cache = new Map<string, Promise<unknown>>();
const settled = new Set<string>();

function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  const existing = cache.get(key) as Promise<T> | undefined;
  if (existing) {
    cache.delete(key);
    cache.set(key, existing);
    return existing;
  }
  const request = load().then((value) => {
    if (cache.get(key) === request) settled.add(key);
    return value;
  }, (error: unknown) => {
    if (cache.get(key) === request) cache.delete(key);
    throw error;
  });
  cache.set(key, request);
  for (const old of cache.keys()) {
    if (cache.size <= MAX_CACHED) break;
    if (old === key || PINNED.has(old) || !settled.has(old)) continue;
    cache.delete(old);
    settled.delete(old);
  }
  return request;
}

/** Forget every cached request, so an error boundary retry refetches its data. */
export function clearDataCache(): void {
  cache.clear();
  settled.clear();
}

function segment(value: string): string {
  return encodeURIComponent(value);
}

export function getIndex(): Promise<SiteIndex> {
  return cached("index", () => fetchJson<SiteIndex>("data/index.json", hasArrays("maps")));
}

export function getMeta(map: string): Promise<MapMeta> {
  return cached(`meta:${map}`, () => fetchJson<MapMeta>(`data/${segment(map)}/meta.json`, hasObjects("radar")));
}

export function getTeams(map: string): Promise<TeamSummary[]> {
  return cached(`teams:${map}`, () =>
    fetchJson<TeamSummary[]>(`data/${segment(map)}/teams.json`, Array.isArray),
  );
}

export function getTeam(map: string, slug: string): Promise<TeamProfile> {
  return cached(`team:${map}:${slug}`, () =>
    fetchJson<TeamProfile>(`data/${segment(map)}/teams/${segment(slug)}.json`,
      (value) => hasArrays("matches", "economy")(value) && hasObjects("sides")(value)),
  );
}

export function getPlayers(map: string): Promise<PlayerProfile[]> {
  return cached(`players:${map}`, () =>
    fetchJson<PlayerProfile[]>(`data/${segment(map)}/players.json`, playerRows),
  );
}

export function getPlayerQuotes(): Promise<PlayerQuotes> {
  return cached("player-quotes", () => fetchJson<PlayerQuotes>("data/player_quotes.json", isObject));
}

export function getAssetSlots(): Promise<AssetSlots> {
  return cached("asset-slots", () => fetchJson<AssetSlots>("data/asset_slots.json", hasArrays("teams", "players")));
}

/** The full lineup library: only the lineups page needs every field of every row. */
export function getLineups(map: string): Promise<Lineup[]> {
  return cached(`lineups:${map}`, () =>
    fetchJson<Lineup[]>(`data/${segment(map)}/lineups.json`, Array.isArray),
  );
}

function lineupRef(lineup: Lineup): LineupRef {
  const { side, type, throw_place, land_place, n_throws, name } = lineup;
  const { x, y, z, pitch, yaw } = lineup.throw;
  return { side, type, throw_place, land_place, n_throws, name,
    throw: [lineup.throw.radar_x, lineup.throw.radar_y], land: [lineup.land.radar_x, lineup.land.radar_y], setpos: [x, y, z, pitch, yaw] };
}

/**
 * lineup id -> the fields the tactics radar, the recipe practice script and the hub
 * utility layer read (playbook/site_index.py). Exports written before the index
 * existed fall back to deriving it from lineups.json.
 */
export function getLineupIndex(map: string): Promise<LineupIndex> {
  return cached(`lineup-index:${map}`, async () => {
    try {
      return await fetchJson<LineupIndex>(`data/${segment(map)}/lineup_index.json`, isObject);
    } catch (error) {
      if (!(error instanceof DataError) || error.kind !== "missing") throw error;
      return Object.fromEntries((await getLineups(map)).map((lineup) => [lineup.id, lineupRef(lineup)]));
    }
  });
}

/** Column order the palette decodes; must match playbook/site_index.py. */
export const SEARCH_COLUMNS: Record<Exclude<keyof SearchIndex, "schema_version" | "generated_at" | "events">, string[]> = {
  maps: ["map", "display_name"],
  teams: ["slug", "team", "maps"],
  matches: ["team", "map", "demo_id", "opponent", "date", "date_precision", "event", "hltv_match_id"],
  recipes: ["id", "map", "site", "spots"],
  lineups: ["id", "map", "side", "type", "throw_place", "land_place", "n_throws", "name"],
  players: ["steamid", "name", "teams"],
};

/** Everything the Ctrl+K palette searches, in one small file (playbook/site_index.py). */
export function getSearchIndex(): Promise<SearchIndex> {
  return cached("search-index", () => fetchJson<SearchIndex>("data/search_index.json", (value) =>
    isObject(value) && value.schema_version === 1 && Array.isArray(value.events)
    && Object.entries(SEARCH_COLUMNS).every(([key, columns]) => {
      const table = value[key];
      return isObject(table) && Array.isArray(table.rows) && Array.isArray(table.columns)
        && table.columns.length === columns.length && columns.every((column, i) => (table.columns as unknown[])[i] === column);
    })));
}

export function getTactics(map: string): Promise<TacticsFile> {
  return cached(`tactics:${map}`, () => fetchJson<TacticsFile>(`data/${segment(map)}/tactics.json`,
    (value) => hasArrays("recipes", "spots")(value) && hasObjects("t_overview", "ct_overview")(value)
      && isObject((value as TacticsFile).ct_overview) && Array.isArray((value as TacticsFile).ct_overview.setups_20s)));
}

/** Optional showcase export. Older/static sites may return an HTML fallback for missing files. */
export function getWinprob(map: string, demoId: string): Promise<WinprobTimeline | null> {
  return cached(`winprob:${map}:${demoId}`, async () => {
    const response = await fetch(`${base}data/${segment(map)}/winprob/${segment(demoId)}.json`);
    if (response.status === 404) return null;
    if (!response.ok) throw new DataError("http", `data/${map}/winprob/${demoId}.json`, response.status);
    if (!response.headers.get("content-type")?.includes("json")) return null;
    const timeline = await response.json() as WinprobTimeline;
    return timeline?.demo_id === demoId && timeline.wp_t && typeof timeline.wp_t === "object" ? timeline : null;
  });
}

export function getHeatmapTeams(): Promise<HeatmapTeamIndexEntry[]> {
  return cached("hm-teams", () => fetchJson<HeatmapTeamIndexEntry[]>("data/heatmap_teams.json",
    (value) => Array.isArray(value) && value.every((team) => isObject(team) && Array.isArray(team.maps))));
}

export function getHeatmapBaseline(map: string): Promise<HeatmapBaseline> {
  return cached(`hm-base:${map}`, () =>
    fetchJson<HeatmapBaseline>(`data/${segment(map)}/heatmaps/baseline.json`, hasObjects("data", "per_round")),
  );
}

export function getTeamHeatmap(map: string, slug: string): Promise<TeamHeatmap> {
  return cached(`hm-team:${map}:${slug}`, () =>
    fetchJson<TeamHeatmap>(`data/${segment(map)}/heatmaps/teams/${segment(slug)}.json`,
      (value) => hasArrays("roster")(value) && hasObjects("summary", "players", "team_grid")(value)),
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
    if (!response.ok) throw new DataError("http", `data/${map}/replay/index.json`, response.status);
    const value: unknown = await response.json();
    return isObject(value) ? value as Record<string, number[]> : {};
  });
}

export function getReplay(map: string, demoId: string, round: number): Promise<ReplayRound> {
  return cached(`replay:${map}:${demoId}:${round}`, () =>
    fetchJson<ReplayRound>(`data/${segment(map)}/replay/${segment(demoId)}/${round}.json`,
      (value) => hasArrays("players", "frames", "events")(value) && hasObjects("teams")(value)));
}

export function getAILab(): Promise<import("./labTypes").AILab> {
  return cached("ai-lab", () => fetchJson("data/ai_lab.json", (value) => hasArrays("attention", "references")(value) && hasObjects("shap", "metadata")(value)));
}
export function getCTPatterns(map: string): Promise<import("./labTypes").CTPatterns> {
  return cached(`ct-patterns:${map}`, () => fetchJson(`data/${segment(map)}/ct_patterns.json`,
    (value) => hasArrays("clusters", "fingerprints")(value) && hasObjects("chi_square", "counts", "metadata", "embedding")(value)));
}
