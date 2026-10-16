# クラウドモデル（Private Cloud Compute）の調査メモ

tinytown_tool.py をクラウドモデル版にするため、Foundation Models の **Private Cloud Compute（PCC）モデル**が使えるかを調べた記録です。

- 調査日: 2026-10-16
- 結論: **今の環境では使えません。** クラウドモデル版の tinytown_tool はまだ作っていません。

## PCC モデルの概要

WWDC26 セッション 319 と 241 で説明されている内容です。

| 項目 | 内容 |
|---|---|
| モデル | Apple Intelligence の多くの機能で使われているのと同じサーバー側のモデル |
| コンテキスト長 | 32K トークン。reasoning（`.light` / `.moderate` / `.deep`）に使ったトークンも、この上限に含まれる |
| 対象デバイス | Apple Intelligence に対応したデバイス。インターネット接続が必要 |
| 認証 | OS と iCloud に組み込まれているため、API キーは不要。使用量は利用者の iCloud アカウントで数えられる |
| 費用 | 開発者に料金はかからない |
| 利用量の上限 | 利用者ごとに 1 日あたりの上限がある（iCloud+ にすると上がる）。`quotaUsage` で状態を確認できる |
| 利用資格 | ダウンロード数が 200 万未満のアプリ。**Apple Developer サイトで申請が必要** |

Swift では、モデルの型を差し替えるだけで使えます。

```swift
import FoundationModels

let session = LanguageModelSession(
    model: PrivateCloudComputeLanguageModel(),
    tools: [/* Tool */]
)
let response = try await session.respond(to: "...")
```

## 調査結果

### 1. Python SDK が PCC モデルに対応していない

| 確認したもの | 結果 |
|---|---|
| PyPI の `apple_fm_sdk`（最新版 0.2.1） | `PrivateCloudComputeLanguageModel` に当たるクラスがない |
| GitHub の main ブランチ（調査時点の最新コミット `0249f35fce855a6701debaed569b6827fc6f5706`） | "cloud" や "PrivateCloud" に関するコードも記述もない |

指定できるのは、オンデバイスの `SystemLanguageModel` だけです（`use_case` と `guardrails` の 2 つの引数で調整します）。
そのため、**tinytown_tool.py のモデルだけを差し替えて PCC 版にすることはできません。**

### 2. Swift のコマンドラインプログラムから呼ぶと失敗する

確認用に、次の Swift プログラムを `swiftc` でビルドして実行しました（署名なし）。

```swift
import FoundationModels

let model = PrivateCloudComputeLanguageModel()
print("isAvailable:", model.isAvailable)
print("availability:", model.availability)
let session = LanguageModelSession(model: model)
let r = try await session.respond(to: "こんにちは。一文で自己紹介してください。")
```

結果:

```
isAvailable: true
availability: available
error: FoundationModels.LanguageModelError Code=-1
  └ ModelManagerServices.ModelManagerError Code=1046
```

- `isAvailable` は `true` を返しますが、実際に `respond()` を呼ぶと失敗します。
- `ModelManagerError 1046` が何を意味するかは、公開されている情報からは確認できていません。
- 署名も PCC の利用申請もしていないプログラムから呼んだことが原因である可能性が高い、と考えています（未検証）。

## 進め方の候補

| 候補 | 内容 | 前提 |
|---|---|---|
| A. Swift で作る（おすすめ） | tinytowngen を Tool として呼ぶ Swift 版を別に作る | Apple Developer サイトでの PCC 利用申請と、それに合わせた署名設定。申請後も動くかは試すまで分からない |
| B. Python SDK の対応を待つ | 対応したら、tinytown_tool.py のモデル指定を変えるだけで済む見込み | Apple の SDK 更新を待つ |
| C. Python 版を先に書いておく | モデルを切り替えられる形で書いておく | 今は実行すると失敗し、動作確認もできない |

## 今後確認すること

- [ ] PCC の利用申請を済ませる（Apple Developer サイト）
- [ ] 申請後、署名したプログラムで `ModelManagerError 1046` が出なくなるか確かめる
- [ ] `apple_fm_sdk` の新しいバージョンで PCC モデルに対応したか確認する（`pip index versions apple_fm_sdk`）
- [ ] `/usr/bin/fm` CLI（利用規約への同意が必要）から PCC モデルを指定できるか確かめる

## 参考

- [Build with the new Apple Foundation Model on Private Cloud Compute（WWDC26 セッション 319）](https://developer.apple.com/videos/play/wwdc2026/319/)
- [What's new in the Foundation Models framework（WWDC26 セッション 241）](https://developer.apple.com/videos/play/wwdc2026/241/)
- [apple/python-apple-fm-sdk](https://github.com/apple/python-apple-fm-sdk)
