#!/usr/bin/env bash
# The scan. Usage: ./run.sh "Your Name your@email.com" [extra cli flags...]
#
# 60 days, and the window is the one decision here that cannot be revisited.
# Transactions outside it are never collected, so the archive under state/ can
# always be rescored to a NARROWER window and never to a wider one, and days
# already past can never be recovered at all. The window in force is a permanent
# ceiling on every question the archive will ever be able to answer.
#
# It also decides what is SEEN, not merely what is kept: a Form 4 reaching the
# EDGAR index more than `days` after its transaction date is invisible to a run
# of that width, and no later run goes back for it.
#
# Cost, measured rather than assumed. The slow step is three years of Form 4
# history per distinct insider, cached per CIK, so the first run pays for all of
# them and consecutive runs share all but one day of the window. Measured at 30
# days: ~85 minutes cold, 6 minutes warm. 60 days roughly doubles the cold
# figure and leaves the warm one close to unchanged.
#
# The cap band is now the code default. This script carried --max-cap 2e9 while
# the library default was 10e9, and the disagreement silently decided which
# names could be emitted: 10 of the 41 signals emitted on 28 Aug sit above the
# lower ceiling, one of them at 8/12.
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "usage: ./run.sh \"Your Name your@email.com\" [--days N] [--all] ..." >&2
  echo "the SEC blocks requests without a real name+email User-Agent." >&2
  exit 1
fi

UA="$1"; shift

# shellcheck disable=SC1091
. ./venv.sh

# The window, the floor and the cap are NOT repeated here. They live once, in
# form4_scanner/scan.py, and this script inherits them. Restating them would
# recreate exactly the drift that made this change necessary: run.sh said 2e9
# while the library said 10e9, nothing kept the two in step, and the
# disagreement silently decided which names could be emitted.
#
# Override for a one-off by appending flags -- they land in "$@" after these.
exec "$PY" -m form4_scanner.cli \
  --user-agent "$UA" \
  --out "out/scan_$(date +%Y%m%d).csv" \
  "$@"
