#!/usr/bin/env bash
# Locate the project interpreter, wherever this platform put it.
#
# Sourced, not executed: it exports PY for the caller.
#
# It resolves the interpreter BINARY rather than sourcing `activate`, because
# activate's PATH manipulation does not reliably survive into Git Bash on
# Windows -- the script sources without error and `python` still resolves to
# whatever is on PATH. A silent no-op that leaves the scripts running outside
# the venv, while appearing to work, is worse than a hard failure.

if [ -n "${PY:-}" ] && [ -x "$PY" ]; then
  :                                          # gia' scelto dal chiamante
elif [ -x .venv/bin/python ]; then
  PY="$PWD/.venv/bin/python"                 # POSIX
elif [ -x .venv/Scripts/python.exe ]; then
  PY="$PWD/.venv/Scripts/python.exe"         # Windows
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
  echo "note: no .venv found, using system python3" >&2
elif command -v python >/dev/null 2>&1; then
  PY=python
  echo "note: no .venv found, using system python" >&2
else
  echo "no python interpreter found" >&2
  exit 1
fi
export PY
