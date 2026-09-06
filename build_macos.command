#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script must run on macOS."
  exit 1
fi
PYTHON="${PYTHON:-python3.11}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Install Python 3.11 from python.org, then run this script again."
  exit 1
fi
"$PYTHON" -m venv .venv-macos
.venv-macos/bin/python -m pip install -r requirements.txt
.venv-macos/bin/python macos/prepare_assets.py
.venv-macos/bin/python -m unittest discover -s tests -p test_game.py -v
.venv-macos/bin/python -m unittest discover -s tests -p test_platform.py -v
.venv-macos/bin/python macos/build_macos.py
