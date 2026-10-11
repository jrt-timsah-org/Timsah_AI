# Controller Diagnostics

SDL / pygame から見えるUSBゲームパッドの名前、押されているボタン、軸の値を表示します。
Python 3.10 以上を用意し、以下をリポジトリ直下から実行してください。

```bash
python3 -m venv tools/controller_diagnostics/.venv
source tools/controller_diagnostics/.venv/bin/activate
# Windows (PowerShell): tools\controller_diagnostics\.venv\Scripts\Activate.ps1
python -m pip install -r tools/controller_diagnostics/requirements.txt
python tools/controller_diagnostics/main.py
```

終了は `Ctrl+C` です。`No controller detected` の場合は、データ通信対応ケーブルと
USBポートを確認してください。

Robot Control Monitor の仮想環境にも必要な依存があるので、その環境から実行することもできます。
リポジトリ直下の `python controller_diagnostics.py` は互換用の起動コマンドです。
