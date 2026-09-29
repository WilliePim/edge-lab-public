"""E3, fermata 1 — le IPO escluse per «meno dell'80% di barre» a causa di un `salto_sospetto` dell'archivio.

L'archivio segnala un salto simile a un frazionamento non verificato e toglie dai prezzi puliti tutta la storia dalla
prima barra al salto (es. AAA: prima barra 2014-02-03, salto del 2023-12-18, esclusi 2014-02-03 … 2023-12-17). La
serie pulita non arriva quindi all'80% di barre fino alla data di controllo e l'IPO esce, anche quando il salto cade
anni dopo. Le IPO toccate non sono un campione a caso: il salto è quasi sempre un raggruppamento, cioè un titolo che
è sceso molto.

Questo script **conta soltanto**, per la decisione dell'utente alla fermata 1: per ciascuna di quelle IPO, se il
salto segnalato cade dopo la data di controllo e fra la prima barra e il controllo non ci sono né salti né
frazionamenti, la classifica sulle chiusure grezze (che in quella finestra sono nelle unità del prospetto), con le
stesse regole di `casi.py`: coerenza ADR-051, rotta ≤ −30% alla data di controllo, forte mai sotto il collocamento.
Nessun prezzo dopo la data di controllo, nessun rendimento extra.

Scrive `state/backfill/ipo_e3/salti.csv`.

    python backtest/ipo_e3/salti.py
"""
from __future__ import annotations

import bisect
import collections
import csv
import re

import casi as K
import comune as C

USCITA = C.STATO / "salti.csv"


def main() -> int:
    from market_data import api
    ids = C.ids()
    casi = [x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8"))
            if x["motivo"].startswith("meno dell'80%")]
    simboli = ["{}.US".format(x["codice"]) for x in casi]
    fl = api.flags(simboli)
    salti = collections.defaultdict(list)
    for code, ctl, det in zip(fl["code"], fl["controllo"], fl["detail"]):
        m = re.search(r"salto del (\d{4}-\d{2}-\d{2})", str(det))
        if ctl == "salto_sospetto" and m:
            salti[str(code).removesuffix(".US")].append(m.group(1))
    tab = api.splits(simboli)
    split = collections.defaultdict(list)
    for code, d in zip(tab["code"], tab["date"]):
        split[str(code).removesuffix(".US")].append(str(d)[:10])
    df = api.prices(simboli, start="2011-06-01", end=ids[-1], clean=False)
    serie = collections.defaultdict(dict)
    for code, d, cl in zip(df["code"], df["date"], df["close"]):
        serie[str(code).removesuffix(".US")][str(d)[:10]] = float(cl)
    righe = []
    for x in casi:
        c, a, fine = x["codice"], x["prima_barra"], x["controllo"]
        r = {"cik": x["cik"], "nome": x["nome"], "anno": x["anno"], "codice": c, "prima_barra": a,
             "controllo": fine, "salti": ";".join(sorted(set(salti[c]))), "esito": "", "gruppo": ""}
        giorni = ids[bisect.bisect_left(ids, a):bisect.bisect_left(ids, fine) + 1]
        s = serie[c]
        pres = [s[d] for d in giorni if d in s]
        if not salti[c]:
            r["esito"] = "nessun salto_sospetto segnalato"
        elif any(a <= d <= fine for d in salti[c]) or any(a < d <= fine for d in split[c]):
            r["esito"] = "salto o frazionamento dentro la finestra"
        elif len(pres) < K.COPERTURA * len(giorni):
            r["esito"] = "barre grezze sotto l'80%"
        elif not (K.COERENZA[0] <= pres[0] / float(x["prezzo"]) <= K.COERENZA[1]):
            r["esito"] = "prima chiusura incoerente (ADR-051)"
        else:
            off = float(x["prezzo"])
            cc = next(s[d] for d in reversed(giorni[-(K.STALE + 1):]) if d in s)
            r["esito"] = "classificabile"
            r["gruppo"] = ("rotta" if cc / off - 1 <= K.SOGLIA_ROTTA
                           else "forte" if min(pres) >= off else "intermedia")
        righe.append(r)
    with USCITA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe[0].keys()))
        w.writeheader()
        w.writerows(righe)
    print(len(righe), collections.Counter(r["esito"] for r in righe),
          collections.Counter(r["gruppo"] for r in righe if r["gruppo"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
