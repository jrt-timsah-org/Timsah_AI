# Robot Panel YOLO

[`apps/robot_control_monitor/`](../../apps/robot_control_monitor/README.md) と
[`tools/yolo_lab/`](../../tools/yolo_lab/README.md) が既定で使う
Ultralytics YOLO 形式の学習済み `best.pt` を同梱しています。
YOLO Lab の `unified-damage-panel-v1-nano` の最良チェックポイントをコピーしたものです。
2026-10-21に学習を完了しました。YOLOv8n の事前学習重みから512pxで50エポック学習しています。

既定のモデルパスは `weights/robot_panel/best.pt` です。
`ROBOT_PANEL_MODEL` で別のファイルを指定すると、そのパスが優先されます。
YOLO Lab の既定の学習設定もこのファイルから追加学習します。

クラス番号0は `Damage-Panel` です。
学習7,172枚、検証897枚、テスト909枚。同じ元画像の派生データと完全同一画像を同じ分割にまとめています。
テスト評価は Precision 98.19%、Recall 88.79%、mAP@50 92.79%、mAP@50–95 83.03% です。
以前の3クラスモデルとはデータとクラス定義が異なるため、数値を直接比較することはできません。
出典・クラス定義・SHA-256 は [`model.json`](model.json) に記録しています。
学習データの注意点は [データセットの記録](../../tools/yolo_lab/DATASET-NOTES.md) を参照してください。
ライセンスは未確認のため未登録です。
