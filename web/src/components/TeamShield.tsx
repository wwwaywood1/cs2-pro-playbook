/** Shared neutral placeholder until the owner supplies a real team logo. */
export default function TeamShield({ name }: { name: string }) {
  const known: Record<string, string> = { "natus vincere": "NAVI", "the mongolz": "MONGOLZ", "ninjas in pyjamas": "NIP" };
  const short = known[name.toLowerCase()] ?? name.replace(/^team\s+/i, "").slice(0, 10).toUpperCase();
  return <svg className="team-shield" viewBox="0 0 100 100" aria-hidden="true">
    <path d="M50 6 88 19v32c0 20-17 34-38 43C29 85 12 71 12 51V19Z" fill="#16202a" stroke="#46515c" strokeWidth="2" />
    <text x="50" y="51" textAnchor="middle" dominantBaseline="middle" fill="#c5cdd5" fontSize={short.length > 7 ? 10 : 13} fontWeight="700">{short}</text>
  </svg>;
}
