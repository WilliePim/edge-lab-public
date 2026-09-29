"""Russell 2000, uscite verso il basso — l'istantanea di giugno è successiva alla ricostituzione? (addendum 1)

Per ogni anno: data della ricostituzione, periodo e data di deposito dell'istantanea di IWM di giugno, sedute fra le due
date (calendario di IWM), società entrate in IWM fra marzo e giugno, uscite verso il basso e posizioni residue (presenti a
giugno con al massimo il 50% delle azioni di marzo). Abbinamento per emittente; quota residua con le sole azioni
rettificate per i frazionamenti Yahoo (senza la quota del capitale, per non scaricare companyfacts: è un controllo).

    python backtest/russell_exits/controllo_date_giugno.py
"""
from __future__ import annotations

import bisect
import csv
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT, ROOT / "tools", ROOT / "backtest" / "rematch_50_300m", HERE):
    sys.path.insert(0, str(p))

import falsi_positivi as FP  # noqa: E402
import step1_analysis as S1  # noqa: E402

GIORNI = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def main() -> int:
    ids = S1.IDS
    man = json.loads((FP.HOLD / "_manifest.json").read_text(encoding="utf-8"))
    dep = {d["accession"]: d["depositato"]
           for ds in json.loads((HERE / "risultati" / "fase0_depositi.json").read_text(encoding="utf-8"))["depositi"].values()
           for d in ds}
    righe = ["# Istantanea di giugno e ricostituzione, per anno", "",
             "Generato da `python backtest/russell_exits/controllo_date_giugno.py`. Sedute dopo = sedute di IWM con data "
             "successiva alla ricostituzione e non oltre il 30 giugno.", "",
             "| anno | ricostituzione | 30 giugno | sedute dopo | deposito (modulo, data) | entrate in IWM | uscite verso il basso | … di cui posizioni residue |",
             "|---|---|---|---:|---|---:|---:|---:|"]
    out = {}
    with (HERE / "date_ricostituzione.csv").open(encoding="utf-8", newline="") as fh:
        date_r = {int(r["anno"]): r for r in csv.DictReader(fh) if r["anno"].isdigit()}
    for anno in range(2015, 2026):
        r = date_r[anno]["ricostituzione"]
        g = "{}-06-30".format(anno)
        m = man.get("IWM_" + g)
        dopo = bisect.bisect_right(ids, g) - bisect.bisect_right(ids, r)
        if not m or m.get("esito") != "OK":
            righe.append("| {} | {} {} | {} | {} | assente | — | — | — |".format(
                anno, r, GIORNI[date.fromisoformat(r).weekday()], GIORNI[date.fromisoformat(g).weekday()], dopo))
            continue
        A = FP.Anno(anno, con_capitale=False)
        entrate = sum(1 for f, _k, _r in A.nuove if f == "IWM")
        basso = residue = 0
        for k in A.az_m:
            stato, quota, _metodo, _corr = A.classe(k, True)
            if stato == "basso":
                basso += 1
                residue += quota is not None and quota > 0
        out[anno] = {"ricostituzione": r, "sedute_dopo": dopo, "deposito": dep.get(m["accession"]), "modulo": m["tipo"],
                     "entrate": entrate, "uscite_basso": basso, "residue": residue}
        righe.append("| {} | {} {} | {} | {} | {} {} | {} | {} | {} |".format(
            anno, r, GIORNI[date.fromisoformat(r).weekday()], GIORNI[date.fromisoformat(g).weekday()], dopo, m["tipo"],
            dep.get(m["accession"], "—"), entrate, basso, residue))
    (HERE / "risultati" / "controllo_date_giugno.md").write_text("\n".join(righe) + "\n", encoding="utf-8")
    (HERE / "risultati" / "controllo_date_giugno.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(righe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
