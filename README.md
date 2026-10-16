# foundation-models-tool-calling-eval

macOS 27 のオンデバイス基盤モデル（Apple Foundation Models）を [Foundation Models SDK for Python](https://github.com/apple/python-apple-fm-sdk)（`apple_fm_sdk`）から使い、
街の画像を生成する CLI [tinytowngen](https://github.com/notoroid/tinytowngen) を **Tool calling** で呼び出させて、
**モデルがどの程度複雑な指示をこなせるか**を評価した記録です。

## 結果の要約

指示の複雑さを 5 段階に分け、tinytowngen のエラーが 3 回に達したら失敗とする条件で評価しました。

| レベル | 内容 | 結果（ガイド修正後、5 回試行） |
|---|---|---|
| 1 | 全面を商業地区で埋める | 5 回中 3 回成功 |
| 2 | 大路と寺院（座標の指定なし） | 5 回中 4 回成功 |
| 3 | 座標を指定した要素 3 つ | 5 回中 1 回成功 |
| 4 | 交差の回避が 1 箇所必要 | 成功なし |
| 5 | 交差の回避が 3 箇所＋細かい指定 | 成功なし |

- このオンデバイスモデルが安定して扱えるのは、**座標を指定しない、要素 2〜3 個程度の指示まで**でした。
- 失敗の主な原因は、座標と道路番号の取り違え、範囲外の指定、要素の重複です。ツールのガイドを補っても改善しませんでした。
- 同じガイドだけを使う Claude Code の Skill は、レベル 4 をエラー 1 回で解きました。

詳しくは [Doc/evaluation.md](Doc/evaluation.md) を参照してください。

## fm コマンドから使う場合

macOS 27 の `fm` コマンド（`/usr/bin/fm`）には、任意のツールを登録するオプションがありません。`--tool` で指定できるのは組み込みの `barcode` と `ocr` だけです。
そこで [tinytown_fm.sh](tinytown_fm.sh) では、tinytowngen の引数を `fm respond --schema` に JSON で出力させ、スクリプトがその値からコマンドを組み立てて tinytowngen を実行します。tinytowngen がエラーを返したときは、`--resume` でエラー文をモデルに返して直させます（3 回まで）。

- 結果は SDK で Tool calling を使った場合と同じ傾向でした。座標を指定しない指示では 1 回目で成功しますが、レイアウトはガイドの例をほぼそのまま使っていました。座標や道路番号を指定しても守られず、重なりのエラーを返しても同じ誤りを 3 回繰り返しました。
- `fm respond --schema` に渡すスキーマには `x-order`（プロパティを生成する順番）が必要です。これがないと `The data couldn't be read because it is missing` というエラーになります。`enum` と `minimum`/`maximum` は使えます。
- `--resume` と `-i` は同時に指定できません。2 回目以降の呼び出しでは、最初の指示（instructions）は保存した会話から引き継がれます。
- 最初に `sudo fm license` で利用規約に同意する必要があります。

## 必要な環境

- Apple シリコン搭載の Mac、macOS 26 以降（macOS 27.0.1 で検証）、Apple Intelligence が有効
- Xcode 26 以降（検証は Xcode 27.1）。`xcode-select` で Xcode 本体を指定しておく
- Python 3.10 以降（検証は 3.14）

## クイックスタート

```bash
# Python SDK
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# tinytowngen をソースからビルドして venv に置く
git clone https://github.com/notoroid/tinytowngen.git
(cd tinytowngen && git checkout 1ecc60155382d931dd131c8c7481cfa21e1efc36 && swift build -c release)
cp tinytowngen/.build/release/tinytowngen .venv/bin/

source .venv/bin/activate
python hello_fm.py                                      # SDK の動作確認
python tinytown_tool.py "13x7 の平安京。中央に大路、左上に寺院"   # モデルに街を描かせる
python tinytown_eval.py                                 # 5 段階の評価（各 3 回）
./tinytown_fm.sh "13x7 の平安京。中央に大路、左上に寺院"   # fm コマンド版（要 jq、sudo fm license）
```

生成した画像と評価結果は `output/` に保存されます。セットアップの詳細とトラブルシューティングは [Doc/README.md](Doc/README.md) にあります。

## 構成

| パス | 内容 |
|---|---|
| [hello_fm.py](hello_fm.py) | SDK の動作確認（モデルが使えるかの確認、テキスト生成、Guided generation） |
| [tinytown_tool.py](tinytown_tool.py) | tinytowngen を `fm.Tool` として使うラッパーとデモ |
| [tinytown_eval.py](tinytown_eval.py) | 指示の複雑さ 5 段階の評価スクリプト |
| [tinytown_fm.sh](tinytown_fm.sh) | `fm` コマンドで引数を生成し、tinytowngen で描くシェルスクリプト |
| [.claude/skills/tinytown/](.claude/skills/tinytown/SKILL.md) | 同じガイドで動く Claude Code の Skill（`/tinytown <説明>`） |
| [Doc/README.md](Doc/README.md) | 環境構築の手順 |
| [Doc/evaluation.md](Doc/evaluation.md) | 評価の方法・結果・考察 |
| [Doc/private-cloud-compute.md](Doc/private-cloud-compute.md) | クラウドモデル（Private Cloud Compute）が使えるかの調査（今の環境では使えませんでした） |

## 注意

- `apple_fm_sdk` はベータ版のため、API が変わる可能性があります。
- モデルの出力は毎回変わるため、評価結果は実行ごとにばらつきます。
- このリポジトリは個人の検証記録で、Apple とは関係ありません。

## ライセンス

[MIT License](LICENSE)
