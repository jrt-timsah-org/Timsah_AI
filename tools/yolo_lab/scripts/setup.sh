#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo 'uv is required: https://docs.astral.sh/uv/'; exit 1; }
export UV_HTTP_TIMEOUT=600
export UV_CONCURRENT_DOWNLOADS=2
uv venv .venv --python python3 --allow-existing
if [[ -f requirements.lock ]]; then
  uv pip sync --python .venv/bin/python requirements.lock --extra-index-url https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match
else
  uv pip install --python .venv/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu126
  uv pip install --python .venv/bin/python -r requirements.in
  uv pip freeze --python .venv/bin/python > requirements.lock
fi
./yolo-lab doctor
