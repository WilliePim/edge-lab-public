#!/usr/bin/env bash
# One-shot setup. Creates the venv, installs deps, runs the offline test suite.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> creating virtualenv"
python3 -m venv .venv 2>/dev/null || python -m venv .venv

# Resolves the interpreter binary rather than sourcing activate -- see venv.sh
# for why that distinction matters on Windows.
# shellcheck disable=SC1091
. ./venv.sh

echo "==> installing dependencies"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r requirements.txt

# Pre-commit guard (.githooks/guard.py): no market data, big files or API keys in commits.
[ -d .githooks ] && git config core.hooksPath .githooks

echo "==> running offline test suite"
./test.sh

cat <<'MSG'

Setup complete.

Next:
  1. source .venv/bin/activate   (Windows: source .venv/Scripts/activate)
  2. ./smoke.sh "Your Name your@email.com"   -- 2 minutes, checks SEC connectivity
  3. ./run.sh   "Your Name your@email.com"

MSG
