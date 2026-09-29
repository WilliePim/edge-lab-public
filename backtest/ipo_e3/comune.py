"""E3 — IPO rotte e IPO forti: percorsi, calendario, tetto EDGAR, indici trimestrali. Condiviso da tutti i passi.

- **Calendario**: sedute della borsa americana dall'archivio EODHD (`market_data.api.trading_days("US")`), dal 2011
  per avere le 126 sedute prima delle prime IPO del 2012. Le stesse sedute di IWM usate nel Russell, dove si
  sovrappongono (3.183 dal 2014 al 28-08-2026). Ultima seduta: l'ultima barra di IWM nell'archivio.
- **Tetto EDGAR**: 3.000 chiamate, contatore `backtest/ipo_e3/edgar_calls.json`, lo stesso `Budget` del Russell. I due
  zip in blocco contano una chiamata ciascuno (`bulk.py`).
- **Indici trimestrali** `form.idx`: in cache dal 2013; il 2012 costa quattro chiamate.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", ROOT / "backtest" / "russell_exits", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

STATO = ROOT / "state" / "backfill" / "ipo_e3"
RISULTATI = HERE / "risultati"
CALLS = HERE / "edgar_calls.json"
TETTO = 3000
ANNI = range(2012, 2025)
INIZIO_CALENDARIO = "2011-06-01"

FULL_INDEX = "https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx"
#  Come `tools/spinoffs.py`: le colonne di form.idx non stanno dove dice la testata; si legge per forma.
ROW_RE = re.compile(r"^(?P<form>.*?)\s{2,}(?P<name>.*?)\s{2,}(?P<cik>\d+)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+"
                    r"(?P<path>\S+)\s*$")

_budget = None
_ids = None


def budget():
    global _budget
    if _budget is None:
        import sec as RS                      # backtest/russell_exits/sec.py
        _budget = RS.Budget(TETTO, calls=CALLS)
    return _budget


def ids() -> list[str]:
    """Sedute della borsa americana, ISO, dal 2011-06-01 all'ultima barra di IWM nell'archivio."""
    global _ids
    if _ids is None:
        from market_data import api
        ultima = str(api.prices(["IWM.US"], start="2026-01-01", clean=True)["date"].max())[:10]
        _ids = [d.isoformat() for d in api.trading_days("US", INIZIO_CALENDARIO, ultima)]
    return _ids


def righe_indice(forme: tuple[str, ...], anni=ANNI) -> list[tuple[str, str, str, str, str]]:
    """[(forma, cik a 10 cifre, data, nome, percorso)] delle forme date, dagli indici trimestrali."""
    fuori = []
    for y in anni:
        for q in (1, 2, 3, 4):
            t = budget().get(FULL_INDEX.format(y=y, q=q))
            if t is None:
                raise SystemExit("indice {} T{} non disponibile (tetto?)".format(y, q))
            for line in t.splitlines():
                m = ROW_RE.match(line)
                if m and m["form"].strip() in forme:
                    fuori.append((m["form"].strip(), m["cik"].zfill(10), m["date"], m["name"].strip(), m["path"]))
    return fuori
