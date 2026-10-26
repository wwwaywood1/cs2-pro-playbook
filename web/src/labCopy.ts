import { t, type Lang } from "./i18n";

// The AI lab and CT pattern exports carry English method ids and notes. Translate them
// at the presentation boundary; numbers, ids and citations stay as exported.
const LAB_COPY_ZH: Record<string, string> = {
  "Distance kernel, not learned attention; self edges included; tau=0.25": "基于距离的核权重，并非学习得到的注意力；包含自连接；温度参数 τ=0.25",
  "Existing model uses lane occupancies as spatial inputs; replay t_control is observed separately and is not a model feature.": "现有模型以通道占位作为空间输入；回放中的 T 控图率是独立观测指标，不属于模型特征。",
  "Active utility and positional spread/pinch are not inputs to the existing model and have zero attribution.": "场上道具、站位分散与夹击均未作为现有模型的输入，因此归因为零。",
  "Map and pre-round score are held fixed; background size is capped at 32 to bound export runtime.": "地图与回合开始前的比分保持固定；背景样本最多为 32 个，以限制导出耗时。",
  "Explains calibrated match-held-out model, not a separately trained surrogate.": "归因解释的是经过校准、按比赛留出的模型，并非另外训练的替代模型。",
  "Existing occupied 15x15 XY replay grid; straight-line nearest-player distances, no NavMesh or walls": "使用现有回放中有观测的 15×15 XY 网格，按最近玩家的直线距离计算；不包含导航网格或墙体",
  "Use recorded positions of the original five CT members, including dead members after 10s; drop incomplete/non-finite rounds.": "使用开局五名 CT 队员的记录位置（10 秒后阵亡的队员保留其记录位置）；剔除数据不完整或含非有限值的回合。",
  "Expected cells below 5; asymptotic p-value may be unreliable": "部分单元格的期望频数低于 5；渐近 p 值可能不可靠。",
};

const METHOD_ZH: Record<string, string> = {
  lightweight_standardised_pca_kmeans: "轻量标准化、主成分分析与 K 均值聚类",
  exact_interventional_group_shapley_64_coalitions: "精确干预式分组 Shapley 归因（64 种组合作用）",
  existing_hist_gradient_boosting_match_oof_plus_isotonic: "现有直方图梯度提升模型，按比赛留出预测并进行保序校准",
  pca_2d: "主成分分析二维投影",
};

/** Chinese copy for an exported English note; English mode and unknown notes stay as exported. */
export function labCopy(value: string, lang: Lang = "zh"): string {
  if (lang !== "zh") return value;
  const paper = value.match(/^TAGNet was validated on Dust2 only \(([^)]+) rounds\);/);
  if (paper) return `TAGNet 仅在 Dust2 上进行了验证（${paper[1]} 个回合）；本项目将轻量方法应用于所有已解析地图。下方结果均由本项目的比赛录像计算得出。`;
  const retained = value.match(/^K=(\d+) retained$/);
  if (retained) return `保留 ${retained[1]} 个簇（K=${retained[1]}）`;
  return LAB_COPY_ZH[value] ?? value;
}

/** Readable method name; the exported id remains available for citation. */
export function methodName(value: string, lang: Lang = "zh"): string {
  return lang === "zh" ? METHOD_ZH[value] ?? value : value.replace(/_/g, " ");
}

/** Economy and round-context keys share the site-wide buy-type wording (i18n buy.*). */
const CONTEXT_KEYS: Record<string, string> = {
  full_buy: "buy.full", trailing: "round6.context_trailing", leading: "round6.context_leading",
  tied: "round6.context_tied", after_loss: "round6.context_after_loss", mixed: "round6.context_mixed",
};
export function economyLabel(value: string): string {
  const key = CONTEXT_KEYS[value] ?? `buy.${value}`;
  const label = t(key);
  return label === key ? value : label;
}
