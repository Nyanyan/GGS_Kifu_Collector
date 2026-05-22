# GGS Othello Live Collector

GGS（Generic Game Server）のOthelloサービス `/os` に常時接続し、進行中対局を観戦して、**ルール上ちゃんと終局した棋譜のみ**保存するPythonプログラムです。

- `history` / `shistory` は使用しません。
- `t /os match` で進行中対局を見つけます。
- `t /os watch + .<match_id>` と `t /os moves .<match_id>` を併用して着手を収集します。
- 収集できるのは「接続中に観戦できた対局」のみです。

## Files

- `ggs_othello_collector.py`: メインCLI（常駐収集）
- `ggs_client.py`: TCP接続、ログイン、再接続、送受信
- `parser.py`: GGS/GGF行パース
- `othello.py`: 8x8 Othello合法手検証と盤面更新
- `storage.py`: 正常終局記録・エラーログ保存
- `models.py`: dataclass定義
- `tests/`: pytestテスト

## Setup

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install pytest
```

Python 3.11+ を想定しています。

## Run

```bash
python ggs_othello_collector.py --username YOUR_GGS_NAME
```

パスワード指定方法（優先順）:
1. `--password`
2. 環境変数 `GGS_PASSWORD`
3. 対話入力

例:

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
  1回だけ `match` を取り、watch中の対局がすべて終わったら終了
- `--dry-run`  
  保存は行わず、ログと検証のみ
- `--verbose`

## 保存仕様

正常終局した棋譜のみ保存します。保存は `.tmp` ディレクトリに書いた後、`os.replace` で原子的に公開します。

保存先:

`<out-dir>/stones_NN/YYYYMMDD_HHMMSS_<match_id>_<black>_vs_<white>/`

- `NN` は初期盤面の石数（黒+白）のゼロ埋め2桁
- 例: `stones_04`, `stones_14`

保存ファイル:

1. `record.txt`  
   1行目: 初期盤面64文字（`X`/`O`/`-`）  
   2行目: 初期手番（`black` or `white`）  
   3行目: pass除外コンパクト着手列（`f5d6c3...`）  
   4行目: 安全着手列（`f5 d6 pass c3 ...`）

2. `metadata.json`  
   match ID、プレイヤー名、game type、開始終了時刻、初期石数、初期盤面、着手列、最終盤面、最終石数、結果、raw log参照など

3. `raw.txt`  
   そのmatchに紐づいた生ログ

## 「終局した棋譜のみ保存」の判定

以下をすべて満たした場合のみ保存:

1. 自前Othello検証で全着手が合法
2. 終局条件を満たす  
   - 64マス埋まり  
   - 両者合法手なし  
   - 連続pass終局
3. `RE[...]` 等に resign / timeout / mutual score / stored / abort / break を示す情報がない
4. 結果数値（`RE[+2.00]` 等）が読める場合は最終石差と整合
5. 初期盤面が取得できる  
   - 取得できない場合は、標準初期局面と判断できる game type のみ補完可  
   - random初期局面らしい game type で初期盤面が不明なら保存しない

保存しない場合は `errors/YYYYMMDD_HHMMSS_<match_id>.json` に理由と途中データを残します。

## raw log

`raw_logs/session_YYYYMMDD_HHMMSS.log` に送受信行をタイムスタンプ付きで保存します。  
実サーバ出力が想定外でも、raw logを使って後からパーサ改善できます。

## 想定しているGGS出力形式

揺れに耐える実装ですが、特に次を想定しています。

- match ID: `.78665`
- GGF token:
  - `BO[...]`（初期盤面）
  - `B[F5//1.23]`, `W[D6/0.5/0.1]`
  - `B[pass//0.68]`
  - `RE[+2.00]`, `RE[-64.00:r]`
- 平文の結果キーワード:
  - `resign`, `timeout`, `mutual score`, `stored`, `abort`, `break`

## Tests

```bash
pytest -q
```

テスト内容:

- Othello合法手、石返し、pass、連続pass終局、違法手拒否
- GGFパーサ（`BO`, `B[]`, `W[]`, `pass`, `RE`）
- 保存先 `stones_04` / `stones_14` 分岐
- `.tmp` 経由atomic rename
- 同一着手の重複登録防止

## Known limitation

GGSの過去棋譜は `history` から復元できないため、**接続中に観戦できた対局のみ**収集できます。

