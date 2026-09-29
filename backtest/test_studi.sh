#!/usr/bin/env bash
# Test degli studi pubblicati (E2 russell_exits, E3 ipo_e3, ri-test rematch_50_300m, splits), offline.
#
# Girano solo su dati sintetici o costruiti nel test: nessun prezzo, ticker o CIK reale, nessuna rete.
# I referti degli studi NON si rigenerano da qui: servono l'archivio prezzi con licenza (EODHD), il panel
# Yahoo e le cache EDGAR, che non sono in questo repo.
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. ./venv.sh
# Output in UTF-8 anche quando stdout e' una pipe: su Windows il default e' cp1252, che non codifica «−» e fa
# fallire una suite per la stampa, non per il test.
export PYTHONIOENCODING=utf-8

failed=0
names=""
for t in backtest/test_*.py backtest/*/test_*.py; do
  [ -f "$t" ] || continue
  echo "==> $t"
  if "$PY" "$t" | tail -2; then :; else
    failed=$((failed + 1))
    names="$names $t"
  fi
done

echo
if [ "$failed" -eq 0 ]; then
  echo "ALL STUDY SUITES PASSED"
else
  echo "$failed STUDY SUITE(S) FAILED:$names"
  exit 1
fi
