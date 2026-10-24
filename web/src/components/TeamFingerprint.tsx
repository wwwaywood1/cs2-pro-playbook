import { getCTPatterns, useData } from "../data";
import { fmtPct } from "../format";
import { signedPP } from "./CTDefense";
import "../lab.css";

export default function TeamFingerprint({ map, team }: { map: string; team: string }) {
  const { data } = useData(() => getCTPatterns(map), [map]);
  const fingerprint = data?.fingerprints.find(f => f.team.toLowerCase() === team.toLowerCase());
  if (!data || !fingerprint || fingerprint.n < 30) return null;
  return <section className="team-fingerprint panel" aria-label="CT 阵型指纹" data-team={team} data-n={fingerprint.n}>
    <h3>CT 阵型指纹</h3><p>{team} · {fingerprint.n} 个 CT 回合 · 与同图全部职业样本比较</p>
    {fingerprint.usage.map(row => <div className="fingerprint-row" key={row.cluster_id} data-cluster-id={row.cluster_id} data-share={row.share} data-pro-share={row.pro_share}>
      <strong>{data.clusters.find(c => c.id === row.cluster_id)?.label_zh ?? row.cluster_id}</strong>
      <div className="fingerprint-bar"><span>战队 {fmtPct(row.share)}</span><div className="bar-track"><i style={{ width: `${row.share * 100}%` }} /></div></div>
      <div className="fingerprint-bar is-league"><span>全图 {fmtPct(row.pro_share)}</span><div className="bar-track"><i style={{ width: `${row.pro_share * 100}%` }} /></div></div>
      <small>{signedPP(row.difference_pp)}</small>
    </div>)}
  </section>;
}
