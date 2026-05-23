# GGS Othello Live Collector

GGS・・eneric Game Server・峨・Othello繧ｵ繝ｼ繝薙せ `/os` 縺ｫ蟶ｸ譎よ磁邯壹＠縲・ｲ陦御ｸｭ蟇ｾ螻繧定ｦｳ謌ｦ縺励※縲・*繝ｫ繝ｼ繝ｫ荳翫■繧・ｓ縺ｨ邨ょｱ縺励◆譽玖ｭ懊・縺ｿ**菫晏ｭ倥☆繧輝ython繝励Ο繧ｰ繝ｩ繝縺ｧ縺吶・
- `history` / `shistory` 縺ｯ菴ｿ逕ｨ縺励∪縺帙ｓ縲・- `t /os match` 縺ｧ騾ｲ陦御ｸｭ蟇ｾ螻繧定ｦ九▽縺代∪縺吶・- `t /os watch + .<match_id>` 縺ｨ `t /os moves .<match_id>` 繧剃ｽｵ逕ｨ縺励※逹謇九ｒ蜿朱寔縺励∪縺吶・- 蜿朱寔縺ｧ縺阪ｋ縺ｮ縺ｯ縲梧磁邯壻ｸｭ縺ｫ隕ｳ謌ｦ縺ｧ縺阪◆蟇ｾ螻縲阪・縺ｿ縺ｧ縺吶・
## Files

- `ggs_othello_collector.py`: 繝｡繧､繝ｳCLI・亥ｸｸ鬧仙庶髮・ｼ・- `ggs_client.py`: TCP謗･邯壹√Ο繧ｰ繧､繝ｳ縲∝・謗･邯壹・∝女菫｡
- `ggs_parser.py`: GGS/GGF陦後ヱ繝ｼ繧ｹ
- `othello.py`: 8x8 Othello蜷域ｳ墓焔讀懆ｨｼ縺ｨ逶､髱｢譖ｴ譁ｰ
- `storage.py`: 豁｣蟶ｸ邨ょｱ險倬鹸繝ｻ繧ｨ繝ｩ繝ｼ繝ｭ繧ｰ菫晏ｭ・- `models.py`: dataclass螳夂ｾｩ
- `tests/`: pytest繝・せ繝・
## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install pytest
```

Python 3.9+ 繧呈Φ螳壹＠縺ｦ縺・∪縺吶・
## Run

```bash
python ggs_othello_collector.py --username YOUR_GGS_NAME
```

繝代せ繝ｯ繝ｼ繝画欠螳壽婿豕包ｼ亥━蜈磯・ｼ・
1. `--password`
2. 迺ｰ蠅・､画焚 `GGS_PASSWORD`
3. 蟇ｾ隧ｱ蜈･蜉・
萓・

```bash
python ggs_othello_collector.py --username foo --poll-interval 30 --max-watches 200
python ggs_othello_collector.py --username foo --once --verbose
python ggs_othello_collector.py --username foo --dry-run
```

## CLI options

- `--host` (default: `skatgame.net`)
- `--port` (default: `5000`)
- `--username` (required)
- `--password`
- `--out-dir` (default: `records`)
- `--raw-log-dir` (default: `raw_logs`)
- `--poll-interval` (default: `30`)
- `--max-watches` (default: `200`)
- `--once`  
  1蝗槭□縺・`match` 繧貞叙繧翫『atch荳ｭ縺ｮ蟇ｾ螻縺後☆縺ｹ縺ｦ邨ゅｏ縺｣縺溘ｉ邨ゆｺ・- `--dry-run`  
  菫晏ｭ倥・陦後ｏ縺壹√Ο繧ｰ縺ｨ讀懆ｨｼ縺ｮ縺ｿ
- `--verbose`

## 菫晏ｭ倅ｻ墓ｧ・
豁｣蟶ｸ邨ょｱ縺励◆譽玖ｭ懊・縺ｿ菫晏ｭ倥＠縺ｾ縺吶ゆｿ晏ｭ倥・ `.tmp` 繝・ぅ繝ｬ繧ｯ繝医Μ縺ｫ譖ｸ縺・◆蠕後～os.replace` 縺ｧ蜴溷ｭ千噪縺ｫ蜈ｬ髢九＠縺ｾ縺吶・
菫晏ｭ伜・:

`<out-dir>/discs_NN/YYYYMMDD_HHMMSS_<match_id>_<black>_vs_<white>/`

- `NN` 縺ｯ蛻晄悄逶､髱｢縺ｮ遏ｳ謨ｰ・磯ｻ・逋ｽ・峨・繧ｼ繝ｭ蝓九ａ2譯・- 萓・ `discs_04`, `discs_14`

菫晏ｭ倥ヵ繧｡繧､繝ｫ:

1. `record.txt`  
   1陦檎岼: 蛻晄悄逶､髱｢64譁・ｭ暦ｼ・X`/`O`/`-`・・ 
   2陦檎岼: 蛻晄悄謇狗分・・black` or `white`・・ 
   3陦檎岼: pass髯､螟悶さ繝ｳ繝代け繝育捩謇句・・・f5d6c3...`・・ 
   4陦檎岼: 螳牙・逹謇句・・・f5 d6 pass c3 ...`・・
2. `metadata.json`  
   match ID縲√・繝ｬ繧､繝､繝ｼ蜷阪“ame type縲・幕蟋狗ｵゆｺ・凾蛻ｻ縲∝・譛溽浹謨ｰ縲∝・譛溽乢髱｢縲∫捩謇句・縲∵怙邨ら乢髱｢縲∵怙邨ら浹謨ｰ縲∫ｵ先棡縲〉aw log蜿ら・縺ｪ縺ｩ

