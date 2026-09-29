"""Quanto testo c'e' davvero dentro un deposito, e quanto ne resta dopo il taglio.

Il Passo 0 del piano: nessuna stima di costo entra in un documento prima di
questa tabella. La dimensione che le submissions dichiarano e' quella della
SUBMISSION COMPLETA -- exhibit, grafica e XBRL inclusi -- e non dice niente su
quanti caratteri di prosa contiene il documento primario.

I CIK arrivano da fuori, uno per riga, da un file o da stdin. Nessuna lista
vive in questo package.

    python -m edgar_llm.tools.measure_docs --ciks - --per-form 5 < ciks.txt
"""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import defaultdict
from pathlib import Path

from ..edgar import EdgarClient
from ..fetch import UnreadableDocument, to_text, windows
from ..filings import offering_filings

#  Rapporto caratteri/token per prosa inglese, usato solo per dare un ordine di
#  grandezza. E' un'approssimazione dichiarata, non una misura.
CHARS_PER_TOKEN = 4.0

#  Listino per milione di token, da riga di comando perche' cambia e il codice
#  non deve essere la fonte di verita' su un prezzo.
DEFAULT_IN_PER_MTOK = 3.0
DEFAULT_OUT_PER_MTOK = 15.0
#  Un'estrazione restituisce cinque campi con citazione: qualche centinaio di
#  token. Misurato per davvero solo dopo la prima corsa vera.
ASSUMED_OUT_TOKENS = 400

BUCKETS = ("424B5", "424B3", "424B4", "8-K/2.01")


def bucket_of(f):
    if f.is_ma_8k:
        return "8-K/2.01"
    return f.form if f.form in BUCKETS else None


def read_ciks(spec: str) -> list[str]:
    lines = (sys.stdin if spec == "-" else Path(spec).open(encoding="utf-8")).read().split()
    seen, out = set(), []
    for c in lines:
        c = c.strip().lstrip("0")
        if c.isdigit() and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ciks", required=True, help="file con un CIK per riga, o '-'")
    ap.add_argument("--per-form", type=int, default=5)
    ap.add_argument("--since", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--in-price", type=float, default=DEFAULT_IN_PER_MTOK,
                    help="$ per milione di token di input")
    ap.add_argument("--out-price", type=float, default=DEFAULT_OUT_PER_MTOK,
                    help="$ per milione di token di output")
    ap.add_argument("--per-day", type=int, default=0,
                    help="documenti attesi al giorno, per la riga del costo marginale")
    ap.add_argument("--backfill", type=int, default=0,
                    help="documenti del backfill una tantum")
    a = ap.parse_args(argv)

    client = EdgarClient()
    picked = defaultdict(list)
    for cik in read_ciks(a.ciks):
        if all(len(picked[b]) >= a.per_form for b in BUCKETS):
            break
        for f in offering_filings(client, cik, since=a.since):
            b = bucket_of(f)
            if b and len(picked[b]) < a.per_form:
                picked[b].append(f)

    rows, unreadable = [], []
    for b in BUCKETS:
        for f in picked[b]:
            raw = client.get(f.url) or ""
            try:
                text = to_text(raw)
            except UnreadableDocument as e:
                unreadable.append((b, f, str(e)[:60]))
                print("  {:<10} {} ILLEGGIBILE  {}".format(b, f.filed, e),
                      flush=True)
                continue
            win = windows(text)
            rows.append((b, f, len(raw), len(text), len(win)))
            print("  {:<10} {} {:>9,}B raw {:>9,} testo {:>8,} finestre  {}".format(
                b, f.filed, len(raw), len(text), len(win), f.primary_document),
                flush=True)

    L = ["# Costi — misura del documento primario", "",
         "Generato da `python -m edgar_llm.tools.measure_docs`. Il campione e' "
         "di {} depositi, {} per forma.".format(len(rows), a.per_form), "",
         "`raw` e' il file scaricato, `testo` cio' che resta dopo HTML->testo, "
         "`finestre` cio' che finisce davvero nel prompt.", "",
         "| forma | n | testo mediano | finestre mediane | token stimati | resa |",
         "|---|---:|---:|---:|---:|---:|"]
    tot_win = []
    for b in BUCKETS:
        sel = [r for r in rows if r[0] == b]
        if not sel:
            continue
        t = statistics.median(r[3] for r in sel)
        w = statistics.median(r[4] for r in sel)
        tot_win += [r[4] for r in sel]
        L.append("| {} | {} | {:,.0f} car. | {:,.0f} car. | ~{:,.0f} | {:.0%} |".format(
            b, len(sel), t, w, w / CHARS_PER_TOKEN, (w / t) if t else 0))
    if tot_win:
        med = statistics.median(tot_win)
        tok_in = med / CHARS_PER_TOKEN
        unit = (tok_in * a.in_price + ASSUMED_OUT_TOKENS * a.out_price) / 1e6
        L += ["", "Mediana complessiva delle finestre: **{:,.0f} caratteri**, "
              "~**{:,.0f} token** di input a {:.0f} car./token.".format(
                  med, tok_in, CHARS_PER_TOKEN), "",
              "## Costo", "",
              "A ${:.2f}/Mtok di input e ${:.2f}/Mtok di output, con {} token "
              "di output assunti per estrazione (**assunto, non misurato**: lo "
              "diventa dopo la prima corsa vera).".format(
                  a.in_price, a.out_price, ASSUMED_OUT_TOKENS), "",
              "| | documenti | costo |", "|---|---:|---:|",
              "| per documento | 1 | **${:.4f}** |".format(unit),
              "| per 1.000 filing | 1.000 | **${:,.2f}** |".format(unit * 1000)]
        if a.per_day:
            L.append("| al giorno | {:,} | ${:,.2f} |".format(
                a.per_day, unit * a.per_day))
        if a.backfill:
            L.append("| backfill una tantum | {:,} | ${:,.2f} |".format(
                a.backfill, unit * a.backfill))
        L += ["", "La cache rende il costo NON ricorrente: un documento si paga "
              "una volta per (prompt, modello). Il costo al giorno e' quindi un "
              "tetto, non una rendita.", ""]
    if unreadable:
        L += ["", "**{} documenti illeggibili** su {}:".format(
            len(unreadable), len(rows) + len(unreadable)), ""]
        L += ["- `{}` {} — {}".format(b, f.primary_document, why)
              for b, f, why in unreadable]
        L += [""]
    L += ["", "## Limiti", "",
          "1. **La resa non e' uniforme.** Un 8-K entra quasi intero; un 424B3 "
          "che veicola un prospetto di fusione da 1,7 milioni di caratteri "
          "entra all'1%. La copertina e sei finestre bastano su un supplemento "
          "di prospetto e non e' detto che bastino li'. E' la prima cosa che "
          "le evals devono misurare, per forma.",
          "2. **`token stimati` non e' un conteggio**: e' caratteri diviso "
          "{:.0f}. Il numero vero arriva dagli `usage` della prima corsa.".format(
              CHARS_PER_TOKEN),
          "3. **Il campione e' di {} depositi.** Serve a dimensionare, non a "
          "descrivere la popolazione.".format(a.per_form * len(BUCKETS)),
          "4. **I prezzi sono argomenti di riga di comando**, non un fatto "
          "misurato: se il listino cambia, cambia la riga di comando.", "",
          "EDGAR: {:,} chiamate di rete, {:,} dalla cache.".format(
              client.stats["network"], client.stats["cache"]), ""]

    text = "\n".join(L)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
        print("\nscritto {}".format(a.out))
    else:
        print("\n" + text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
