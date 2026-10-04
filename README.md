# Robot Control Monitor

ロボコン用のダメージパネル検出・操作画面です。`../Panel_Yolo/best.pt` の学習済みYOLOモデルを使用し、カメラ映像上の検出パネルに左から順にIDを重ねて表示します。

## 起動

```bash
cd /Users/takaaki.h/Downloads/Robot_Control_Monitor

# 初回のみ: 仮想環境を作成してライブラリを入れる
/opt/homebrew/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 起動
.venv/bin/python app.py
```

Homebrew の Python 3.14 を使う場合は、Tk GUI を別途導入する必要があります。

```bash
brew install python-tk@3.14
```

`ModuleNotFoundError: No module named '_tkinter'` が出る場合は、上記コマンドを実行後にターミナルを開き直してください。アプリの実行には、システム Python ではなく `.venv/bin/python` を使います。

## 操作

- 右側の `CAMERA` から接続するカメラ番号を選択（通常は `0`）。
- `PANEL DETECTION` または `Space` でYOLO検出表示を切り替え。
- `STABILIZATION` で、映像内の特徴点を追跡する軽量な電子手ブレ補正を切り替え。
- USB接続した Nintendo Switch Proコントローラーで `L2/ZL`・`R2/ZR` を押すと、左から順に割り振られたターゲットIDを選択。`A` で選択対象に `[HIT!]` 演出を表示。
- 右下の `CONFIDENCE` スライダーで、YOLOの検出しきい値を10〜95%の範囲で調整。
- `ALLOW CLASS` の `BOTH`、`1 ONLY`、`PANEL 3` ボタンで許可クラスを即時切替。
- `MAX ASPECT` で縦横比フィルターを調整。`1.8:1` より横長・縦長の枠は除外されます。
- `LONG RANGE` は推論解像度を960pxへ上げ、遠方の小さなパネルを検出しやすくします（FPSは下がります）。
- `RECONNECT CAMERA` で再接続。
- `ESC` または `EMERGENCY STOP` で映像を停止。

## YOLOモデル

アプリは [Panel_Yolo](../Panel_Yolo/) フォルダにある `best.pt` を自動で読み込みます。移動した場合は、起動前に環境変数でモデル位置を指定できます。

```bash
ROBOT_PANEL_MODEL=/path/to/best.pt .venv/bin/python app.py
```

YOLO推論にはPyTorchを使用します。初回はモデル読込に少し時間がかかる場合があります。表示する枠の量と誤検出は `CONFIDENCE` を上げ下げして現場で調整してください。

## 距離推定

パネル正面の一辺を **145 mm** として、検出枠の大きさから距離を推定します。初回のみ、正面をカメラへ向けたパネルを既知距離（例: 1000 mm）に置き、次の操作で校正してください。

1. 左下の `PANEL SIZE` が `145`、`KNOWN RANGE` が実測距離（mm）になっていることを確認。
2. 該当するIDを選択。
3. `CALIBRATE SELECTED` をクリック。

以後、選択中のパネルまでの推定距離が左下と各検出枠に表示されます。カメラとパネルが正対しているほど正確です。傾き、検出枠の揺れ、または裏面の出っ張りは距離誤差になります。

手ブレ補正には Shi-Tomasi 特徴点と Lucas-Kanade オプティカルフローを使用します。ロボット本体の小さな振動や回転を抑える用途に向いていますが、露光中に生じた強いモーションブラーを復元する機能ではありません。

## Proコントローラーが検出されない場合

充電専用ではないUSB-CデータケーブルでMacへ直接接続し、コントローラーのUSB-C端子を抜き差ししてからアプリを起動してください。接続確認には次を実行します。

```bash
.venv/bin/python controller_diagnostics.py
```

`No controller detected` のままなら、アプリではなくmacOSがUSBゲームパッドとして認識していません。別のデータ対応ケーブルまたはUSBポートを試してください。
