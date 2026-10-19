# GPT-06：道具落点命名（交给 GPT，需要看图）

> 用法：在 ChatGPT 里从分割线开始粘贴下面的内容，并**上传 5 个附件**（都在 `delegation/inputs/spots/`）：
> `spots_to_name.csv`、`de_mirage_T.png`、`de_mirage_CT.png`、`de_inferno_T.png`、`de_inferno_CT.png`。
> 产出是两个配置文件 `config/spots/de_mirage.toml` 和 `config/spots/de_inferno.toml`，把职业比赛里统计出的道具落点起上大家熟悉的名字（比如 "CT smoke / 警家烟"），网站上的"职业爆弹套路"和选手道具卡片都会用到。

---

We cluster where professional CS2 teams' grenades land. Each cluster ("spot") is one landing place, whatever the throw position. Right now spots only carry the nearest map callout (for example `BombsiteA #2`), which players do not recognise. Give each spot the name the CS community actually uses, in English and Simplified Chinese.

Attachments:
- `spots_to_name.csv`: one row per spot, maps Mirage and Inferno. Columns: `map, spot_id, short_id, side (who threw it), type (smoke/molotov), callout (nearest callout name), x, y, z (game units), radar_x, radar_y (pixels on the 1024 x 1024 radar image), n_throws, n_matches, median_pop_t_s (seconds into the round when it usually pops), used_in_recipes (A:r01 = part of the first A-site execute recipe), en, zh` (the last two are empty for you to fill).
- `<map>_<side>.png`: the radar with every spot drawn (grey circle = smoke, orange triangle = molotov), labelled with `short_id`, plus callout names in cyan at the centre of each callout area.

How to name:
- Use standard community names: e.g. Mirage T side "Window smoke", "Stairs smoke", "Jungle smoke", "CT smoke", "Top-mid smoke", "Shop smoke", "Firebox molotov"; Inferno "Coffins smoke", "CT smoke (B)", "Library smoke", "Arch smoke", "Pit molotov", "Banana molotov". Chinese: the names Chinese players use (e.g. "VIP 狙位烟", "警家烟", "丛林烟", "楼梯烟", "棺材烟", "图书馆烟", "拱门烟", "香蕉道火"), not literal translations.
- Use timing as a clue: smokes popping in the first ~15 s are map-control smokes (e.g. Mirage window and top-mid smokes), 25–70 s are usually execute smokes.
- Side matters: CT-side spots are defensive or retake utility (e.g. CT molotov on T ramp, CT smoke on short).
- If two spots are the same smoke thrown slightly differently, give both the same name and add a short qualifier, e.g. "Jungle smoke (deep)".
- If you are not sure what players call a spot, describe it by location instead ("smoke between Jungle and Stairs" / "丛林与楼梯之间的烟") and mark it `confidence = "low"`. Do not invent names.

Deliverable — two TOML files, one entry per spot, coordinates copied from the CSV (`x`, `y`, not radar pixels):

```toml
# config/spots/de_mirage.toml
[[spot]]
id = "de_mirage-t-smoke-s157"   # spot_id from the CSV (for traceability; matching uses x/y)
side = "T"
type = "smoke"
x = -320.5
y = -1460.0
radius = 200                     # 200 for smokes, 150 for molotovs
en = "Stairs smoke"
zh = "楼梯烟"
confidence = "high"              # high / medium / low
```

Return both files in full, then a short list of the spots you marked `low` and why.
