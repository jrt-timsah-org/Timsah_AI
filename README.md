# Timsah AI Workspace

AIアプリ、学習・推論の補助ツール、モデルの重みをまとめて置くためのワークスペースです。
アプリごとに依存関係を分け、データと生成物はローカルで管理します。
既定の `best.pt` と YOLO Lab の事前学習重み・チェックポイントは Git に含めています。

## ディレクトリ構成

```text
Timsah_AI/
├── apps/                      # AIを使うアプリ・実験プロジェクト
│   └── robot_control_monitor/ # YOLOによるロボット操縦支援モニター
├── tools/                     # 診断・前処理・変換などの補助ツール
│   ├── controller_diagnostics/
│   └── yolo_lab/              # YOLOデータ登録・学習・評価・エクスポート
├── weights/                   # モデルの重み（既定の best.pt と YOLO Lab の .pt は Git 管理）
│   └── robot_panel/best.pt    # モニターとYOLO Labが既定で使う学習済み重み
├── datasets/                  # 学習・評価データ（実体は Git 管理外）
├── outputs/                   # 生成物（YOLO Lab の重み以外は Git 管理外）
├── notebooks/                 # ノートブック
├── docs/                      # 追加・管理の手順
├── app.py                     # 既存モニターの互換ランチャー
├── controller_diagnostics.py  # 既存診断ツールの互換ランチャー
└── requirements.txt           # 既存モニターの互換依存定義
```

## 使えるアプリ・ツール

| 名前 | 用途 | 手順 |
| --- | --- | --- |
| Robot Control Monitor | YOLOによるパネル検出、距離推定、操縦支援 | [アプリの README](apps/robot_control_monitor/README.md) |
| Controller Diagnostics | USBゲームパッドの認識と入力を確認 | [ツールの README](tools/controller_diagnostics/README.md) |
| YOLO Lab | YOLOデータ登録・学習・評価・推論・モデル変換 | [ツールの README](tools/yolo_lab/README.md) |

## モニターを起動する

Python 3.10 以上と Tk、カメラ、学習済みの Ultralytics YOLO モデルが必要です。
以下はリポジトリ直下から実行します。

```bash
python3 -m venv apps/robot_control_monitor/.venv
source apps/robot_control_monitor/.venv/bin/activate
# Windows (PowerShell): apps\robot_control_monitor\.venv\Scripts\Activate.ps1
python -m pip install -r apps/robot_control_monitor/requirements.txt
```

同梱の学習済み `weights/robot_panel/best.pt` を使って起動します。モデルの追加配置は不要です。
現在のモデルは `unified-damage-panel-v1-nano`（`Damage-Panel` 1クラス）です。
学習条件・テスト評価・出典は [モデルの記録](weights/robot_panel/README.md) を参照してください。

```bash
python apps/robot_control_monitor/app.py
```

別のモデルは環境変数で指定できます。

```bash
ROBOT_PANEL_MODEL=/path/to/best.pt python apps/robot_control_monitor/app.py
```

環境変数を指定しなければ、同梱の `weights/robot_panel/best.pt` を読み込みます。
YOLO Lab の既定の学習設定もこのモデルから追加学習します。
詳しくは [YOLO Lab の README](tools/yolo_lab/README.md) を参照してください。

従来の `pip install -r requirements.txt`、`python app.py`、
`python controller_diagnostics.py` も引き続き使えます。

## ツールや重みを追加する

- 新しいアプリは `apps/<名前>/`、補助ツールは `tools/<名前>/` に置きます。
- Python の依存定義と仮想環境は各プロジェクト内に置きます。全ツールの依存を一括インストールする必要はありません。
- 重みは `weights/<モデル名>/<バージョン>/`、データは `datasets/<名前>/`、生成物は `outputs/<ツール名>/` にまとめます。
- 重みは既定では Git 管理外ですが、`weights/robot_panel/best.pt` と YOLO Lab の `.pt` は明示的な例外として共有しています。
- 外部サービスの認証情報は Git に入れず、環境変数や各ツールの `.env` で渡します。

具体例は [ツール追加手順](docs/adding-tools.md) と [重みの管理方法](weights/README.md) を参照してください。
