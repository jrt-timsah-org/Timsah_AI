# YOLO Lab

RTX 3060 12GB / Ryzen 5 5600G / Python 3.12 向けの、データセットを切り替えられるYOLO物体検出学習環境です。既存のシステムPythonや他のアプリの仮想環境は変更しません。

## 最初の準備

このコピーではコードを `tools/yolo_lab/` に置き、保存先を次のように統合しています。
以下のコマンドは、特に指定がなければ `tools/yolo_lab/` から実行してください。

| 内容 | リポジトリ直下からのパス |
| --- | --- |
| 登録データ | `datasets/yolo_lab/` |
| 既定の学習済み重み | `weights/robot_panel/best.pt` |
| 事前学習重み | `weights/yolo_lab/pretrained/` |
| 追加の重み | `weights/yolo_lab/extra/` |
| 実験結果・チェックポイント | `outputs/yolo_lab/runs/` |
| 実行ログ | `outputs/yolo_lab/logs/` |

コピー元の YOLO Lab は変更していません。既存の学習結果と重みを
コピーしていますが、プロセスは引き継ぎません。コピーした実験の `status` は記録を表示し、
`stop` は元の実行には作用しません。新しい学習には別の実験名を使ってください。
既存チェックポイントには元の学習環境の設定が含まれるため、再学習の初期重みとして
`--set model=/absolute/path/best.pt` を使えます。

`damage-panel4-v1` は元と同じSSD上のデータセットへのシンボリックリンクです。
データセットへの変更は元環境にも共有されます。仮想環境・キャッシュ・Ultralyticsの
ローカル設定はコピーせず、この場所で専用の仮想環境を作成します。

モニターも同梱の `weights/robot_panel/best.pt` を既定で使います。
リポジトリ直下から起動してください。

```bash
python app.py
```

モニターの依存関係は別途セットアップしてください。

既定の `best.pt`、事前学習重み、`runs/**/weights/*.pt` のチェックポイントは Git に含めています。
実験の図・メトリクス・ログ、データセットへのリンクはローカルのみです。
新しくcloneした環境では、データセットを登録して新しい実験名で学習してください。
推論・エクスポートには、cloneしたチェックポイントをそのまま指定できます。

```bash
cd tools/yolo_lab  # Timsah_AI のリポジトリ直下から
./scripts/setup.sh
./yolo-lab doctor
```

CUDA 12.6対応PyTorchを専用 `.venv` にインストールします。ホストのNVIDIAドライバを使用するため、CUDA Toolkitの別途インストールは不要です。導入後の実際のパッケージバージョンは `requirements.lock` に固定します。CUDAホイールと通常のPyPIの両方を使って復元します。

## データセットを登録・切り替え

```bash
./yolo-lab import /path/to/dataset.zip \
  --name my-panel-v1 --storage "$HOME/.cache/yolo-lab/datasets"

# 次のZIPを、別の名前で追加します。既存のデータは上書きしません。
./yolo-lab import /absolute/path/new-dataset.zip --name next-v1 \
  --storage "$HOME/.cache/yolo-lab/datasets"
./yolo-lab start --data next-v1 --name next-v1-nano
```

コピーした `damage-panel4-v1` は登録済みなので、再インポートは不要です。

`train/images`, `train/labels`, `valid/images` (または `val/images`), `valid/labels`, `data.yaml` を含むYOLO形式に対応します。`test` は任意です。ZIP内に一段上の共通フォルダがあっても登録できます。今回は物体検出を学習します。ポリゴンラベルが含まれる場合は、それを囲む矩形へ変換し、元のラベルを `labels.source/`、変換数を `label-conversion.json` に保存します。矩形とポリゴンの混在にも対応します。分類・キーポイント用ラベルは対象外です。

`--storage` を指定すると画像と画像キャッシュをSSD側に置き、`../../datasets/yolo_lab/<name>` からリンクします。指定しなければ、リポジトリの `datasets/yolo_lab/`（HDD側）に保存します。ディスクキャッシュは圧縮JPEGより大きくなります。このデータセットは512×512の画像35,909枚を含むため、学習画像キャッシュだけで約28GB必要です。RAM全体へはキャッシュしません。

インポート時に画像、ラベルのクラス番号・座標、画像との対応を検査します。同一画像や `.rf.` より前のファイル名の一致による分割間の重複も警告します。これらはファイル名に基づく手掛かりであり、分割の独立性を保証する検査ではありません。クラス名やデータの分割は自動で変更しません。

