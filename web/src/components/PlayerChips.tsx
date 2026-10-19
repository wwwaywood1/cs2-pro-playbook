import { playerColor } from "../heatmap";
import { t } from "../i18n";
import type { RosterEntry, Side } from "../types";

interface PlayerChipsProps {
  roster: RosterEntry[];
  side: Side;
  selected: string[];
  onChange: (players: string[]) => void;
}

export default function PlayerChips({ roster, side, selected, onChange }: PlayerChipsProps) {
  const available = roster.filter((player) => player.rounds[side] > 0);
  return (
    <fieldset className="hm-field">
      <legend>{t("heatmap.players")}</legend>
      <div className="hm-actions">
        <button type="button" onClick={() => onChange(available.map((player) => player.steamid))}>
          {t("heatmap.select_all")}
        </button>
        <button type="button" onClick={() => onChange([])}>{t("heatmap.select_none")}</button>
      </div>
      <div className="hm-chips">
        {available.map((player) => (
          <label key={player.steamid} className="hm-chip">
            <input
              type="checkbox" checked={selected.includes(player.steamid)}
              onChange={(event) => onChange(event.target.checked
                ? [...selected, player.steamid]
                : selected.filter((id) => id !== player.steamid))}
            />
            <span className="hm-swatch" style={{ backgroundColor: playerColor(player.color).deep }} aria-hidden="true" />
            <span>{player.name}</span>
            <small>{t("heatmap.rounds", { n: player.rounds[side] ?? "—" })}</small>
            {player.low_sample[side] && <small className="hm-low">{t("heatmap.low_sample")}</small>}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
