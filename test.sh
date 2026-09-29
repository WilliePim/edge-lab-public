#!/usr/bin/env bash
# Full offline test suite for the event-driven scanner. No network required.
#
# Runs every test file to completion and reports the failures together. An
# earlier version aborted on the first failing file, which meant a single
# breakage hid every other one behind it.
set -uo pipefail
cd "$(dirname "$0")"
# shellcheck disable=SC1091
. ./venv.sh
# Output in UTF-8 anche quando stdout e' una pipe (su Windows il default e' cp1252).
export PYTHONIOENCODING=utf-8

failed=0
names=""
for t in tests/test_*.py; do
  echo "==> $t"
  if "$PY" "$t" | tail -3; then :; else
    failed=$((failed + 1))
    names="$names $t"
  fi
done

# edgar_llm/ gira con pytest, e solo lui: i marker servono a tenere fuori dal
# run di default i test che chiamano davvero l'API, cosa che l'harness non sa
# fare. Il confine e' la directory ed e' lo stesso del perimetro pubblico --
# edgar_llm/docs/adr/007-pytest-solo-qui.md.
#
# Se pytest non c'e', la suite NON passa in silenzio: dice che non ha girato.
if [ -d edgar_llm ]; then
  echo "==> edgar_llm (pytest)"
  if "$PY" -m pytest edgar_llm -c edgar_llm/pytest.ini 2>&1 | tail -3; then :; else
    failed=$((failed + 1))
    names="$names edgar_llm"
  fi
else
  #  Il perimetro pubblico non porta edgar_llm/: la sua assenza non e' un fallimento.
  echo "==> edgar_llm assente: saltato"
fi

# market-data/ ha i suoi test pytest (market-data/docs/adr/007), con la configurazione nel suo
# pyproject.toml ([tool.pytest.ini_options]) e il path messo da tests/conftest.py.
# Stessa regola di edgar_llm: se pytest non c'e', la suite dice che non ha girato.
if [ -d market-data ]; then
  echo "==> market-data (pytest)"
  if "$PY" -m pytest market-data/tests -c market-data/pyproject.toml 2>&1 | tail -3; then :; else
    failed=$((failed + 1))
    names="$names market-data"
  fi
else
  #  Il perimetro pubblico non porta market-data/: la sua assenza non e' un fallimento.
  echo "==> market-data assente: saltato"
fi

# Test degli studi pubblicati (backtest/): solo dati sintetici, nessuna rete. Stesso interprete ($PY esportato).
if [ -f backtest/test_studi.sh ]; then
  echo "==> backtest/test_studi.sh"
  if bash backtest/test_studi.sh 2>&1 | tail -3; then :; else
    failed=$((failed + 1))
    names="$names backtest/test_studi.sh"
  fi
fi

echo
if [ "$failed" -eq 0 ]; then
  echo "ALL SUITES PASSED"
else
  echo "$failed SUITE(S) FAILED:$names"
  exit 1
fi
