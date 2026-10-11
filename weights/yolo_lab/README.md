# YOLO Lab の重み

`/mnt/hdd/LLM-Experiments/yolo-lab` からコピーした事前学習重みです。

- `pretrained/yolov8n.pt`: YOLO Lab の既定の初期モデル。
- `extra/yolo26n.pt`: 元環境にあった追加モデル。

コピーした学習済み重みは `outputs/yolo_lab/runs/damage-panel4-v1-nano/weights/` にあります。
これらの `.pt` は学習済みチェックポイントを含めて Git で共有しています。
追加のモデルは `pretrained/` に置き、
`--set model=<ファイル名>` で指定できます。
入手元・ライセンスの詳細は元環境の記録にないため未登録です。
使い方は [YOLO Lab](../../tools/yolo_lab/README.md) を参照してください。
