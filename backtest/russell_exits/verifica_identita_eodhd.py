"""Russell 2000, uscite verso il basso — verifica dell'identità con il prezzo implicito, sui prezzi EODHD.

Stessa regola di `verifica_identita.py` (pre-registrazione §3): prezzo implicito = valore della posizione del fondo /
azioni; l'identità è verificata se la chiusura **non rettificata** del titolo alla data dell'istantanea coincide entro
il 3%. Cambia la fonte dei prezzi.

**Perché.** Con Yahoo la verifica falliva soprattutto per `NESSUN_PREZZO_YAHOO`: 932 righe su 1.964 nell'istantanea
del 31 marzo 2016, contro 204 nel 2025. Yahoo non conserva i titoli usciti dal listino, cioè proprio quelli che
diventano casi: fra le uscite del 2015-2018 l'identità risolta era il 23-32%. L'archivio EODHD conserva 36.049
titoli americani delistati dal 1962, e i ticker riusati hanno codici separati (`P` e `P_old`).

**Come.** Da ogni CIK candidato a tutti i codici EODHD con quel CIK, compresi quelli `_old`. La chiusura di EODHD è
già quella scambiata quel giorno: non serve ricostruirla moltiplicando i frazionamenti successivi, come con Yahoo.
Se il 31 marzo non è una seduta vale l'ultima chiusura entro cinque giorni prima. Si confronta con la chiusura
**grezza** (`clean=False`): qui si verifica chi è la società, non se i suoi prezzi sono usabili — quello lo dice la
copertura dei prezzi, a parte.

Legge i prezzi solo tramite `market_data.api` (ADR-040). Non tocca `identita.csv`, che resta quella con Yahoo su cui
sono state fatte le misure fin qui: scrive `identita_eodhd.csv`.

    python backtest/russell_exits/verifica_identita_eodhd.py
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import math
import sys
from pathlib import Path

from market_data import api

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STATE = ROOT / "state" / "backfill" / "russell"
OUT = STATE / "identita_eodhd.csv"
RIEPILOGO = HERE / "risultati" / "identita_eodhd_riepilogo.json"
TOLLERANZA = 0.03                 # la stessa della verifica con Yahoo
GIORNI_INDIETRO = 5               # il 31 marzo può cadere di sabato o di domenica
BLOCCO_SIMBOLI = 1500             # simboli per richiesta, per stare sotto il tetto di memoria


def cik10(c: str) -> str:
    return str(c).strip().zfill(10)


def codici_per_cik() -> dict[str, list[str]]:
    """CIK -> codici EODHD americani con quel CIK, attivi e delistati, compresi i `_old` dei ticker riusati."""
    df = api.listings(exchange="US")
    fuori = collections.defaultdict(list)
    for code, cik in zip(df["code"], df["cik"]):
        if cik:
            fuori[cik10(cik)].append(code)
    return fuori


def chiusure_alla_data(codici: list[str], giorno: dt.date) -> dict[str, float]:
    """codice -> ultima chiusura grezza entro GIORNI_INDIETRO giorni prima di `giorno` (compreso)."""
    fuori = {}
    da = giorno - dt.timedelta(days=GIORNI_INDIETRO)
    for i in range(0, len(codici), BLOCCO_SIMBOLI):
        simboli = ["{}.US".format(c) for c in codici[i:i + BLOCCO_SIMBOLI]]
        df = api.prices(simboli, start=da, end=giorno, clean=False)
        if df.empty:
            continue
        df = df.sort_values(["code", "date"])
        ultime = df.groupby("code").tail(1)
        for code, chiusura in zip(ultime["code"], ultime["close"]):
            if chiusura and chiusura == chiusura and chiusura > 0:
                fuori[code] = float(chiusura)
    return fuori


def main(argv=None) -> int:
    with (STATE / "identita_candidati.csv").open(encoding="utf-8", newline="") as fh:
        righe = list(csv.DictReader(fh))
    per_cik = codici_per_cik()
    print("CIK con almeno un codice EODHD:", len(per_cik), flush=True)

    #  Una lettura di prezzi per istantanea, con tutti i codici che servono a quell'istantanea.
    per_istantanea = collections.defaultdict(set)
    for r in righe:
        for c in (x for x in r["candidati"].split(";") if x):
            per_istantanea[r["istantanea"]].update(per_cik.get(cik10(c), ()))
    chiusure = {}
    for istantanea, codici in sorted(per_istantanea.items()):
        giorno = dt.date.fromisoformat(istantanea.split("_")[1])
        chiusure[istantanea] = chiusure_alla_data(sorted(codici), giorno)
        print("  {}: {} codici, {} con una chiusura".format(istantanea, len(codici), len(chiusure[istantanea])),
              flush=True)

    righe_out = []
    riep = collections.defaultdict(collections.Counter)
    valore = collections.defaultdict(collections.Counter)
    for r in righe:
        ist = r["istantanea"]
        try:
            implicito = float(r["valore"]) / float(r["azioni"])
        except (ValueError, ZeroDivisionError):
            implicito = None
        esito, cik, codice, scarto, motivo = "NON_VERIFICATA", "", "", "", ""
        cands = [c for c in r["candidati"].split(";") if c]
        if not cands:
            motivo = "NESSUN_CANDIDATO"
        elif implicito is None or implicito <= 0:
            motivo = "PREZZO_IMPLICITO_ASSENTE"
        else:
            visto, migliore = False, None
            for c in cands:
                for code in per_cik.get(cik10(c), ()):
                    chiusura = chiusure[ist].get(code)
                    if not chiusura:
                        continue
                    visto = True
                    e = abs(math.log(chiusura / implicito))
                    migliore = e if migliore is None else min(migliore, e)
                    if e <= TOLLERANZA:
                        esito, cik, codice, scarto = "VERIFICATA", c, code, round(e, 4)
                        break
                if esito == "VERIFICATA":
                    break
            if esito == "NON_VERIFICATA":
                motivo = "PREZZO_DIVERSO" if visto else "NESSUN_PREZZO_EODHD"
                scarto = round(migliore, 4) if migliore is not None else ""
        riep[ist][esito if esito == "VERIFICATA" else motivo] += 1
        valore[ist]["totale"] += float(r["valore"] or 0)
        if esito == "VERIFICATA":
            valore[ist]["verificato"] += float(r["valore"] or 0)
        righe_out.append({"istantanea": ist, "nome": r["nome"], "titolo": r["titolo"], "cusip": r["cusip"],
                          "azioni": r["azioni"], "valore": r["valore"], "prezzo_implicito": implicito,
                          "chiave": r["chiave"], "metodo": r["metodo"], "candidati": r["candidati"], "esito": esito,
                          "motivo": motivo, "cik": cik, "codice_eodhd": codice, "scarto_log": scarto})

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(righe_out[0]))
        w.writeheader()
        w.writerows(righe_out)
    out = {k: {"righe": dict(v), "quota_valore_verificato": round(valore[k]["verificato"] / valore[k]["totale"], 4)}
           for k, v in sorted(riep.items())}
    RIEPILOGO.parent.mkdir(parents=True, exist_ok=True)
    RIEPILOGO.write_text(json.dumps(out, indent=1), encoding="utf-8")
    for k, v in out.items():
        n = sum(v["righe"].values())
        print("{} righe {} verificate {} ({:.1%}) | {}".format(k, n, v["righe"].get("VERIFICATA", 0),
                                                                v["righe"].get("VERIFICATA", 0) / n, dict(v["righe"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
