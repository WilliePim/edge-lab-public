#!/usr/bin/env bash
# The daily entrypoint. This is the command a scheduler runs.
#
#     ./daily.sh "Your Name your@email.com"
#     ./daily.sh "Your Name your@email.com" --days 7        # override anything
#
# WHAT THIS FILE USED TO BE. It also exported signals to an external queue
# (emit.py). It no longer does, and nothing in this repo depends on an external
# repo.
#
# WHY IT IS NOT THAT ANY MORE. emit.py keyed its dedup on the score
# (emit.py:140, `dedup: str(card.score)`) and gated emission on PASS_MARK. The
# v3 prune removed the rubric, so there is no score to key on and no threshold
# to gate on. Re-emitting on score_v3 would mean inventing a threshold before
# anything has been measured against one, which is the mistake the whole prune
# was for. There is no export until M1 and M2 give v3 a measured cut.
#
# What remains: the scan, and the append-only archive under this repo's state/,
# which needs nothing external.
set -uo pipefail
cd "$(dirname "$0")"

if [ $# -lt 1 ]; then
  echo "usage: ./daily.sh \"Your Name your@email.com\" [extra cli flags...]" >&2
  echo "the SEC blocks requests without a real name+email User-Agent." >&2
  exit 2
fi
UA="$1"; shift

# shellcheck disable=SC1091
. ./venv.sh

"$PY" -m form4_scanner.cli \
  --user-agent "$UA" \
  --out "out/scan_$(date +%Y%m%d).csv" \
  "$@"
status=$?

# DIRE CHE IL REPORT ESISTE. Il giro scrive reports/daily_YYYY-MM-DD.md e chi
# lo ha lanciato cattura lo stdout, quindi fino a ieri quindici nomi da leggere
# restavano su un disco senza che niente lo dicesse.
#
# Best-effort e senza condizioni: `|| true` e uno `status` che non viene mai
# toccato. Un avviso mancato e' un fastidio; un giro fallito per colpa
# dell'avviso sarebbe un danno. Lo script stesso esce 0 in ogni caso --
# tools/notify.ps1 lo dichiara nella sua intestazione.
#
# Su un giro fallito si avvisa DEL GUASTO e non si legge l'esito, che sarebbe
# quello di ieri: una notifica che annuncia i numeri del giorno prima sembra
# riuscita, ed e' peggio del silenzio.
if command -v powershell.exe >/dev/null 2>&1; then
  if [ "$status" -eq 0 ]; then
    powershell.exe -NoProfile -ExecutionPolicy Bypass       -File "tools/notify.ps1" >/dev/null 2>&1 || true
  else
    powershell.exe -NoProfile -ExecutionPolicy Bypass       -File "tools/notify.ps1" -Fail "uscita $status" >/dev/null 2>&1 || true
  fi
fi

# A failed scan must not look like a successful one to whatever ran this.
if [ "$status" -ne 0 ]; then
  echo "edge-lab daily scan FAILED with status $status" >&2
fi
exit "$status"
