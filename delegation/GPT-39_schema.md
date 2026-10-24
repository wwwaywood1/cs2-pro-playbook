# GPT-39 backend contract (schema_version: 1)

Files: `data/site/<map>/ct_patterns.json` for every parsed map (including Overpass), and `data/site/ai_lab.json`. All probabilities/shares are fractions; differences ending `_pp` are percentage points. Radar coordinates are on the existing 1024×1024 radar. No paper cluster names or outcome numbers are copied.

```ts
type RegionShares = { A: number; MID: number; B: number; CT_SPAWN: number; OTHER: number };
type RoundRef = { demo_id: string; round_num: number; team: string; economy: string;
  score: {ct: number; t: number} };
type Snapshot = { t_s: number; positions: number[][] }; // five [radar_x,radar_y,level] slots
interface CTPatterns {
  schema_version: 1; map: string; method: string; metadata: Record<string, unknown>;
  counts: {total: number; eligible_at_10: number; dropped_at_10: number;
    dropped_incomplete: number; included: number};
  clusters: {id: string; label_zh: string; label_en: string; n: number; share: number;
    ct_win_rate: number; ct_win_ci95: [number,number]; region_shares_15s: RegionShares;
    push_depth: number; trajectories: Snapshot[]; medoid: RoundRef;
    context_preferences: Record<string, {n: number; share: number|null;
      map_share: number; difference_pp: number|null}>}[];
  chi_square: {statistic: number; dof: number; p: number; economy_types: string[];
    observed: number[][]; min_expected: number|null; caveat: string|null};
  fingerprints: {team: string; n: number;
    usage: {cluster_id: string; share: number; pro_share: number; difference_pp: number}[]}[];
  embedding: {method: 'pca_2d'; points: (RoundRef & {cluster_id: string; x: number; y: number})[]};
}
interface AILab {
  schema_version: 1; method: string; metadata: Record<string, unknown>;
  model_accuracy: Record<string, unknown>|null; // exact winprob_metrics.json payload
  attention: {map: string; cluster_id: string; round: RoundRef; method: 'distance_kernel';
    tau: number; snapshots: (Snapshot & {alpha: number[][]})[]}[];
  shap: {method: string; groups: string[]; background_size: number;
    limitations: string[]; rounds: {map: string; demo_id: string; round_num: number;
      showcase_team: string; model: string; background_n: number;
      states: {t_s: number; base_value: number; t_win_prob: number;
        shap_values: Record<string,number>; observed_t_control: number|null}[]}[]};
  control: null | {map: string; demo_id: string; round_num: number; grid_size: 15;
    method: string; cells: {index: number; gx: number; gy: number; radar_x: number;
      radar_y: number; occupied: boolean}[];
    snapshots: {phase: 'round_start'|'before_execute'|'after_plant'; t_s: number;
      ownership: ('T'|'CT'|'neutral')[]; delta_distance: (number|null)[];
      t_control: number|null}[];
    smoke_simulation: {t_s: number; center_world: number[]; center_radar: number[];
      radius_units: number; penalty_units: 450; ownership_before: string[];
      ownership_after: string[]; t_control_before: number|null;
      t_control_after: number|null; difference_pp: number|null}};
  references: {id: string; title: string; authors: string; venue: string;
    year: number; url: string; doi?: string}[];
}
```

Cluster IDs `C0`…`C5` are assigned by ascending mean 15s A share, with full spatial centroid as deterministic tie break. Labels derive from observed region shares and CT-to-T depth; colliding labels include the strongest distinguishing observed feature. Trajectory slots are CT members sorted at 15s by A/MID/B/CT_SPAWN/OTHER, depth, Steam ID, then held fixed through time. Mean trajectories use majority observed floor. Later dead members retain their observed positions; no missing snapshot is fabricated. The attention matrices include self edges and are row normalised, computed as `softmax(exp(-distance/4215.87/tau))`, tau=0.25, with world XYZ distances. They are **distance kernels, not learned attention**.

Context preferences are the fraction of cluster rounds in each context minus that fraction across the map; `after_loss` follows the same team across side swaps. Chi-square uses all observed economy categories, including pistol, with a sparse-cell warning. Fingerprints require at least 30 included CT rounds.

Shapley explains the existing calibrated match-held-out model via exact 64-coalition enumeration and a deterministic same-map, training-match-only background of up to 32 states. Six groups: `alive_diff`, `hp_equipment`, `map_control`, `bomb_state_time`, `active_utility`, `positional_spread_pinch`. Map and pre-round score are held fixed. `map_control` intervenes on existing lane occupancy inputs; `observed_t_control` exposes the replay grid metric separately. The current model does not consume `t_control`, active utility or spread/pinch; the latter two therefore have exactly zero attribution. This is disclosed in `shap.limitations`; no surrogate contributions are invented. `base_value + sum(shap_values) == t_win_prob` within 1e-6, in probability space. Explained probabilities have full precision and can differ from rounded replay values.

Control exports 225 cells; `occupied=false` cells are neutral and excluded from control fractions, preserving the existing replay grid's observed-cell mask. Distances use straight world XY segments, not NavMesh; smoke adds 450 units to each segment intersecting its disc before nearest-player minimisation. Smoke effect may be positive, negative, or zero. `delta_distance` = nearest CT distance − nearest T distance in world units (not travel seconds). Floors/walls are not modelled in the Mirage example. After-plant uses the first sampled second at/after the actual plant. References are restricted to the six verified items in the brief.
