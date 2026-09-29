"""Test della definizione di uscita dell'addendum 1 (azioni rettificate, quota del capitale, soglia 50%).

    python backtest/russell_exits/test_uscite.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests"))

from harness import check, report  # noqa: E402

import uscite as U  # noqa: E402

check("assente a giugno: quota 0, metodo assente", U.quota_residua(1000, 0) == (0.0, "assente"))
check("9% delle azioni senza frazionamenti", U.quota_residua(1000, 90, split=[], da="2025-03-31", a="2025-06-30") == (0.09, "azioni rettificate"))
q, m = U.quota_residua(1000, 100, split=[("2025-05-01", 0.1)], da="2025-03-31", a="2025-06-30")
check("raggruppamento 1:10 fra le date: 100 azioni dopo = 1000 prima, quota 1", abs(q - 1.0) < 1e-12 and m == "azioni rettificate", str(q))
q, _ = U.quota_residua(1000, 2000, split=[("2025-05-01", 2.0)], da="2025-03-31", a="2025-06-30")
check("frazionamento 2:1 fra le date: quota 1", abs(q - 1.0) < 1e-12)
q, _ = U.quota_residua(1000, 100, split=[("2025-07-15", 0.1)], da="2025-03-31", a="2025-06-30")
check("raggruppamento dopo la data dopo: non conta, quota 0,1", abs(q - 0.1) < 1e-12)
q, _ = U.quota_residua(1000, 100, split=[("2025-03-31", 0.1)], da="2025-03-31", a="2025-06-30")
check("raggruppamento il giorno della data prima: già nelle azioni di marzo, non conta", abs(q - 0.1) < 1e-12)
q, m = U.quota_residua(1000, 100, split=None, quota_capitale=(0.02, 0.019))
check("senza serie: quota del capitale", abs(q - 0.95) < 1e-12 and m == "quota del capitale")
check("senza serie e senza quota del capitale: non calcolabile", U.quota_residua(1000, 100) == (None, None))

check("in IWB dopo: verso l'alto", U.classifica(True, True, 0.1) == "alto")
check("assente da IWM e da IWB: verso il basso", U.classifica(False, False, 0.0) == "basso")
check("quota 0,50: verso il basso (al massimo il 50%)", U.classifica(True, False, 0.5) == "basso")
check("quota 0,51: rimasto", U.classifica(True, False, 0.51) == "rimasto")
check("presente con quota non calcolabile: non classificato", U.classifica(True, False, None) is None)

if __name__ == "__main__":
    sys.exit(report("TEST USCITE PASSATI"))
