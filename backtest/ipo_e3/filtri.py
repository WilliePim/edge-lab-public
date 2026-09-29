"""E3, fase 2 — filtri di qualità delle rotte (e il filtro fusioni delle forti). Solo depositi precedenti all'ingresso.

Legge `casi.csv`, scrive `state/backfill/ipo_e3/filtri.csv`: una riga per (caso, ingresso), perché un filtro vale
alla data d'ingresso e le rotte ne hanno tre (A, B, C). Una rotta entra nella cella di un ingresso solo se passa tutti
e quattro i filtri a quella data. «Non verificabile» (dato assente) non passa, e si conta a parte per filtro.

Dati: i due zip in blocco della SEC (ADR-046), letti dentro lo zip. Nessuna chiamata EDGAR.

1. **Flusso di cassa operativo, ultimi 12 mesi > 0**: `russell_exits/filtri_xbrl.f1_flusso_cassa` (tag
   `NetCashProvidedByUsedInOperatingActivities`, poi `...ContinuingOperations`; anno fiscale più progressivo, oppure
   quattro trimestri consecutivi; dato non più vecchio di 270 giorni). I bilanci del prospetto non sono in XBRL:
   conta il primo 10-Q/10-K depositato prima dell'ingresso. Dove i 12 mesi non sono calcolabili, il progressivo di
   6-12 mesi deve essere positivo (`f1_progressivo`, opzione (b) della fermata 1).
2. **Cassa netta, oppure debito netto / EBITDA < 3**; EBITDA ≤ 0 con debito netto positivo esclude:
   `filtri_xbrl.f2_leva`, invariato.
3. **Nessuna emissione dall'IPO**, due parti che devono essere vere tutte e due:
   - nessun deposito fra la data di collocamento + 15 giorni (fuori il 424B4 dell'IPO e i suoi strascichi) e
     l'ingresso fra: S-1 e S-3 (con le loro varianti), 424B1/B2/B3/B4/B5/B7, e 8-K con la voce 3.02 (vendita di
     azioni non registrate, dove passano convertibili e collocamenti privati). Il 424B5 copre anche gli ATM;
   - azioni in circolazione cresciute al massimo del 5% dal primo deposito dopo il collocamento all'ultimo prima
     dell'ingresso (`dei:EntityCommonStockSharesOutstanding`, classi sommate per deposito, come nel Russell),
     corrette per i frazionamenti intercorsi.
4. **Nessuna fusione o acquisizione annunciata**: nessun deposito della società fra il collocamento e l'ingresso fra
   quelli di `survival.ACQ` (DEFM14A, DEFM14C, SC TO-T, SC TO-C, SC 13E3, SC 14D9), più PREM14A, PREM14C e 425.

Le forti passano solo il filtro 4, alla data di controllo (la forza è il segnale; la direttiva).

    python backtest/ipo_e3/filtri.py
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json

import bulk
import comune as C

EMISSIONE = frozenset({"S-1", "S-1/A", "S-1MEF", "S-3", "S-3/A", "S-3ASR", "S-3MEF", "424B1", "424B2", "424B3", "424B4",
                       "424B5", "424B7"})
GIORNI_DOPO_IPO = 15
SOGLIA_AZIONI = 0.05
USCITA = C.STATO / "filtri.csv"


def _fusioni() -> frozenset:
    import survival as SV                              # backtest/rematch_50_300m/survival.py
    return frozenset(SV.ACQ) | {"PREM14A", "PREM14C", "425"}


def fattore_split(splits: list[tuple[str, float]], da: str, a: str) -> float:
    f = 1.0
    for d, s in splits:
        if da < d <= a:
            f *= s
    return f


def emissioni(dep: list[tuple] | None, cf: dict | None, collocamento: str, ingresso: str,
              splits: list[tuple[str, float]]) -> tuple[bool | None, str]:
    if dep is None:
        return None, "submissions assenti"
    da = (dt.date.fromisoformat(collocamento) + dt.timedelta(days=GIORNI_DOPO_IPO)).isoformat()
    trovati = sorted({f if not f.startswith("8-K") else "8-K 3.02" for d, f, voci, *_ in dep
                      if da <= d < ingresso and (f in EMISSIONE or (f.startswith("8-K") and "3.02" in voci))})
    if trovati:
        return False, "depositi: " + ", ".join(trovati)
    import filtri_xbrl as FX                           # backtest/russell_exits/filtri_xbrl.py
    per, tag = FX.azioni_per_deposito(cf, ingresso) if cf else ({}, None)
    dopo = sorted(k for k in per if k[0] >= collocamento)
    if not dopo:
        return None, "nessun deposito con le azioni dopo il collocamento"
    base, ultimo = dopo[0], dopo[-1]
    if per[base] <= 0:
        return None, "azioni non positive"
    crescita = per[ultimo] / (per[base] * fattore_split(splits, base[0], ultimo[0])) - 1.0
    return crescita <= SOGLIA_AZIONI, "{} {:+.1%} da {} a {}".format(tag, crescita, base[0], ultimo[0])


def fusioni(dep: list[tuple] | None, collocamento: str, ingresso: str) -> tuple[bool | None, str]:
    if dep is None:
        return None, "submissions assenti"
    forme = _fusioni()
    trovati = sorted({f for d, f, *_ in dep if collocamento <= d < ingresso and f in forme})
    return (not trovati), ("annunci: " + ", ".join(trovati) if trovati else "nessun annuncio")


def f1_progressivo(cf, rif: str) -> tuple[bool | None, str]:
    """Filtro 1, opzione (b) scelta dall'utente alla fermata 1: il segno dell'ultimo flusso di cassa operativo
    progressivo di 6-12 mesi depositato prima di `rif`, usato solo dove quello dei 12 mesi non è calcolabile. Resta
    un vincolo di flusso positivo, meno rigido solo sul periodo; senza dato è «non verificabile» e non passa."""
    import filtri_xbrl as FX
    for tag in FX.DURATION["ocf"]:
        fs = [f for f in FX.fatti(cf, "us-gaap", tag, "USD", rif) if f.get("start") and 170 <= FX._durata(f) <= 380]
        if fs:
            f = max(fs, key=lambda f: (f["end"], FX._durata(f)))
            if (FX._d(rif) - FX._d(f["end"])).days > FX.ETA_MAX:
                return None, "progressivo vecchio ({})".format(f["end"])
            return float(f["val"]) > 0, "{:,.0f} dal {} al {}".format(float(f["val"]), f["start"], f["end"])
    return None, "nessun progressivo di almeno 6 mesi"


def filtri_rotta(cik: str, collocamento: str, ingresso: str, splits) -> dict:
    import filtri_xbrl as FX
    cf = bulk.companyfacts(cik)
    _t, dep = bulk.submissions(cik)
    dep = dep if _t is not None else None
    return {"f1": FX.f1_flusso_cassa(cf, ingresso) if cf else (None, "companyfacts assente"),
            "f2": FX.f2_leva(cf, ingresso) if cf else (None, "companyfacts assente"),
            "f3": emissioni(dep, cf, collocamento, ingresso, splits),
            "f4": fusioni(dep, collocamento, ingresso)}


def main() -> int:
    import serie_eodhd as SE
    ids = C.ids()
    casi = [x for x in csv.DictReader((C.STATO / "casi.csv").open(encoding="utf-8")) if x["gruppo"] in ("rotta", "forte")]
    SE.carica([x["codice"] for x in casi if x["gruppo"] == "rotta"], ids)
    righe, conta = [], collections.defaultdict(collections.Counter)
    for x in casi:
        if x["gruppo"] == "forte":
            _t, dep = bulk.submissions(x["cik"])
            f4 = fusioni(dep if _t is not None else None, x["data_collocamento"], x["ingresso_forte"])
            esiti = {"f4": f4}
            ingressi = {"forte": x["ingresso_forte"]}
        else:
            ser, _ = SE.serie_seguita(x["codice"], ids)
            splits = ser[3] if ser else []
            ingressi = {k: x["ingresso_" + k] for k in ("A", "B", "C") if x["ingresso_" + k]}
            esiti = None
        for nome, data in ingressi.items():
            e = esiti if esiti is not None else filtri_rotta(x["cik"], x["data_collocamento"], data, splits)
            if esiti is None:
                #  Filtro 1, opzione (b) scelta alla fermata 1: dove i 12 mesi non sono calcolabili, il flusso di cassa
                #  operativo progressivo di 6-12 mesi deve essere positivo. «Non verificabile» resta fuori.
                if e["f1"][0] is None:
                    cf = bulk.companyfacts(x["cik"])
                    f1b = f1_progressivo(cf, data) if cf else (None, "companyfacts assente")
                    e = dict(e, f1=(f1b[0], "12 mesi: {}; progressivo: {}".format(e["f1"][1], f1b[1])))
            passa = all(v[0] is True for v in e.values())
            riga = {"cik": x["cik"], "nome": x["nome"], "anno": x["anno"], "gruppo": x["gruppo"], "ingresso": nome,
                    "data_ingresso": data, "passa": "sì" if passa else "no"}
            for k in ("f1", "f2", "f3", "f4"):
                if k in e:
                    riga[k] = {True: "passa", False: "non passa", None: "non verificabile"}[e[k][0]]
                    riga[k + "_nota"] = e[k][1]
                    conta[(x["gruppo"], nome, k)][riga[k]] += 1
            righe.append(riga)
    campi = ["cik", "nome", "anno", "gruppo", "ingresso", "data_ingresso", "passa",
             "f1", "f1_nota", "f2", "f2_nota", "f3", "f3_nota", "f4", "f4_nota"]
    with USCITA.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=campi, extrasaction="ignore")
        w.writeheader()
        w.writerows(righe)
    for k in sorted(conta):
        print(k, dict(conta[k]))
    print("passano:", collections.Counter((r["gruppo"], r["ingresso"]) for r in righe if r["passa"] == "sì"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
