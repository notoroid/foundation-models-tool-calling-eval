# FMPayground 環境構築メモ

macOS 27 のオンデバイス基盤モデル（Foundation Models）を、Python から使うための環境です。
使っているのは **Foundation Models SDK for Python**（`apple_fm_sdk`）です。
さらに、街の画像を生成する CLI **tinytowngen** を、モデルが呼び出せる Tool として組み込んでいます。

- 参考: [WWDC26 セッション 334](https://developer.apple.com/jp/videos/play/wwdc2026/334)
- SDK: [apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk)（ドキュメント: https://apple.github.io/python-apple-fm-sdk/ ）
- tinytowngen: [notoroid/tinytowngen](https://github.com/notoroid/tinytowngen)

## 動作確認した環境（2026-10-14）

| 項目 | バージョン |
|---|---|
| macOS | 27.0.1（Apple シリコン、Apple Intelligence 有効） |
| Xcode | 27.1（`/Applications/Xcode27.1.app`）、Swift 6.4 |
| Python | 3.14.7（python.org 版） |
| apple_fm_sdk | 0.2.1（ベータ版、PyPI からインストール） |
| tinytowngen | commit `1ecc60155382d931dd131c8c7481cfa21e1efc36`（2026-10-12、main） |

SDK の要件は、macOS 26.0 以降、Xcode 26.0 以降、Python 3.10 以降、Apple Intelligence が有効になっていること、の 4 点です。

## フォルダ構成

```
FMPayground/
├── .venv/               Python 仮想環境（apple_fm_sdk と tinytowngen バイナリ入り）
├── requirements.txt     apple_fm_sdk==0.2.1
├── hello_fm.py          SDK の動作確認サンプル
├── tinytown_tool.py     tinytowngen を fm.Tool として使うラッパー＋デモ
├── tinytown_eval.py     tinytown_tool の評価スクリプト（指示の複雑さ 5 レベル）
├── output/              tinytown_tool.py が生成する PNG の出力先（評価結果は output/eval/）
├── tinytowngen/         tinytowngen のソース（git clone）
├── .claude/skills/tinytown/  tinytown_tool.py と同じガイドで動く Claude Code の Skill（/tinytown <説明>）
└── Doc/                 このドキュメント
```

## 1. Python SDK のセットアップ

### 前提: Xcode を開発者ディレクトリにする

`apple_fm_sdk` はインストール時に Swift のコードをビルドします。そのため Command Line Tools だけでは足りず、**Xcode 本体**が必要です。
`xcode-select` が Command Line Tools を向いていると、インストール時に次のエラーが出ます。

```
SwiftToolingError: The active developer directory is set to Command Line Tools ..., but a full Xcode installation is required.
```

Xcode に切り替えてください（一度だけ、sudo が必要です）。

```bash
sudo xcode-select -s /Applications/Xcode27.1.app/Contents/Developer
xcode-select -p   # → /Applications/Xcode27.1.app/Contents/Developer
```

Xcode のライセンスにまだ同意していない場合は、Xcode を一度起動して同意しておきます。

### インストール

```bash
cd FMPayground
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

### 動作確認

```bash
source .venv/bin/activate
python hello_fm.py
```

次のような出力が出れば成功です。

```
こんにちは。私はAppleが開発した基盤モデルです。
['curry powder', 'coconut milk', 'potatoes']
```

`hello_fm.py` では、次の 3 つを試しています。

- `SystemLanguageModel().is_available()` で、モデルが使えるかを確認する
- `LanguageModelSession(instructions=...)` を作り、`respond()` で文章を生成する
- `@fm.generable` と `fm.guide` で構造化出力の型を定義し、`respond(..., generating=型)` で受け取る（Guided generation）

## 2. tinytowngen のビルド

```bash
git clone https://github.com/notoroid/tinytowngen.git
cd tinytowngen
git checkout 1ecc60155382d931dd131c8c7481cfa21e1efc36   # 検証時と同じ版にそろえる場合
swift build -c release
swift test                                   # 96 tests が通ることを確認
cp .build/release/tinytowngen ../.venv/bin/  # venv の PATH に置く
```

ソースを更新して再ビルドしたときは、`cp` をもう一度実行してください。

単体での使用例:

```bash
source .venv/bin/activate
tinytowngen -m heiankyo11c -o heian.png --scale 2 -l "U3{0,0} U2{9,4} F{3} W{5} B{7,1} C*"
tinytowngen --help   # レイアウト文法の詳細
```

## 3. tinytowngen を fm の Tool として使う

`tinytown_tool.py` では、`TinyTownTool`（`fm.Tool` のサブクラス）を定義しています。
モデルは、ユーザーの依頼をもとに次の引数を決めて `render_town` ツールを呼び出します。

| 引数 | 型 | 内容 |
|---|---|---|
| `layout` | str | tinytowngen の配置文字列（例: `U3{0,0} F{3} W{5} C*`） |
| `grid` | str | グリッドサイズ `WxH`（例: `13x7`） |
| `map` | str | `sapporo`（現代都市）/ `heiankyo11c`（平安京）。`anyOf` でこの 2 つに制限 |
| `seed` | int | バリエーション用シード（1〜999） |
| `filename` | str | 出力ファイル名（`.png`） |

### 実行

```bash
source .venv/bin/activate
python tinytown_tool.py                                   # 既定: 13x7 の平安京、中央に大路、左上に寺院
python tinytown_tool.py "現代的な 10x6 の街。右下に公園、縦に水路を1本"
```

生成された画像は `output/` に保存されます。

### 自分のコードから使う

```python
import apple_fm_sdk as fm
from tinytown_tool import TinyTownTool

session = fm.LanguageModelSession(
    instructions="You design small grid cities and draw them with the render_town tool.",
    tools=[TinyTownTool(scale=2)],
)
print(await session.respond("海沿いの小さな港町を描いて"))
```

### 実装上のポイント

- **レイアウト文法をツールの説明に入れる**: モデルが正しい配置文字列を書けるよう、`description` に文法の要約と例を入れています（`LAYOUT_GUIDE`）。
- **エラーをモデルに返す**: tinytowngen が失敗（終了コード 1 または 2）したときは、例外を投げずに stderr の内容を文字列で返しています。モデルはそれを見て、レイアウトを直して呼び直せます。
- **出力先を制限する**: モデルが決めたファイル名からはベース名だけを取り出し、`output/` の中にだけ書き込むようにしています。
- **シェルを通さずに実行する**: `asyncio.create_subprocess_exec` に引数をリストで渡しているので、配置文字列に含まれる `{}` や `*` がシェルに解釈されることはありません。

### モデルの能力の目安

オンデバイスモデルが安定して扱えるのは、座標を指定しない、要素 2〜3 個程度の指示までです。座標の指定や、交差を避ける配置が必要になると失敗しやすくなります。評価の方法と結果は [evaluation.md](evaluation.md) にまとめています。

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| `pip install` で `SwiftToolingError ... Command Line Tools` | `xcode-select` が Command Line Tools を向いている。手順 1 の `sudo xcode-select -s` を実行する |
| `GenerationError (status: 255): None` | apple_fm_sdk 0.2.1 では、`fm.guide(regex=...)` を使うとこのエラーになる。`regex` は使わず、値のチェックは Tool 側か CLI 側で行う（`anyOf` と `range` は問題なく動く） |
| `Foundation Model is not available: ...` | Apple Intelligence が無効、またはモデルのダウンロードが終わっていない。システム設定を確認する |
| `tinytowngen が PATH に見つかりません` | venv を有効にしていない、またはバイナリを `.venv/bin/` にコピーしていない |
| `fm --help` で利用規約の同意を求められる | `/usr/bin/fm`（macOS 27 に最初から入っている CLI）は、規約への同意が必要（`sudo fm license`、マシン全体に適用される）。Python SDK だけを使う場合は不要 |

## 補足

- SDK はベータ版なので、API が変わる可能性があります。
- `/usr/bin/fm` CLI は、この環境ではまだ使える状態にしていません（規約に同意していないため）。tinytowngen の連携は Python SDK の Tool 経由で実装しています。
- 使っているのはオンデバイスモデルだけです。クラウドモデル（Private Cloud Compute）は今の環境では使えませんでした。調査の結果と今後の進め方は [private-cloud-compute.md](private-cloud-compute.md) にまとめています。
