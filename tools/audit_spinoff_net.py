"""Quanto precisa e' la rete spin-off? Una misura sola, che non decide niente.

LA PIPELINE NON LEGGE CORPI. `RULES.md` §5 lo tiene come vincolo: la rete si
ferma al numero dell'exhibit (EX-99.1) e all'ancora sul prezzo, perche' la
descrizione degli exhibit -- «Information Statement», «Separation and
Distribution Agreement» -- **non esiste nei metadati EDGAR**. Campionata su sei
spin-off certi, sia nella tabella `-index.htm` sia nell'intestazione SGML, il
campo descrizione ripete il numero: `TYPE=EX-99.1  DESCRIPTION=EX-99.1`.

Quelle due frasi vivono nell'indice degli exhibit **dentro** il Form 10. Questo
strumento le va a cercare, una volta, per rispondere a una domanda che la
pipeline non puo' porsi: **quanti spin-off veri la rete a metadati sta
perdendo?**

    in entrambe        la rete+ancora e le stringhe concordano
    solo rete+ancora   la pipeline tiene, le stringhe no  -> falsi positivi?
    solo stringhe      le stringhe trovano, la pipeline no -> falsi negativi

**Criterio dichiarato prima del run:** se la rete+ancora perde piu' del **5%**
degli spin-off veri che le stringhe trovano, si ridiscute la rete. Sotto quella
soglia la pipeline resta a metadati e prezzi.

Non gira nel giro giornaliero, non scrive `data/spinoffs_index.json`, non filtra
niente. Scrive un report e basta.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from form4_scanner.edgar import EdgarClient

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "backfill"
CANDIDATES = STATE / "spinoff_candidates.jsonl"
ANCHORED = STATE / "spinoff_anchored.json"
OUT = ROOT / "reports" / "spinoff_net_audit.md"
CACHE = STATE / "spinoff_strings.json"

#  Le due frasi, cercate alla lettera e senza interpretazione. Lo spazio
#  flessibile copre l'a capo dentro una cella di tabella HTML.
INFO_STMT = re.compile(r"information\s+statement", re.I)
SEP_AGMT = re.compile(r"separation\s+and\s+distribution\s+agreement", re.I)
TAG = re.compile(r"<[^>]+>")


def primary_doc_url(client, cik, path):
    """L'URL del documento primario del deposito, dal suo index.json."""
    acc = path.split("/")[-1].replace(".txt", "")
    base = "https://www.sec.gov/Archives/edgar/data/{}/{}".format(
        cik, acc.replace("-", ""))
    idx = client.get_json(base + "/index.json")
    if not idx:
        return None
    items = (idx.get("directory") or {}).get("item") or []
    #  Il primario e' l'htm piu' grande che non sia l'index e non sia un
    #  exhibit: nei Form 10 e' sempre il documento con "1012b" o "form10" nel
    #  nome, ma il nome non e' garantito, quindi si prende per dimensione.
    cands = [it for it in items
             if it.get("name", "").endswith((".htm", ".html"))
             and "index" not in it.get("name", "")]
    if not cands:
        return None
    best = max(cands, key=lambda it: int(it.get("size") or 0))
    return base + "/" + best["name"]


def strings_in(client, cik, path):
    """(information statement?, separation agreement?) nel documento primario."""
    url = primary_doc_url(client, cik, path)
    if not url:
        return None
    html = client.get(url)
    if not html:
        return None
    text = TAG.sub(" ", html)
    return bool(INFO_STMT.search(text)), bool(SEP_AGMT.search(text))


def main() -> int:
    ua = " ".join(sys.argv[1:])
    if not ua:
        raise SystemExit('uso: audit_spinoff_net.py "Nome Cognome email@dominio"')
    client = EdgarClient(ua)

    raw = [json.loads(l) for l in CANDIDATES.read_text(encoding="utf-8").splitlines()]
    filings = {}
    for r in raw:
        if r["form"].startswith("10-12B"):
            filings.setdefault(r["cik"], []).append(r)

    anch = json.loads(ANCHORED.read_text(encoding="utf-8")) if ANCHORED.exists() else {}
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}

    #  L'ultimo deposito porta l'indice degli exhibit definitivo: uno per CIK,
    #  non tutti e novecento.
    for i, (cik, fl) in enumerate(sorted(filings.items())):
        if cik in cache:
            continue
        last = sorted(fl, key=lambda r: r["filed"])[-1]
        got = strings_in(client, cik, last["path"])
        cache[cik] = {"info": got[0], "sep": got[1]} if got else {"info": None,
                                                                  "sep": None}
        if i % 20 == 0:
            print("  {}/{}".format(i, len(filings)), flush=True)
            CACHE.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")

    both, only_pipe, only_str, neither, unread = [], [], [], [], []
    for cik in sorted(filings):
        c = cache.get(cik) or {}
        a = anch.get(cik) or {}
        name = a.get("name") or ""
        if c.get("info") is None:
            unread.append((cik, name))
            continue
        by_strings = bool(c["info"] and c["sep"])
        by_pipeline = bool(a.get("date_distribution"))
        if by_strings and by_pipeline:
            both.append((cik, name))
        elif by_pipeline:
            only_pipe.append((cik, name, a.get("drop_reason")))
        elif by_strings:
            only_str.append((cik, name, a.get("drop_reason")))
        else:
            neither.append((cik, name))

    denom = len(both) + len(only_str)
    lost = (100.0 * len(only_str) / denom) if denom else 0.0

    L = ["# Audit della rete spin-off", "",
         "Misura di precisione, non un filtro. La pipeline resta a metadati e",
         "prezzi qualunque cosa dica questa pagina: `RULES.md` §5.", "",
         "Le due stringhe sono cercate alla lettera nel documento primario",
         "dell'ultimo 10-12B(/A) di ogni CIK. Nessuna interpretazione.", "",
         "| | N |", "|---|---:|",
         "| in entrambe | {} |".format(len(both)),
         "| solo rete+ancora | {} |".format(len(only_pipe)),
         "| solo stringhe | {} |".format(len(only_str)),
         "| in nessuna delle due | {} |".format(len(neither)),
         "| documento non leggibile | {} |".format(len(unread)), "",
         "**Spin-off veri persi dalla rete a metadati: {}/{} = {:.1f}%** "
         "(criterio dichiarato: sopra il 5% si ridiscute la rete).".format(
             len(only_str), denom, lost), ""]

    if only_str:
        L += ["## Solo stringhe — la pipeline li perde", "",
              "| CIK | nome | motivo di caduta |", "|---|---|---|"]
        for cik, name, why in only_str[:40]:
            L.append("| {} | {} | {} |".format(cik, name[:44], why or "—"))
        L.append("")
    if only_pipe:
        L += ["## Solo rete+ancora — le stringhe non li trovano", "",
              "| CIK | nome |", "|---|---|"]
        for cik, name, _ in only_pipe[:40]:
            L.append("| {} | {} |".format(cik, name[:44]))
        L.append("")

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\nscritto {}".format(OUT))
    print("  in entrambe {}, solo pipeline {}, solo stringhe {}, "
          "nessuna {}, illeggibili {}".format(
              len(both), len(only_pipe), len(only_str), len(neither), len(unread)))
    print("  persi dalla rete: {:.1f}%".format(lost))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
