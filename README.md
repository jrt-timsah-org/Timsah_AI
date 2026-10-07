# Robot Control Monitor

カメラ映像からパネルをYOLOで検出し、左から順にIDを重ねて表示する、ロボット操縦支援用のモニターアプリです。検出結果の選択・ヒット演出・距離推定・電子手ブレ補正に対応しています。

## 特長

- YOLOによるパネル検出（左から順にIDを自動割り当て）
- Nintendo Switch Proコントローラーによるターゲット選択
- パネルの既知サイズを使った距離推定
- 特徴点追跡による軽量な電子手ブレ補正
- 信頼度しきい値・許可クラス・縦横比フィルターをGUIから調整可能

## 必要環境

- Python 3.10 以上（Tk 対応のもの）
- Webカメラ等のUVC対応カメラ
- 学習済みYOLOモデル（Ultralytics 形式の `.pt`）
- （任意）USB接続の Nintendo Switch Pro コントローラー

## セットアップ

```bash
git clone https://github.com/jrt-timsah-org/Timsah_AI.git
cd Robot_Control_Monitor

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Tk が見つからない場合

`ModuleNotFoundError: No module named '_tkinter'` が出る場合は、お使いの Python に対応した Tk を導入してください。

- macOS (Homebrew): `brew install python-tk@<Pythonのバージョン>`（例: `python-tk@3.12`）
- Debian / Ubuntu: `sudo apt install python3-tk`

導入後はターミナルを開き直し、仮想環境の Python で実行してください。

## モデルの準備

学習済みモデル（`best.pt`）は本リポジトリに含まれていません。次のいずれかで指定してください。

1. 既定の場所 `../Panel_Yolo/best.pt` に置く
2. 環境変数 `ROBOT_PANEL_MODEL` でパスを指定する

```bash
ROBOT_PANEL_MODEL=/path/to/best.pt python app.py
```

推論には PyTorch を使用します。初回はモデルの読み込みに時間がかかる場合があります。

## 起動

```bash
python app.py
```

## 操作

| 操作 | 内容 |
| --- | --- |
| `CAMERA` | 接続するカメラ番号を選択（通常は `0`） |
| `PANEL DETECTION` / `Space` | YOLO検出表示の切り替え |
| `STABILIZATION` | 電子手ブレ補正の切り替え |
| `L2/ZL`・`R2/ZR` | 左から順にターゲットIDを選択（Proコントローラー） |
| `A` | 選択中のターゲットに `[HIT!]` 演出を表示 |
| `CONFIDENCE` | 検出しきい値を 10〜95% で調整 |
| `ALLOW CLASS` | 許可クラスを切り替え（`BOTH` / `1 ONLY` / `PANEL 3`） |
| `MAX ASPECT` | 縦横比フィルター。`1.8:1` より横長・縦長の枠を除外 |
| `LONG RANGE` | 推論解像度を 960px に上げ、遠方の小さなパネルを検出しやすくする（FPSは低下） |
| `RECONNECT CAMERA` | カメラを再接続 |
| `ESC` / `EMERGENCY STOP` | 映像を停止 |

誤検出や検出数は、環境に合わせて `CONFIDENCE` を調整してください。

## 距離推定

パネル正面の一辺（既定 **145 mm**）と検出枠の大きさから距離を推定します。初回のみ校正が必要です。

1. パネルの正面をカメラへ向け、既知の距離（例: 1000 mm）に置く
2. 左下の `PANEL SIZE`（既定 `145`）と `KNOWN RANGE`（実測距離, mm）を確認
3. 対象のIDを選択
4. `CALIBRATE SELECTED` をクリック

以後、選択中のパネルまでの推定距離が左下と各検出枠に表示されます。

> **注意**: カメラとパネルが正対しているほど正確です。パネルの傾き、検出枠の揺れ、裏面の出っ張りは誤差の原因になります。実際のパネルサイズに合わせて `PANEL SIZE` を変更してください。

## 手ブレ補正

Shi-Tomasi 特徴点と Lucas-Kanade オプティカルフローによる電子補正です。ロボット本体の小さな振動や回転を抑える用途向けで、露光中に生じた強いモーションブラーを復元する機能ではありません。

## Proコントローラーが検出されない場合

1. データ通信対応の USB-C ケーブルで PC に直接接続する（充電専用ケーブルは不可）
2. コントローラー側の USB-C 端子を抜き差しする
3. 次を実行して認識状況を確認する

```bash
python controller_diagnostics.py
```

`No controller detected` のままの場合、アプリではなく OS が USB ゲームパッドとして認識していません。別のデータ対応ケーブルまたは USB ポートを試してください。

## ライセンス

<!-- ライセンスを記載（例: MIT） -->