3. `raw.txt`  
   縺昴・match縺ｫ邏舌▼縺・◆逕溘Ο繧ｰ

## 縲檎ｵょｱ縺励◆譽玖ｭ懊・縺ｿ菫晏ｭ倥阪・蛻､螳・
莉･荳九ｒ縺吶∋縺ｦ貅縺溘＠縺溷ｴ蜷医・縺ｿ菫晏ｭ・

1. 閾ｪ蜑弘thello讀懆ｨｼ縺ｧ蜈ｨ逹謇九′蜷域ｳ・2. 邨ょｱ譚｡莉ｶ繧呈ｺ縺溘☆  
   - 64繝槭せ蝓九∪繧・ 
   - 荳｡閠・粋豕墓焔縺ｪ縺・ 
   - 騾｣邯嗔ass邨ょｱ
3. `RE[...]` 遲峨↓ resign / timeout / mutual score / stored / abort / break 繧堤､ｺ縺呎ュ蝣ｱ縺後↑縺・4. 邨先棡謨ｰ蛟､・・RE[+2.00]` 遲会ｼ峨′隱ｭ繧√ｋ蝣ｴ蜷医・譛邨ら浹蟾ｮ縺ｨ謨ｴ蜷・5. 蛻晄悄逶､髱｢縺悟叙蠕励〒縺阪ｋ  
   - 蜿門ｾ励〒縺阪↑縺・ｴ蜷医・縲∵ｨ呎ｺ門・譛溷ｱ髱｢縺ｨ蛻､譁ｭ縺ｧ縺阪ｋ game type 縺ｮ縺ｿ陬懷ｮ悟庄  
   - random蛻晄悄螻髱｢繧峨＠縺・game type 縺ｧ蛻晄悄逶､髱｢縺御ｸ肴・縺ｪ繧我ｿ晏ｭ倥＠縺ｪ縺・
菫晏ｭ倥＠縺ｪ縺・ｴ蜷医・ `errors/YYYYMMDD_HHMMSS_<match_id>.json` 縺ｫ逅・罰縺ｨ騾比ｸｭ繝・・繧ｿ繧呈ｮ九＠縺ｾ縺吶・
## raw log

`raw_logs/session_YYYYMMDD_HHMMSS.log` 縺ｫ騾∝女菫｡陦後ｒ繧ｿ繧､繝繧ｹ繧ｿ繝ｳ繝嶺ｻ倥″縺ｧ菫晏ｭ倥＠縺ｾ縺吶・ 
螳溘し繝ｼ繝仙・蜉帙′諠ｳ螳壼､悶〒繧ゅ〉aw log繧剃ｽｿ縺｣縺ｦ蠕後°繧峨ヱ繝ｼ繧ｵ謾ｹ蝟・〒縺阪∪縺吶・
## 諠ｳ螳壹＠縺ｦ縺・ｋGGS蜃ｺ蜉帛ｽ｢蠑・
謠ｺ繧後↓閠舌∴繧句ｮ溯｣・〒縺吶′縲∫音縺ｫ谺｡繧呈Φ螳壹＠縺ｦ縺・∪縺吶・
- match ID: `.78665`
- GGF token:
  - `BO[...]`・亥・譛溽乢髱｢・・  - `B[F5//1.23]`, `W[D6/0.5/0.1]`
  - `B[pass//0.68]`
  - `RE[+2.00]`, `RE[-64.00:r]`
- 蟷ｳ譁・・邨先棡繧ｭ繝ｼ繝ｯ繝ｼ繝・
  - `resign`, `timeout`, `mutual score`, `stored`, `abort`, `break`

## Tests

```bash
pytest -q
```

繝・せ繝亥・螳ｹ:

- Othello蜷域ｳ墓焔縲∫浹霑斐＠縲｝ass縲・｣邯嗔ass邨ょｱ縲・＆豕墓焔諡貞凄
- GGF繝代・繧ｵ・・BO`, `B[]`, `W[]`, `pass`, `RE`・・- 菫晏ｭ伜・ `discs_04` / `discs_14` 蛻・ｲ・- `.tmp` 邨檎罰atomic rename
- 蜷御ｸ逹謇九・驥崎､・匳骭ｲ髦ｲ豁｢

## Known limitation

GGS縺ｮ驕主悉譽玖ｭ懊・ `history` 縺九ｉ蠕ｩ蜈・〒縺阪↑縺・◆繧√・*謗･邯壻ｸｭ縺ｫ隕ｳ謌ｦ縺ｧ縺阪◆蟇ｾ螻縺ｮ縺ｿ**蜿朱寔縺ｧ縺阪∪縺吶・
## Additional Compact Batch Output

In addition to per-match directories, the collector also writes a compact line format.

- Directory: `<out-dir>/compact_batches/discs_NN/`
- `NN` is the initial disc count (zero-padded, e.g. `discs_04`, `discs_14`)
- File name: save start timestamp (UTC), for example `20260523_120000.txt`
- Max records per file: `10000` (then rotates to a new timestamped file)
- Line format:
  - `<initial_board_64> <X|O> <moves_compact>`
  - Example:
    - `------------------OOOO----OOXX---OXOXO----XXOO------O----------- X b4d7c7...`

Only rule-verified terminal games are written. In `--dry-run` mode, compact files are not written.

