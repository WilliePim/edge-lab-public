#!/usr/bin/env bash
# Connectivity check before committing to a full 20-40 min scan.
# One day, high threshold -> a handful of names, a couple of minutes.
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "usage: ./smoke.sh \"Your Name your@email.com\"" >&2
  exit 1
fi

# shellcheck disable=SC1091
. ./venv.sh

exec "$PY" -m form4_scanner.cli \
  --user-agent "$1" \
  --days 2 \
  --min-value 500000 \
  --all -v \
  --out out/smoke_test.csv
