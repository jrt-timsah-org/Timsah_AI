#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${1:-damage-panel4-v1-nano}"
LOG="$("$ROOT/.venv/bin/python" - "$ROOT" "$NAME" <<'PY'
import json, re, sys
from pathlib import Path
root, name = Path(sys.argv[1]), sys.argv[2]
if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', name):
    raise SystemExit('Invalid run name')
print(json.loads((root.parents[1] / 'outputs' / 'yolo_lab' / 'logs' / f'{name}.json').read_text())['log'])
PY
)"
printf 'YOLO 学習ログ: %s\n' "$NAME"
printf 'ログ: %s\n' "$LOG"
printf 'Ctrl+C またはウィンドウを閉じると表示だけ終了します。学習は続きます。\n\n'
printf 'Epoch   GPU_mem   box_loss   cls_loss   dfl_loss   Instances   Size\n'
exec tail -c 1800 -F "$LOG"
