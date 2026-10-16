#!/bin/zsh
# fm コマンドで tinytowngen の引数を生成し、tinytowngen で画像を描く。
#
#   ./tinytown_fm.sh "13x7 の平安京。中央に大路、左上に寺院"
#
# モデルの出力は JSON スキーマで縛り、コマンドラインはこのスクリプトが組み立てる
# (モデルが書いた文字列をシェルで評価しない)。tinytowngen が失敗したら
# エラー文をモデルに返して直させる。tinytown_tool.py と同じく 3 回まで。
set -euo pipefail

SCRIPT_DIR=${0:A:h}
OUTPUT_DIR=$SCRIPT_DIR/output
MAX_ATTEMPTS=3
SCALE=2

TINYTOWNGEN=${TINYTOWNGEN:-$(command -v tinytowngen || echo "$SCRIPT_DIR/.venv/bin/tinytowngen")}
[[ -x $TINYTOWNGEN ]] || { echo "tinytowngen が見つかりません: $TINYTOWNGEN" >&2; exit 1; }
command -v jq >/dev/null || { echo "jq が必要です" >&2; exit 1; }

PROMPT=${*:-"13x7 の平安京の街を描いて。中央に大路、左上に寺院。"}

# tinytown_tool.py の LAYOUT_GUIDE と同じ文面
LAYOUT_GUIDE='Layout tokens (space separated, tile coords are 0-based {x,y} from top-left):
  C{x,y}      commercial block (1 tile); x/y may be a range: C{0-3,0-1}
  B{x,y}      building under construction
  U1{x,y} U2{x,y} U3{x,y} U1x2{x,y} U2x1{x,y}  park/forest, top-left at {x,y}
  F{r}        boulevard on horizontal road r (1..H-1); F{r,x0-x1} for part of it
  W{c}        canal on vertical road c (1..W-1); W{c,y0-y1} for part of it
  C*  B*      fill all remaining tiles (put last)
Tokens must not overlap, and F/W must not cross a park.
Example (13x7): U3{0,0} U2{9,4} F{3} W{5} B{7,1} C*'

INSTRUCTIONS="You design small grid cities. Reply with the arguments for the tinytowngen renderer.
$LAYOUT_GUIDE"

# TinyTownArgs (tinytown_tool.py) と同じ項目。filename は使わず出力先はこちらで決める
# fm は x-order (プロパティの生成順) がないと "data is missing" で読み込みに失敗する
SCHEMA='{
  "type": "object",
  "title": "TinyTownArgs",
  "properties": {
    "layout": {"type": "string", "description": "Layout tokens, e.g. '\''U3{0,0} F{3} W{5} C*'\''"},
    "grid":   {"type": "string", "description": "Grid size WxH in tiles, e.g. 13x7"},
    "map":    {"type": "string", "enum": ["sapporo", "heiankyo11c"],
               "description": "sapporo = modern city, heiankyo11c = ancient Kyoto"},
    "seed":   {"type": "integer", "minimum": 1, "maximum": 999,
               "description": "Seed for building variations"}
  },
  "x-order": ["grid", "map", "layout", "seed"],
  "required": ["layout", "grid", "map", "seed"],
  "additionalProperties": false
}'

mkdir -p "$OUTPUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
OUTPUT=$OUTPUT_DIR/fm-$STAMP.png
TRANSCRIPT=$OUTPUT_DIR/fm-$STAMP.transcript.json

message=$PROMPT
for attempt in $(seq 1 $MAX_ATTEMPTS); do
  # 2 回目以降は前回の会話を引き継ぐ。instructions は transcript に入っているので
  # 渡せない (-i と --resume は併用不可)
  context=(-i "$INSTRUCTIONS")
  (( attempt > 1 )) && context=(--resume "$TRANSCRIPT")

  args_json=$(fm respond --no-stream "${context[@]}" --schema "$SCHEMA" \
    --save-transcript "$TRANSCRIPT" "$message")

  if ! jq -e '.layout and .grid and .map and .seed' <<<"$args_json" >/dev/null 2>&1; then
    echo "fm の出力が JSON として読めません:" >&2
    echo "$args_json" >&2
    exit 1
  fi

  layout=$(jq -r .layout <<<"$args_json")
  grid=$(jq -r .grid <<<"$args_json")
  map=$(jq -r .map <<<"$args_json")
  seed=$(jq -r .seed <<<"$args_json")

  cmd=("$TINYTOWNGEN" -l "$layout" -g "$grid" -m "$map" -s "$seed" --scale "$SCALE" -o "$OUTPUT")
  echo "[$attempt/$MAX_ATTEMPTS] ${(q-)cmd[@]}"

  if err=$("${cmd[@]}" 2>&1 >/dev/null); then
    echo "生成しました: $OUTPUT"
    exit 0
  fi

  echo "$err" >&2
  message="Failed. Fix the layout and reply with corrected arguments.
$err"
done

echo "$MAX_ATTEMPTS 回失敗しました" >&2
exit 1
