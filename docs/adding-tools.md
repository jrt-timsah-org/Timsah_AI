# ツール追加手順

アプリは `apps/<名前>/`、補助ツールは `tools/<名前>/` に置きます。
名前は小文字の英数字とアンダースコアに統一すると扱いやすくなります。

## Python プロジェクトの例

```text
apps/my_ai_tool/
├── README.md          # 用途、必要環境、セットアップ、起動方法、モデル指定方法
├── requirements.txt   # このツールだけの依存関係
├── main.py            # 起動用スクリプト
└── .venv/             # ローカル環境（Git 管理外）
```

リポジトリ直下から、ツール専用の仮想環境を作ります。

```bash
python3 -m venv apps/my_ai_tool/.venv
source apps/my_ai_tool/.venv/bin/activate
# Windows (PowerShell): apps\my_ai_tool\.venv\Scripts\Activate.ps1
python -m pip install -r apps/my_ai_tool/requirements.txt
python apps/my_ai_tool/main.py
```

`pyproject.toml`、uv、Conda、Node.js などを使うプロジェクトも、各ディレクトリ内で
依存関係を管理し、その README に手順を書いてください。ルートの `requirements.txt` は
既存モニターとの互換用なので、新しいツールの依存は追加しません。
別のツールを使うときは、仮想環境を切り替えてください。

## 入出力の配置

| 内容 | 配置例 | Git 管理 |
| --- | --- | --- |
| ツールのコードと設定例 | `apps/my_ai_tool/` または `tools/my_ai_tool/` | 対象 |
| モデルの重み | `weights/my_model/v1/` | 対象外 |
| モデルの説明と入手情報 | `weights/my_model/v1/README.md`、`model.json` | 対象 |
| 学習・評価データ | `datasets/my_dataset/` | 対象外 |
| 推論結果・学習チェックポイント | `outputs/my_ai_tool/` | 対象外 |
| ノートブック | `notebooks/` | 対象 |

YOLO Lab の事前学習重みと `outputs/yolo_lab/runs/**/weights/*.pt` は例外として
Git 管理しています。他の重みを共有する場合も、該当パスの例外を `.gitignore` に追加します。

小さなテスト用データを共有したい場合は、各プロジェクトの `tests/fixtures/` に置きます。
ノートブックは保存前に大きな出力や認証情報を消してください。
空のディレクトリを Git に残す場合は `.gitkeep` を置きます。

## モデルパス

重みの指定は環境変数やコマンドライン引数に対応させ、既定値は
起動したディレクトリに依存しないパスにします。上記の `main.py` なら次のように書けます。

```python
import os
from pathlib import Path

REPOSITORY_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.environ.get(
    "MY_AI_MODEL",
    str(REPOSITORY_DIR / "weights" / "my_model" / "v1" / "model.safetensors"),
)).expanduser()
```

ファイルがない場合は必要なパスと準備手順を表示するようにし、入手元・ライセンス・
対応ツールは [重みの管理方法](../weights/README.md) に沿って記録します。
大きなダウンロードを起動時に自動実行する場合は、その挙動も README に記載してください。

最後に [アプリ一覧](../apps/README.md) または [ツール一覧](../tools/README.md) と
[ルートの一覧](../README.md) に用途と README へのリンクを追加します。
