"""`backtest/splits.py` su dati SINTETICI: classificazione di uno split, lettura del rapporto dal testo, popolazione
obbligatoria.

Il comando `salti` legge il panel prezzi e il corpus Form 4 sotto `state/` (non pubblicati) e, dopo la copia
pubblica, riceve la popolazione degli eventi solo come argomento (`--popolazione`, senza default). Qui si provano le
parti pure, su testi e numeri inventati, senza rete:

    python backtest/test_splits_sintetico.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tests")]

from harness import check, raises, report  # noqa: E402

import splits as SP  # noqa: E402

# -------------------------------------------------------------- addendum 5 §4 --
check("osservato 0,1 contro atteso 0,1: CONFERMATO", SP.classifica_split(0.1, 0.1) == "CONFERMATO")
check("osservato 0,12 contro atteso 0,1 (entro 1,5x): CONFERMATO", SP.classifica_split(0.12, 0.1) == "CONFERMATO")
check("osservato 1,1 (nessun salto visibile) contro atteso 0,1: PIATTO", SP.classifica_split(1.1, 0.1) == "PIATTO")
check("osservato 0,03 contro atteso 0,1 (oltre 1,5x): DISCORDE", SP.classifica_split(0.03, 0.1) == "DISCORDE")

# ------------------------------------------------------ rapporto letto da un 8-K --
testo = ("AAA Corp (the Company) announced that its Board approved a 1-for-10 reverse stock split, "
         "effective as of March 3, 2021. Following the 1-for-10 reverse stock split, each ten shares ...")
r, d, _cit = SP.leggi_split(testo)
check("«1-for-10 reverse stock split» -> 0,1 con la data effettiva", r == 0.1 and d == "2021-03-03", (r, d))
r, d, _ = SP.leggi_split("BBB Inc. declares a three-for-two stock split payable to holders of record.")
check("«three-for-two stock split» in parole -> 1,5, senza data", r == 1.5 and d is None, (r, d))
check("nessuno split nel testo: None", SP.leggi_split("CCC Inc. reports quarterly results.") is None)

# ------------------------------------------------ popolazione come argomento obbligatorio --
check("`salti` senza --popolazione: argparse si ferma", raises(lambda: SP.main(["salti"]), SystemExit))
check("popolazione inesistente: il comando si ferma prima di leggere il panel",
      raises(lambda: SP.insieme_usato([HERE / "non_esiste.jsonl"]), SystemExit)
      if not (SP.STATE / "form4_raw").exists() else True)

if __name__ == "__main__":
    sys.exit(report("TEST SINTETICI DI SPLITS PASSATI"))
