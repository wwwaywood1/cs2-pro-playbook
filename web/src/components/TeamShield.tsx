const KNOWN: Record<string, string> = {
  "natus vincere": "NAVI", "the mongolz": "MONGOLZ", "ninjas in pyjamas": "NIP",
  "thunderdownunder": "TDU", "100 thieves": "100T", "gaimin gladiators": "GAIMIN", "9ine pusulabet": "9INE",
};

/** Short shield text: a known abbreviation, the whole name, or its first word; never cut mid-word. */
export function shieldLabel(name: string): string {
  const clean = name.replace(/^team\s+/i, "").trim();
  const known = KNOWN[clean.toLowerCase()];
  if (known) return known;
  const words = clean.split(/\s+/).filter(Boolean);
  return (clean.length <= 10 || words.length < 2 ? clean : words[0]).toUpperCase();
}

/** Shared neutral placeholder until the owner supplies a real team logo. */
export default function TeamShield({ name }: { name: string }) {
  const short = shieldLabel(name);
  // A single long word is condensed to the shield width rather than truncated.
  const squeeze = short.length > 10 ? { textLength: 72, lengthAdjust: "spacingAndGlyphs" as const } : {};
  return <svg className="team-shield" viewBox="0 0 100 100" aria-hidden="true">
    <path d="M50 6 88 19v32c0 20-17 34-38 43C29 85 12 71 12 51V19Z" fill="#16202a" stroke="#46515c" strokeWidth="2" />
    <text x="50" y="51" textAnchor="middle" dominantBaseline="middle" fill="#c5cdd5" fontSize={short.length > 7 ? 10 : 13} fontWeight="700" {...squeeze}>{short}</text>
  </svg>;
}