- `data.yaml`: 実際の保存先に合わせて修正した学習用定義
- `data.source.yaml`: 元の定義
- `manifest.json`: ZIPのSHA256と登録元
- `audit.json`: 画像数、クラス別ボックス数、重複・欠落の検査結果

## 学習

```bash
./yolo-lab start --data damage-panel4-v1 --name damage-panel4-v2-nano
./yolo-lab status damage-panel4-v2-nano

# コピーした既存の結果を確認
./yolo-lab status damage-panel4-v1-nano

# フォアグラウンドで実行する場合
./yolo-lab train --data damage-panel4-v1 --name trial --set epochs=10

# より大きいモデルや画像サイズに変更する場合
./yolo-lab start --data damage-panel4-v1 --name small-640 \
  --set model=yolov8s.pt --set imgsz=640 --set batch=0.65
```

既定値は `configs/default.yaml` で管理します。同梱の学習済み `weights/robot_panel/best.pt` から追加学習し、512px、最大50エポック、改善が10エポック止まったら早期終了します。AMP、自動バッチサイズ（GPUメモリ70%目標）、6ワーカー、SSDディスクキャッシュを使用します。全学習画像を使います。`deterministic: false` は速度を優先する設定で、同じseedでも厳密に同じ結果を保証しません。

`model` のディレクトリ付き相対パスはリポジトリ直下を基準に解決します。
`yolov8n.pt` のようなファイル名だけなら `weights/yolo_lab/pretrained/` を参照します。

`start` は端末やチャットと独立したプロセスで実行します。PCの電源オフ・スリープ・再起動中は学習できません。プロセス状態は `status`、詳細ログは `../../outputs/yolo_lab/logs/` で確認します。途中経過はエポック完了時に更新され、完了後は最良モデルをテスト分割で評価し、`test-metrics.json` に保存します。検証分割はモデル選択、テスト分割は最終評価に使います。

```bash
tail -f ../../outputs/yolo_lab/logs/damage-panel4-v1-nano-*.log

# 最新のログをリアルタイム表示（表示を閉じても学習は継続）
./scripts/watch-training.sh damage-panel4-v1-nano

# 任意: 別端末からTensorBoardをローカル表示
.venv/bin/tensorboard --logdir ../../outputs/yolo_lab/runs --host 127.0.0.1 --port 6006
```

学習中はGPUとCPUを使用します。別のGPUアプリと併用してメモリ不足になったら、次の実行を `--set batch=16` や `--set workers=4` で調整できます。メモリ使用率70%は目標であり上限保証ではありません。

## 停止・再開

```bash
./yolo-lab stop damage-panel4-v1-nano
./yolo-lab start --data damage-panel4-v1 --name damage-panel4-v1-nano \
  --resume ../../outputs/yolo_lab/runs/damage-panel4-v1-nano/weights/last.pt
```

停止時点の未完了エポックは保存されません。再開は最後の完了エポックの `last.pt` から行い、元の学習設定・optimizer状態を復元します。最初のエポックが完了する前には再開用の重みがありません。停止後に `status` でプロセス終了を確認してから再開してください。完了した学習の `last.pt` は再開用ではなく、新しい実験の `--set model=/absolute/path/last.pt` に使います。

## 成果物・推論・エクスポート

- `../../outputs/yolo_lab/runs/<name>/weights/best.pt`: 検証結果が最良のモデル
- `../../outputs/yolo_lab/runs/<name>/weights/last.pt`: 再開用の最新モデル
- `../../outputs/yolo_lab/runs/<name>/results.csv`: エポックごとの損失・精度
- `../../outputs/yolo_lab/runs/<name>/test/`: 最終テスト評価と図
- `../../outputs/yolo_lab/runs/<name>/status.json`: 進捗、失敗時のエラー
- `../../outputs/yolo_lab/runs/latest.json`: 正常に完了した最新実験のモデルの場所

```bash
./yolo-lab predict --weights ../../outputs/yolo_lab/runs/damage-panel4-v1-nano/weights/best.pt \
  --source /absolute/path/image-or-directory --conf 0.25
./yolo-lab export --weights ../../outputs/yolo_lab/runs/damage-panel4-v1-nano/weights/best.pt --format onnx
```

ONNXなど一部の形式はエクスポート時に追加依存関係が必要になります。Ultralytics自身のエクスポーターが案内・導入します。

公式資料: [学習設定と再開](https://docs.ultralytics.com/modes/train/)、[PyTorch CUDAインストール](https://pytorch.org/get-started/locally/)。
