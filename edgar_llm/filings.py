"""Quali depositi contano, e dove sta il loro documento primario.

Il nome del file da scaricare non va indovinato dall'`index.json` della
cartella: le submissions lo dichiarano gia' in `primaryDocument`, insieme alla
forma, alla data e -- per gli 8-K -- agli item. Un deposito costa quindi UNA
sola richiesta di rete, e la selezione del documento non e' un'euristica.

Nessuna lista di emittenti vive qui. I CIK arrivano sempre da chi chiama: una
lista predefinita, in un package pubblico, sarebbe una selezione di qualcuno
-- cioe' esattamente il genere di cosa che non si pubblica.
"""

from __future__ import annotations

from dataclasses import dataclass

from .edgar import SUBMISSIONS, document_url

#  Supplementi di prospetto: il prelievo vero da uno scaffale.
TAKEDOWN_FORMS = frozenset({
    "424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8", "FWP",
})
#  Registrazioni: l'intenzione, non il prelievo.
SHELF_FORMS = frozenset({"S-1", "S-1/A", "S-3", "S-3/A", "S-3ASR", "S-3MEF", "S-1MEF"})
#  8-K item 2.01 = completamento di un'acquisizione o cessione. E' l'item che
#  distingue un aumento di azioni da M&A da un'emissione diluitiva -- il caso
#  che ha motivato questo modulo.
MA_ITEM = "2.01"


@dataclass(frozen=True)
class Filing:
    cik: str
    accession: str
    form: str
    filed: str                 # ISO
    primary_document: str
    items: str = ""            # solo 8-K, come "1.01,2.01,7.01"
    size: int = 0

    @property
    def url(self) -> str:
        return document_url(self.cik, self.accession, self.primary_document)

    @property
    def is_ma_8k(self) -> bool:
        return self.form == "8-K" and MA_ITEM in (self.items or "")


def _absorb(cik, block, out):
    forms = block.get("form", [])

    def col(name):
        v = block.get(name) or []
        return v if len(v) == len(forms) else [""] * len(forms)

    accs, dates = col("accessionNumber"), col("filingDate")
    docs, items, sizes = col("primaryDocument"), col("items"), col("size")
    for i, form in enumerate(forms):
        out.append(Filing(
            cik=str(cik), accession=accs[i], form=str(form or "").strip().upper(),
            filed=dates[i], primary_document=docs[i], items=items[i] or "",
            size=int(sizes[i] or 0) if str(sizes[i]).isdigit() else 0,
        ))


def all_filings(client, cik: str) -> list[Filing]:
    """Ogni deposito di un CIK, shard compresi.

    `filings.recent` tronca la storia a qualche centinaio di righe; il resto sta
    negli shard elencati in `filings.files`. Leggere solo `recent` perde in
    silenzio tutto cio' che sta prima, e su un filer vecchio e' quasi tutto.
    """
    subs = client.submissions(cik)
    if not subs:
        return []
    filings = subs.get("filings") or {}
    out: list[Filing] = []
    _absorb(cik, filings.get("recent") or {}, out)
    for extra in filings.get("files") or []:
        name = (extra or {}).get("name")
        if not name:
            continue
        shard = client.get_json("{}/{}".format(SUBMISSIONS, name))
        if shard:
            _absorb(cik, shard, out)
    return out


def offering_filings(client, cik: str, since: str = "", until: str = "",
                     include_shelves: bool = False) -> list[Filing]:
    """I depositi che possono spiegare un'emissione, dal piu' recente.

    `until` esiste per il point-in-time: un backfill non deve mai vedere un
    deposito successivo alla data che sta valutando.
    """
    keep = []
    for f in all_filings(client, cik):
        if not f.filed or not f.primary_document:
            continue
        if since and f.filed < since:
            continue
        if until and f.filed > until:
            continue
        if f.form in TAKEDOWN_FORMS or f.is_ma_8k or (
                include_shelves and f.form in SHELF_FORMS):
            keep.append(f)
    return sorted(keep, key=lambda f: f.filed, reverse=True)
