# Robot Panel YOLO

[`apps/robot_control_monitor/`](../../apps/robot_control_monitor/README.md) と
[`tools/yolo_lab/`](../../tools/yolo_lab/README.md) が既定で使う
Ultralytics YOLO 形式の学習済み `best.pt` を同梱しています。
YOLO Lab の `damage-panel4-v1-nano` の最良チェックポイントをコピーしたものです。

既定のモデルパスは `weights/robot_panel/best.pt` です。
`ROBOT_PANEL_MODEL` で別のファイルを指定すると、そのパスが優先されます。
YOLO Lab の既定の学習設定もこのファイルから追加学習します。

クラスは `1`、`Damage-Panel3`、`Damage-Panel4` です。
出典・クラス定義・SHA-256 は [`model.json`](model.json) に記録しています。
学習データの注意点は [データセットの記録](../../tools/yolo_lab/DATASET-NOTES.md) を参照してください。
ライセンスは元環境に記録がなく未登録です。
