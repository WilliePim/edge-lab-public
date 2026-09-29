"""E3, fermata 2 — controllo di sensibilità **post hoc**, trovato dopo i rendimenti: non cambia nessun verdetto.

Guardando i valori estremi della base di coorte (Taylor Morrison, −22.117% a 252 sedute), è emerso che per alcune IPO
le azioni in circolazione in XBRL (`dei:EntityCommonStockSharesOutstanding`) sono assurde. La capitalizzazione del
caso esce di poche migliaia di dollari, e i «5 più vicini per capitalizzazione» sono titoli da pochi centesimi con
serie rotte. La regola pre-registrata resta quella, e i verdetti si leggono su di essa. Qui si rifanno le celle
togliendo i casi la cui capitalizzazione è sotto un decimo di quella implicita nel prospetto (prezzo di collocamento
× azioni dopo l'offerta), per mostrare quanto pesano.

Il criterio guarda solo in basso. Sopra 10 volte ci sono soprattutto prospetti che riportano una sola classe
(GoPro, Doximity).

    python backtest/ipo_e3/sensibilita.py
"""
from __future__ import annotations

import collections
import csv
import json

import analisi as A
import comune as C

SOGLIA = 0.1
USCITA = C.RISULTATI / "sensibilita.json"


def main() -> int:
    casi = {x["cik"]: x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8"))}
    sospetti, elenco = set(), []
    for p in csv.DictReader((C.STATO / "peer.csv").open(encoding="utf-8")):
        c = casi[p["cik"]]
        if p["esito"] != "ok" or not c["azioni_dopo"] or not c["prezzo"]:
            continue
        rapporto = float(p["cap"]) / (float(c["azioni_dopo"]) * float(c["prezzo"]))
        if rapporto < SOGLIA:
            sospetti.add((p["cik"], p["ingresso"]))
            elenco.append({"nome": c["nome"], "ingresso": p["ingresso"], "cap_xbrl": float(p["cap"]),
                           "cap_prospetto": float(c["azioni_dopo"]) * float(c["prezzo"]),
                           "rapporto": round(rapporto, 5)})
    righe = [r for r in csv.DictReader((C.STATO / "rendimenti.csv").open(encoding="utf-8")) if r["extra"]]
    celle = {}
    for ing, fin in (("B", "252"), ("B", "placebo"), ("forte", "252"), ("forte", "placebo"),
                     ("base", "63"), ("base", "126"), ("base", "252")):
        per = collections.defaultdict(list)
        for r in righe:
            if r["ingresso"] == ing and r["finestra"] == fin and (r["cik"], ing) not in sospetti:
                per[int(r["anno"])].append(float(r["extra"]))
        celle["{} × {}".format(ing, fin)] = A.statistiche(per)
    verdetti = {}
    for domanda, (ing, h) in A.VERDETTI.items():
        v, criteri = A.verdetto(celle["{} × {}".format(ing, h)], celle["{} × placebo".format(ing)])
        verdetti[domanda] = {"esito": v, "criteri": criteri}
    USCITA.write_text(json.dumps({"soglia": SOGLIA, "esclusi": elenco, "celle": celle, "verdetti": verdetti},
                                 indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    for d, v in verdetti.items():
        print(d, v["esito"])
    for k, c in celle.items():
        print(k, c["casi"], c["mediana"], c["media_delle_medie"], c["t"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
