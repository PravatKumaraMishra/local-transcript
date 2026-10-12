#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f .venv/bin/python ] || [ ! -f frontend/dist/index.html ]; then
  bash setup.sh
fi
.venv/bin/python launcher.py
