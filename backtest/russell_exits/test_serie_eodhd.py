"""Test delle serie dall'archivio EODHD: chiusura rettificata per i soli frazionamenti, e frazionamenti dalle note.

Solo le funzioni pure: nessuna lettura dell'archivio. I valori di Apple sono quelli veri del 2020 (4:1 del 31 agosto).

    python backtest/russell_exits/test_serie_eodhd.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "tests"))

from harness import check, report  # noqa: E402

import serie_eodhd as E  # noqa: E402

# ---- rapporto tipico: la stessa regola del controllo dei salti dell'archivio
check("4:1 visto dalla grezza (0,258) -> 1/4", E.rapporto_tipico(129.04 / 499.23) == 0.25)
check("raggruppamento 1:10 (grezza ×10) -> 10", E.rapporto_tipico(10.0) == 10.0)
check("bordo della tolleranza del 5%: 2,1 -> 2", E.rapporto_tipico(2.1) == 2.0)
check("fuori tolleranza: 2,2 -> nessuno", E.rapporto_tipico(2.2) is None)
check("un movimento normale non è un frazionamento", E.rapporto_tipico(0.97) is None)
check("zero o negativo: nessuno", E.rapporto_tipico(0) is None and E.rapporto_tipico(-2) is None)

# ---- chiusura rettificata per i soli frazionamenti: la Close di Yahoo
grezza = {"2020-08-27": 500.04, "2020-08-28": 499.23, "2020-08-31": 129.04, "2020-09-01": 134.18}
sa = E.rettificata_per_frazionamenti(grezza, [("2020-08-31", 4.0)])
check("Apple 28-08-2020: 499,23 / 4 = 124,81, la Close di Yahoo", abs(sa["2020-08-28"] - 124.8075) < 1e-9, sa["2020-08-28"])
check("il giorno del frazionamento non si divide", sa["2020-08-31"] == 129.04)
check("dopo il frazionamento resta la grezza", sa["2020-09-01"] == 134.18)
check("la serie ricostruita non salta al frazionamento",
      abs(sa["2020-08-31"] / sa["2020-08-28"] - 1) < 0.05, sa["2020-08-31"] / sa["2020-08-28"])
sa2 = E.rettificata_per_frazionamenti({"2015-12-17": 6.59}, [("2019-03-14", 0.1)])
check("Iconix: il raggruppamento 1:10 del 2019 moltiplica per 10 il prezzo del 2015", abs(sa2["2015-12-17"] - 65.9) < 1e-9)

# ---- frazionamenti: tabella del fornitore più le note split_del_fornitore
g = {"2021-01-04": 100.0, "2021-01-05": 50.5, "2021-01-06": 51.0, "2022-06-01": 60.0, "2022-06-02": 20.3}
f = E.frazionamenti([("2021-01-05", 2.0)], [], g)
check("solo la tabella", f == [("2021-01-05", 2.0)])
f = E.frazionamenti([], ["2022-06-02"], g)
check("una nota diventa un frazionamento 3:1 (grezza da 60 a 20,3)", f == [("2022-06-02", 3.0)], f)
f = E.frazionamenti([("2021-01-05", 2.0)], ["2021-01-05"], g)
check("nota sulla stessa data della tabella: non si applica due volte", f == [("2021-01-05", 2.0)], f)
f = E.frazionamenti([], ["2021-01-06"], g)
check("nota su un movimento che non è un rapporto tipico: ignorata", f == [], f)
f = E.frazionamenti([], ["2021-01-04"], g)
check("nota sulla prima barra, senza barra prima: ignorata", f == [], f)
f = E.frazionamenti([("2021-01-05", 0)], [], g)
check("fattore zero nella tabella: scartato", f == [], f)

sys.exit(report("SERIE EODHD"))
