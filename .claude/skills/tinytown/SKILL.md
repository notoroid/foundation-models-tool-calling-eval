---
name: tinytown
description: 街の説明（日本語可）から tinytowngen で上空画像 PNG を生成する。tinytown_tool.py が fm モデルに与えているのと同じガイドだけを使う。「〜な街を描いて」「tinytown で街を生成」などの依頼で使う。
argument-hint: "<描きたい街の説明>"
allowed-tools: Bash(.venv/bin/tinytowngen *), Bash(mkdir -p output)
---

# tinytown: 街の画像を生成する

ユーザーの説明（`$ARGUMENTS`）に合う街を設計し、tinytowngen で PNG を生成する。

この Skill は、`tinytown_tool.py` の `render_town` ツールを Claude が代わりに実行するものである。
fm（オンデバイスモデル）と同じ条件で比べられるよう、**使ってよい情報は下の「ガイド」と「引数」だけ**とする。
`tinytowngen --help`、README、tinytowngen のソースコードは読まないこと。

## ガイド（tinytown_tool.py の LAYOUT_GUIDE と同じ）

```
Layout tokens (space separated, tile coords are 0-based {x,y} from top-left):
  C{x,y}      commercial block (1 tile); x/y may be a range: C{0-3,0-1}
  B{x,y}      building under construction
  U1{x,y} U2{x,y} U3{x,y} U1x2{x,y} U2x1{x,y}  park/forest, top-left at {x,y}
  F{r}        boulevard on horizontal road r (1..H-1); F{r,x0-x1} for part of it
  W{c}        canal on vertical road c (1..W-1); W{c,y0-y1} for part of it
  C*  B*      fill all remaining tiles (put last)
Tokens must not overlap, and F/W must not cross a park.
Example (13x7): U3{0,0} U2{9,4} F{3} W{5} B{7,1} C*
```

## 引数（TinyTownArgs と同じ）

| 引数 | 内容 |
|---|---|
| layout | 上のガイドに従った配置文字列 |
| grid | グリッドサイズ `WxH`（例: `13x7`） |
| map | `sapporo`（現代都市）か `heiankyo11c`（平安京）のどちらか |
| seed | 建物のバリエーションを決めるシード（1〜999） |
| filename | 出力ファイル名（`.png`）。ディレクトリを含めない |

## 手順

1. 説明から 5 つの引数を決める。サイズの指定がなければ `13x7`、シードの指定がなければ `1` にする。
2. プロジェクトのルートで、次のように実行する（`tinytown_tool.py` と同じ `--scale 2` を付け、出力は `output/` に限る）。

   ```bash
   mkdir -p output
   .venv/bin/tinytowngen -l "<layout>" -g <grid> -m <map> -s <seed> --scale 2 -o output/<filename>
   ```

3. 失敗した場合（終了コードが 0 以外）は、stderr のエラーメッセージを読み、layout などを直して再実行する。
   - **エラーが 3 回に達したら、そこでやめる。** 4 回目は実行せず、失敗したことと、3 回分のエラー内容をユーザーに伝える（[Doc/evaluation.md](../../../Doc/evaluation.md) の判定ルールと同じ）。
4. 成功したら、生成した画像を Read で開き、説明どおりの街になっているか確かめる。
5. 次の内容を日本語で報告する。
   - 出力ファイルのパス
   - 最終的なコマンドの引数
   - 実行回数とエラー回数
   - 説明と合わない点があれば、その内容
