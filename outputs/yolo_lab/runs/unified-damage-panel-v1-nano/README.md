# Unified Damage Panel v1 / YOLOv8n

2026-10-20に学習を開始し、2026-10-21に50エポックとテスト評価を完了しました。
学習設定は YOLOv8n の事前学習重み、512px、AMP、batch 65、seed 42、RTX 3060です。

- `weights/best.pt`: 検証結果が最良のチェックポイント。`weights/robot_panel/best.pt` と同一です。
- `weights/last.pt`: 最終エポックのチェックポイント。学習完了済みのため、追加学習では新しい実験の初期重みとして指定します。
- クラス番号0: `Damage-Panel`。
- 学習7,172枚、検証897枚、テスト909枚。同じ元画像の派生データを同じ分割にまとめました。

| テスト指標 | 値 |
| --- | ---: |
| Precision | 98.19% |
| Recall | 88.79% |
| mAP@50 | 92.79% |
| mAP@50–95 | 83.03% |

出典・SHA-256・評価の生値は [`weights/robot_panel/model.json`](../../../../weights/robot_panel/model.json) にあります。
データと画像、ログ、中間エポックの重みは含めません。検証分割はモデル選択、テスト分割は最終評価に使いました。
