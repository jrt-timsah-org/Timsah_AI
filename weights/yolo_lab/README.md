# YOLO Lab の重み

YOLO Lab からコピーした事前学習重みです。

- `pretrained/yolov8n.pt`: YOLOv8n の事前学習モデル（明示的に選択する場合）。
- `extra/yolo26n.pt`: 元環境にあった追加モデル。

コピーした学習済み重みは `outputs/yolo_lab/runs/damage-panel4-v1-nano/weights/` にあります。
現在の既定モデルの最良・最終チェックポイントは
`outputs/yolo_lab/runs/unified-damage-panel-v1-nano/weights/` にあります。
これらの `.pt` は学習済みチェックポイントを含めて Git で共有しています。
追加のモデルは `pretrained/` に置き、
`--set model=<ファイル名>` で指定できます。
入手元・ライセンスの詳細は元環境の記録にないため未登録です。
既定では [`../robot_panel/best.pt`](../robot_panel/README.md) の学習済みモデルを使います。
使い方は [YOLO Lab](../../tools/yolo_lab/README.md) を参照してください。
