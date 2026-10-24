export interface RoundRef { demo_id: string; round_num: number; team: string; economy: string; score: { ct: number; t: number } }
/** Positions are already transformed by the exporter onto the existing 1024px radar. */
export interface Snapshot { t_s: number; positions: number[][] }
export interface CTPatterns {
  map: string; method: string;
  metadata: { min_cluster_size: number; clustering_note: string; later_deaths: string };
  counts: { included: number; dropped_outlier: number };
  clusters: { id: string; label_zh: string; label_en: string; n: number; share: number;
    ct_win_rate: number; ct_win_ci95: [number, number]; trajectories: Snapshot[]; medoid: RoundRef;
    context_preferences: Record<string, { n: number; share: number | null; map_share: number; difference_pp: number | null }> }[];
  chi_square: { statistic: number; dof: number; p: number; min_expected: number | null; caveat: string | null };
  fingerprints: { team: string; n: number; usage: { cluster_id: string; share: number; pro_share: number; difference_pp: number }[] }[];
  embedding: { method: string; points: (RoundRef & { cluster_id: string; x: number; y: number })[] };
}
interface Metrics { accuracy: number; log_loss: number; brier: number }
export interface AILab {
  method: string; metadata: { paper_scope: string; attention: string };
  model_accuracy: { rows: number; matches: number; folds: number; model: Metrics; model_uncalibrated: Metrics; baseline_alive_time: Metrics } | null;
  attention: { map: string; cluster_id: string; round: RoundRef; method: string; tau: number; snapshots: (Snapshot & { alpha: number[][] })[] }[];
  shap: { method: string; groups: string[]; background_size: number; limitations: string[];
    rounds: { map: string; demo_id: string; round_num: number; showcase_team: string; model: string; background_n: number;
      states: { t_s: number; base_value: number; t_win_prob: number; shap_values: Record<string, number>; observed_t_control: number | null }[] }[] };
  control: null | { map: string; demo_id: string; round_num: number; grid_size: number; method: string;
    cells: { index: number; gx: number; gy: number; radar_x: number; radar_y: number; occupied: boolean }[];
    snapshots: { phase: string; t_s: number; ownership: string[]; delta_distance: (number | null)[]; t_control: number | null }[];
    smoke_simulation: { t_s: number; center_radar: number[]; radius_units: number; penalty_units: number; ownership_before: string[]; ownership_after: string[]; t_control_before: number | null; t_control_after: number | null; difference_pp: number | null } };
  references: { id: string; title: string; authors: string; venue: string; year: number; url: string; doi?: string }[];
}
