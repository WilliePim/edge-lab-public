"""E3, fase 0 punto 2 — il prospetto di ogni IPO rimasta dopo le esclusioni dell'universo. Riprende da dove si è fermato.

Uscita: `state/backfill/ipo_e3/prospetti.jsonl`, una riga per CIK con i campi di `prospetto.estrai`, le citazioni,
l'url del documento e l'esito della lettura:

- `letto`: il documento principale è stato scaricato (o era in cache) e le regole sono state applicate;
- `documento principale assente`: le submissions in blocco non danno il documento principale dell'accession;
- `scaricamento fallito`: EDGAR non ha restituito il documento (errore non recuperato dal client);
- `tetto`: la chiamata avrebbe superato le 3.000; la lettura si ferma lì e il conteggio lo dice.

Una chiamata per prospetto non in cache, contata nel tetto di E3 (`edgar_calls.json`).

    python backtest/ipo_e3/leggi_prospetti.py
"""
from __future__ import annotations

import csv
import json

import comune as C
import prospetto as P

USCITA = C.STATO / "prospetti.jsonl"


def ricalcola_da_cache() -> int:
    """Riapplica le regole di `prospetto.estrai` a tutti i prospetti già scaricati, senza chiamate: il testo viene
    dalla cache EDGAR. Le righe il cui documento non è in cache restano com'erano. Si usa quando le regole cambiano
    prima della verifica a mano (ADR-049)."""
    import survival as SV
    from sec import cache_path                          # backtest/russell_exits/sec.py
    vecchie = [json.loads(r) for r in USCITA.open(encoding="utf-8") if r.strip()]
    b = C.budget()
    prima, rifatte = b.usate, 0
    nuove = []
    for v in vecchie:
        u = v.get("url")
        if v.get("esito") == "letto" and u and (cache_path(u).exists() or cache_path(u).with_suffix(".cache.gz").exists()):
            f = P.estrai(SV.testo(b.get(u)))
            v = {"cik": v["cik"], "url": u, "esito": "letto", "motivo_testo": P.motivo(f), **f}
            rifatte += 1
        nuove.append(v)
    tmp = USCITA.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in nuove), encoding="utf-8")
    tmp.replace(USCITA)
    print("ricalcolate {} righe su {} dalla cache; chiamate nuove {}".format(rifatte, len(vecchie), b.usate - prima))
    return 0


def main() -> int:
    import sys
    if sys.argv[1:2] == ["--da-cache"]:
        return ricalcola_da_cache()
    righe = [r for r in csv.DictReader((C.STATO / "universo.csv").open(encoding="utf-8")) if not r["motivo"]]
    fatti = set()
    if USCITA.exists():
        for riga in USCITA.open(encoding="utf-8"):
            if riga.strip():
                fatti.add(json.loads(riga)["cik"])
    b = C.budget()
    inizio = b.usate
    nuovi = 0
    with USCITA.open("a", encoding="utf-8") as fh:
        for r in righe:
            if r["cik"] in fatti:
                continue
            negate_prima = b.negate
            f, u = P.leggi(r["cik"], r["percorso_indice"])
            if f is None and b.negate > negate_prima:
                print("tetto raggiunto a {} chiamate: lettura ferma".format(b.usate), flush=True)
                break
            esito = "letto" if f else ("documento principale assente" if not u else "scaricamento fallito")
            campi = {k: v for k, v in (f or {}).items()}
            fh.write(json.dumps({"cik": r["cik"], "url": u, "esito": esito,
                                 "motivo_testo": P.motivo(f) if f else "", **campi}, ensure_ascii=False) + "\n")
            fh.flush()
            nuovi += 1
            if nuovi % 100 == 0:
                print("{} letti in questa corsa; chiamate EDGAR {} (totale {})".format(nuovi, b.usate - inizio, b.usate),
                      flush=True)
    print("fine: {} prospetti nuovi, {} chiamate in questa corsa, totale {} su {}".format(
        nuovi, b.usate - inizio, b.usate, C.TETTO), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
