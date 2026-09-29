"""Etichettare a mano, un documento alla volta.

    python -m edgar_llm.label --ciks lista.txt --per-form 5
    python -m edgar_llm.label --cik 216228 --accession 0000216228-26-000020

ESPORTA le finestre su file -- esattamente quelle che vedra' il modello, non il
documento intero -- e chiede i cinque campi. Chi etichetta deve poter vedere
cio' che il modello vedra', altrimenti misura la propria capacita' di leggere un
prospetto e non quella del modello di leggerne un estratto.

Il testo NON si stampa piu' nel terminale. Una finestra e' venti-quaranta mila
caratteri: in una console non si torna indietro, non si cerca, non si tiene il
segno. Si legge il file in un editor e si risponde qui a fianco.

Invio vuoto = `null`, che e' una risposta e non un rifiuto: «il documento non lo
dice» e' la verita' in molti casi ed e' cio' che il modello deve imparare a
rispondere. `?` salta il documento senza etichettarlo, `q` esce salvando quel
che si e' fatto.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import sessione as sess
from .edgar import EdgarClient
from .fetch import UnreadableDocument, document_text, windows
from .filings import offering_filings
from .goldens import STORE, append, load, make, sha_of
from .schema import CAMPI, TIPI

DOMANDE = {
    "tipo": "tipo, uno di: " + " | ".join(TIPI),
    "controparte": "controparte (underwriter, acquirente, agente)",
    "importo_usd": "importo lordo in dollari, solo cifre",
    "condizioni": "condizioni (milestone, lock-up, earnout, warrant)",
    "data_efficacia": "data di efficacia o prezzatura, YYYY-MM-DD",
}


def console_utf8() -> None:
    """La console deve poter stampare un prospetto, non solo l'ASCII.

    Su Windows lo standard output nasce in cp1252 e un filing qualunque lo fa
    esplodere: il primo documento della prima sessione conteneva U+202F, uno
    spazio stretto unificatore, e la CLI moriva con UnicodeEncodeError dopo
    aver gia' scaricato tutto. `errors="replace"` perche' un carattere che il
    terminale non sa disegnare deve diventare un punto interrogativo, non
    interrompere il lavoro di chi sta etichettando.
    """
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                      # noqa: BLE001
            pass


def chiedi(nome: str):
    """Il valore, o None. Solleva KeyboardInterrupt su 'q'."""
    while True:
        raw = input("    {}: ".format(DOMANDE[nome])).strip()
        if raw.lower() == "q":
            raise KeyboardInterrupt
        if raw == "":
            return None
        if nome == "tipo":
            if raw in TIPI:
                return raw
            #  Prefisso univoco: "m&" basta per M&A_issuance.
            cand = [t for t in TIPI if t.lower().startswith(raw.lower())]
            if len(cand) == 1:
                return cand[0]
            print("      -> non e' uno dei sette. Invio vuoto se non c'e'.")
            continue
        if nome == "importo_usd":
            try:
                return float(raw.replace(",", "").replace("$", "").replace(" ", ""))
            except ValueError:
                print("      -> serve un numero.")
                continue
        if nome == "data_efficacia":
            if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
                return raw
            print("      -> serve YYYY-MM-DD.")
            continue
        return raw


def read_ciks(spec: str) -> list[str]:
    testo = (sys.stdin if spec == "-" else Path(spec).open(encoding="utf-8")).read()
    seen, out = set(), []
    for c in testo.split():
        c = c.strip().lstrip("0")
        if c.isdigit() and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def bucket(f) -> str:
    return "8-K/2.01" if f.is_ma_8k else f.form


def candidati(client, ciks, per_form, since, gia_fatti, forme):
    """`per_form` depositi per ciascuna forma RICHIESTA, e nient'altro.

    La prima versione accettava qualsiasi forma incontrata e si fermava quando
    almeno quattro secchielli erano pieni. Su questo universo significava
    riempirsi di 424B2, 424B7 e FWP e fermarsi senza aver mai visto un 424B4:
    un campione scelto da cio' che capita prima non e' un campione.
    """
    presi = {nome: [] for nome in forme}
    for cik in ciks:
        if all(len(v) >= per_form for v in presi.values()):
            break
        for f in offering_filings(client, cik, since=since):
            b = bucket(f)
            if b not in presi or len(presi[b]) >= per_form:
                continue
            if "{}:{}".format(f.cik, f.accession) in gia_fatti:
                continue
            presi[b].append(f)

    #  Alternati per forma, non raggruppati: chi etichetta cento documenti non
    #  deve farne venti di fila della stessa specie, o comincia a rispondere a
    #  memoria invece che leggendo.
    fuori, i = [], 0
    while any(len(v) > i for v in presi.values()):
        for nome in forme:
            if len(presi[nome]) > i:
                fuori.append(presi[nome][i])
        i += 1
    return fuori, {k: len(v) for k, v in presi.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ciks", help="file con un CIK per riga, o '-'")
    ap.add_argument("--cik", help="un solo emittente")
    ap.add_argument("--accession", help="un solo deposito, con --cik")
    ap.add_argument("--per-form", type=int, default=5)
    ap.add_argument("--forms", default="424B5,424B3,424B4,8-K/2.01",
                    help="le forme da campionare, separate da virgola")
    ap.add_argument("--since", default="2025-01-01")
    ap.add_argument("--store", default=str(STORE))
    ap.add_argument("--seed", type=int, default=20260902,
                    help="mescola i CIK. L'ordine del file e' l'ordine di "
                         "scansione: prendere i primi e' un campione "
                         "sistematico, non casuale")
    ap.add_argument("--limit", type=int, default=0,
                    help="fermati dopo N documenti: una sessione si chiude, "
                         "non si abbandona")
    ap.add_argument("--out-dir", default=None,
                    help="dove esportare le finestre. Predefinito: una "
                         "directory di stato SOPRA il package, fuori dal "
                         "perimetro pubblico e ignorata da git")
    ap.add_argument("--preview", action="store_true",
                    help="mostra cosa verrebbe chiesto, senza chiedere niente")
    a = ap.parse_args(argv)
    console_utf8()
    forme = [x.strip() for x in a.forms.split(",") if x.strip()]

    client = EdgarClient()
    gia_fatti = {g.key for g in load(Path(a.store))}
    print("gia' etichettati: {}".format(len(gia_fatti)))

    if a.cik and a.accession:
        da_fare = [f for f in offering_filings(client, a.cik)
                   if f.accession == a.accession]
        if not da_fare:
            print("deposito non trovato fra quelli di emissione di CIK {}"
                  .format(a.cik))
            return 1
    elif a.ciks:
        import random

        lista = read_ciks(a.ciks)
        random.Random(a.seed).shuffle(lista)
        da_fare, conteggi = candidati(client, lista, a.per_form, a.since,
                                      gia_fatti, forme)
        print("campione (seed {}): {}".format(
            a.seed, "  ".join("{}={}".format(k, v)
                              for k, v in conteggi.items())))
        sotto = [k for k, v in conteggi.items() if v < a.per_form]
        if sotto:
            print("  SOTTO QUOTA: {} — l'universo non ne ha abbastanza "
                  "depositate dal {}".format(", ".join(sotto), a.since))
    else:
        ap.error("serve --ciks, oppure --cik con --accession")

    if a.limit:
        da_fare = da_fare[:a.limit]
    out_dir = sess.dir_sessione(a.out_dir)
    print("da etichettare: {}".format(len(da_fare)))
    print("finestre su file in: {}\n".format(out_dir))

    #  L'indice si riscrive a ogni cambio di stato, non alla fine: una sessione
    #  interrotta a meta' deve lasciare dietro di se' cosa era stato fatto.
    voci = []

    def aggiorna(pos, stato, note=""):
        voci[pos] = voci[pos][:4] + (stato, note)
        sess.scrivi_indice(out_dir, voci)

    fatti = 0
    try:
        for i, f in enumerate(da_fare, 1):
            ticker = sess.ticker_di(client, f.cik)
            voci.append((i, f, ticker, sess.nome_file(i, f, ticker),
                         sess.DA_FARE, ""))
            sess.scrivi_indice(out_dir, voci)
            pos = i - 1

            try:
                text = document_text(client, f)
            except UnreadableDocument as e:
                print("[{}/{}] {} {} — ILLEGGIBILE: {}".format(
                    i, len(da_fare), f.form, f.accession, e))
                aggiorna(pos, sess.ILLEGGIBILE, str(e)[:60])
                continue
            if not text:
                print("[{}/{}] {} {} — EDGAR non l'ha dato".format(
                    i, len(da_fare), f.form, f.accession))
                aggiorna(pos, sess.ILLEGGIBILE, "EDGAR non l'ha dato")
                continue
            sent = windows(text)

            nome = (client.submissions(f.cik) or {}).get("name") or ""
            p_doc = sess.esporta(i, f, ticker, nome, text, sent, out_dir)

            print("=" * 78)
            print("[{}/{}]  {}  {}  {}  {}".format(
                i, len(da_fare), f.form, ticker or "—", f.filed, f.accession))
            print("documento {:,} car. -> finestre {:,} car. ({:.1%})".format(
                len(text), len(sent), len(sent) / len(text)))
            print()
            #  Il percorso PRIMA della domanda, e non il testo: e' il punto di
            #  tutto questo. Venti pagine a scorrimento in una console non si
            #  leggono, si scremano, e le etichette che ne escono misurano la
            #  pazienza di chi le ha date.
            print("  LEGGI:  {}".format(p_doc))
            print("  EDGAR:  {}".format(f.url))
            print("=" * 78)
            print("  invio vuoto = null · '?' salta · 'q' esce salvando")

            if a.preview:
                #  La prova della CLI, non delle etichette: si guarda che il
                #  documento arrivi e che le finestre bastino a rispondere.
                #  Le etichette le mette una persona, o il golden set misura
                #  quanto il modello somiglia a chi l'ha scritto.
                print("  [preview] qui verrebbero chiesti: {}\n".format(
                    ", ".join(CAMPI)))
                continue
            if input("    etichettare questo? [S/?] ").strip().lower() == "?":
                aggiorna(pos, sess.SALTATO)
                continue
            labels = {c: chiedi(c) for c in CAMPI}
            nota = input("    nota (facoltativa): ").strip()
            append(make(f, text, labels, note=nota), Path(a.store))
            fatti += 1
            aggiorna(pos, sess.ETICHETTATO, nota[:60])
            print("    salvato. sha {}\n".format(sha_of(text)[:12]))
    except (KeyboardInterrupt, EOFError):
        print("\ninterrotto.")

    if voci:
        print("indice della sessione: {}".format(sess.scrivi_indice(out_dir, voci)))

    print("\netichettati in questa sessione: {}   totale: {}".format(
        fatti, len(load(Path(a.store)))))
    print("EDGAR: {:,} di rete, {:,} dalla cache".format(
        client.stats["network"], client.stats["cache"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
