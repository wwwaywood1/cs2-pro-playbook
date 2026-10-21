import CountUp from "./CountUp";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  title?: string;
}

export default function Stat({ label, value, sub, title }: Props) {
  return (
    <div className="stat" title={title}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{typeof value === "number" ? <CountUp value={value} /> : typeof value === "string" && /^-?\d[\d,.]*(?:%|s)?$/.test(value) ? <CountUp text={value} /> : value}</span>
      {sub ? <span className="stat-sub">{sub}</span> : null}
    </div>
  );
}
