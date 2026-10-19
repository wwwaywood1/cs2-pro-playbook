# GPT-05：职业选手角色真值表（交给 GPT，需要联网查资料）

> 用法：在 ChatGPT（开启联网搜索）或 Codex 里，从分割线开始粘贴下面的内容，并**上传附件** `delegation/inputs/players_roster.csv`（155 名选手、31 支队伍）。
> 产出用来校准网站上的"角色标签"（狙击手、突破手、自由人、A/B 点防守等）。这些标签现在是按数据阈值猜的，没有标准答案，所以需要一份有出处的真值表。

---

Attached is `players_roster.csv`: the 155 players (31 teams) who appear in our dataset of professional CS2 matches from **IEM Cologne Major 2026** (June 2026). Columns `team, player, steamid, matches, rounds, maps` are filled; the rest are empty for you to fill.

For every player, research their role **at that event** (June 2026 roster and role, not today's) from public sources: Liquipedia player and team pages, HLTV articles and interviews, team announcements, analyst breakdowns. Fill:

| Column | Allowed values | Notes |
|---|---|---|
| `role_primary` | `awper`, `entry`, `lurker`, `support`, `anchor`, `rifler` | the one role sources agree on; `rifler` only if nothing more specific is documented |
| `role_secondary` | same values, or empty | |
| `is_igl` | `Y`, `N` | in-game leader at that event |
| `ct_position_mirage` | free text, e.g. `B anchor`, `A site`, `connector`, `mid`, `AWP (CT/window)` | only if a source says so; else empty |
| `ct_position_inferno` | free text, e.g. `B anchor (banana)`, `A site`, `mid/arch`, `AWP` | only if a source says so; else empty |
| `t_role_note` | short free text | e.g. "lurks B on Mirage", "first in on executes" |
| `sources` | URLs separated by ` ; ` | at least one per filled row |
| `confidence` | `high`, `medium`, `low` | high = stated directly by the player/team/major outlet; low = inferred from a single analyst remark |

Rules:
- **Do not guess.** If you cannot find a source for a field, leave it empty. An empty cell is useful; a wrong one is harmful, because we will measure our algorithm against this table.
- Use the player's own handle as in the file; if a player is a stand-in or coach-substitute at that event, say so in `t_role_note`.
- Do not change the existing columns or row order, and keep `steamid` as text (no scientific notation).

Deliverable: the completed CSV (same file name), plus a short note listing players you could not find anything for and any team whose roster at that event differs from the file.
