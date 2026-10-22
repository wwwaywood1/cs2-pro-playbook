import { Fragment } from "react";
import { Link } from "react-router-dom";
import { calloutLabel, useLang } from "../i18n";
import type { TeamProfile, TacticsFile } from "../types";

/** Link only names backed by this team's signature recipe; never infer a recipe from prose. */
export default function TeamSummaryLinks({ profile, tactics }: { profile: TeamProfile; tactics?: TacticsFile | null }) {
  const lang = useLang();
  const id = profile.insights?.find((insight) => insight.id === "t_signature_recipe" && insight.recipe_id)?.recipe_id
    ?? profile.tactics?.T.recipes[0]?.value;
  const recipe = tactics?.recipes.find((item) => item.id === id);
  const text = profile.summary?.[lang] || (profile.insights ?? []).slice(0, 3).map((insight) => insight.text[lang]).join("；");
  if (!recipe) return text ? <span>{text}</span> : null;
  const to = `/${profile.map}/tactics?recipe=${encodeURIComponent(recipe.id)}`;
  const spots = [...recipe.core, ...recipe.options];
  const names = [...new Set(spots.flatMap((spot) => [spot.name?.[lang], calloutLabel(profile.map, spot.place)])
    .filter((name): name is string => !!name && name !== "—"))].sort((a, b) => b.length - a.length);
  // Match literal names (including punctuation) without treating export text as markup.
  const parts: { text: string; link: boolean }[] = [];
  let rest = text;
  while (rest) {
    const match = names.map((name) => ({ name, index: rest.indexOf(name) })).filter((item) => item.index >= 0)
      .sort((a, b) => a.index - b.index || b.name.length - a.name.length)[0];
    if (!match) { parts.push({ text: rest, link: false }); break; }
    if (match.index) parts.push({ text: rest.slice(0, match.index), link: false });
    parts.push({ text: match.name, link: true });
    rest = rest.slice(match.index + match.name.length);
  }
  return <span className="team-recipe-summary">
    {parts.map((part, index) => part.link ? <Link key={index} to={to}>{part.text}</Link> : <Fragment key={index}>{part.text}</Fragment>)}
    <span className="team-signature">招牌套路：{recipe.core.map((spot, index) => <Fragment key={spot.spot_id}>
      {index ? " + " : ""}<Link to={to}>{spot.name?.[lang] || calloutLabel(profile.map, spot.place) || spot.label}</Link>
    </Fragment>)}</span>
    <Link className="team-recipe-cta" to={to}>查看该套路落点 →</Link>
  </span>;
}
