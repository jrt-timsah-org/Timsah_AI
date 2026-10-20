# YOLO Lab の実験結果

`runs/` と `logs/` に元の YOLO Lab の結果をコピーしています。
パス情報を新しい配置に更新し、PIDは `original_pid` として記録したうえで
現在のPIDを未設定にしています。コピー元のプロセスを操作するための情報ではありません。
元のログ本文とチェックポイント内の学習設定は、そのまま残しています。
新しい実験の結果もここへ保存します。

現在の既定モデルの学習結果は [`runs/unified-damage-panel-v1-nano/README.md`](runs/unified-damage-panel-v1-nano/README.md) を参照してください。
この実験は最良・最終チェックポイントを共有し、中間エポックの重みは含めません。

`runs/**/weights/*.pt` は Git で共有します。それ以外の実験結果・ログはローカル管理です。
