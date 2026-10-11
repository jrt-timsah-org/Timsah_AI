# Robot Panel YOLO

[`apps/robot_control_monitor/`](../../apps/robot_control_monitor/README.md) が使う
Ultralytics YOLO 形式の学習済みモデルを `best.pt` という名前でここに置きます。
モデルの実体は同梱していません。

既定のモデルパスは `weights/robot_panel/best.pt` です。
`ROBOT_PANEL_MODEL` で別のファイルを指定すると、そのパスが優先されます。
新しい既定パスにファイルがなければ、移行前の `../Panel_Yolo/best.pt` を参照します。

モデルの入手元・学習条件・クラス定義・ライセンスは未登録です。
モデルを配置したら、この README または `model.json` に情報を追記してください。
