import { getIndex, useData } from "../data";
import { useLang } from "../i18n";
import { matchDateLabel, type TimeRange } from "../matchDates";
import type { MatchDateInfo } from "../types";
import Segmented from "./Segmented";

export default function MatchDate({ match }: { match: MatchDateInfo }) {
  const lang = useLang();
  const titles = lang === "zh" ? {
    day: "估算日期：按 HLTV 系列赛编号顺序均匀分布于赛事日期范围，并非实际比赛日。",
    event: "仅知赛事日期范围；使用赛事开始日期，实际比赛日未知。",
    exact: "人工核实的比赛日期。",
    unknown: "比赛日期未知。",
  } : {
    day: "Estimated date: HLTV series IDs ordered and spaced across the event schedule; actual match day is unverified.",
    event: "Event dates only; event start is used internally. Actual match day is unknown.",
    exact: "Manually verified match date.",
    unknown: "Match date unknown.",
  };
  return <span className="match-date" data-date={match.date ?? ""} data-precision={match.date_precision ?? "unknown"} title={titles[match.date_precision ?? "unknown"]}>
    {matchDateLabel(match) || (lang === "zh" ? "日期未知" : "Date unknown")}
  </span>;
}

export function MatchTimeFilter({ value, onChange }: { value: TimeRange; onChange: (value: TimeRange) => void }) {
  const lang = useLang();
  const { data } = useData(getIndex, []);
  const labels = lang === "zh" ? ["全部", "近 3 个月", "近 1 个月"] : ["All", "Last 3 months", "Last month"];
  return <Segmented className="match-time-filter" aria-label={lang === "zh" ? "比赛时间" : "Match time"} title={data?.data_through ? `${lang === "zh" ? "数据截至" : "Data through"} ${data.data_through}` : undefined}>
    {(["all", "3", "1"] as TimeRange[]).map((range, i) => <button type="button" key={range} aria-pressed={value === range} disabled={range !== "all" && !data?.data_through} onClick={() => onChange(range)}>{labels[i]}</button>)}
  </Segmented>;
}
