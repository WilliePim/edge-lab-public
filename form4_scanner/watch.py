"""Sorveglianza di nomi specifici, fuori dall'universo dello scanner.

Lo scanner spazza una FASCIA (50M-2e9) e non sa niente dei nomi. Qui e'
l'opposto: pochi emittenti scelti dall'utente, guardati per un evento preciso.
Sono due domande diverse e vivono in due posti diversi.

LA LISTA ARRIVA SEMPRE DA `config/watch.json`, MAI DAL CODICE. Un elenco di
titoli scritto dentro un sorgente e' esso stesso la cosa da non pubblicare, ed
e' la stessa regola che vale per la lista di esclusione del perimetro pubblico.

DUE GENERI DI SORVEGLIANZA.

`filings` -- compare un deposito di una certa forma. Riporta forma, data,
    numero di protocollo e link, e nient'altro.

    ATTENZIONE, ED E' SCRITTO ANCHE NEL REPORT: la forma NON dice se una
    registrazione e' di rivendita o di emissione primaria. Un S-3 copre
    entrambe e la differenza sta nel testo del documento, che questo modulo non
    apre. L'alert dice «e' comparso un S-3», non «e' comparsa una rivendita».
    Chiamarla rivendita sarebbe un giudizio, e i giudizi non stanno qui.

`form4_buys` -- acquisti di mercato aperto su un emittente, con un filtro di
    ruolo. «Management» significa director oppure officer E NON 10% owner: e' un
    test sui campi del deposito, non una lista di nomi, quindi regge quando il
    fondo di turno cambia.

    Il caso tipico: tutti gli acquisti di mercato aperto di un anno vengono da
    un fondo che deposita con piu' co-firmatari (le stesse transazioni riportate
    piu' volte, quindi l'importo va contato una volta sola) e il management non
    ha comprato. Il filtro per ruolo li esclude senza nominarli, e continuerebbe
    a escluderli se domani il fondo cambiasse nome.

Il deposito gia' visto non si ripete: `state/watch/seen.jsonl` tiene le coppie
(sorveglianza, protocollo). La finestra guarda indietro di piu' di un giorno
apposta, cosi' un giro saltato non perde un alert.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path

from .edgar import ARCHIVES, submission_rows
from .parse import open_market_buys, parse_ownership_xml

log = logging.getLogger(__name__)

DEFAULT_CONFIG = "config/watch.json"

#  Si guarda indietro piu' di un giorno: se il giro delle 8:00 non parte, o
#  l'indice non si legge, l'alert non evapora.
DEFAULT_LOOKBACK_DAYS = 30

KINDS = ("filings", "form4_buys")


@dataclass(frozen=True, slots=True)
class Watch:
    id: str
    cik: str
    ticker: str
    name: str
    kind: str
    forms: tuple = ()
    roles: str = "any"          # "management" | "any"
    min_value: float = 0.0
    note: str = ""
    #  Per sorveglianza, cosi' si puo' allargare la finestra su un nome senza
    #  allargarla su tutti. Il default viene dal file, non da qui.
    lookback_days: int = DEFAULT_LOOKBACK_DAYS


@dataclass(frozen=True, slots=True)
class Hit:
    watch_id: str
    cik: str
    ticker: str
    name: str
    kind: str
    form: str
    filed: str
    accession: str
    url: str
    detail: str = ""


def _url(cik: str, accession: str) -> str:
    acc = accession.replace("-", "")
    return f"{ARCHIVES}/edgar/data/{int(cik)}/{acc}/{accession}-index.htm"


def load_watches(path: str | Path = DEFAULT_CONFIG) -> list:
    """Le sorveglianze dichiarate. File assente = nessuna, non un errore."""
    p = Path(path)
    if not p.exists():
        return []
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        log.warning("watch: %s illeggibile (%s)", p, exc)
        return []

    #  Un default di file, sovrascrivibile per singola sorveglianza.
    fallback = int(doc.get("lookback_days") or DEFAULT_LOOKBACK_DAYS)

    out = []
    for w in doc.get("watches") or []:
        kind = str(w.get("kind") or "").strip()
        if kind not in KINDS:
            log.warning("watch: genere sconosciuto %r, saltata", kind)
            continue
        cik = str(w.get("cik") or "").strip()
        if not cik:
            continue
        out.append(
            Watch(
                id=str(w.get("id") or cik),
                cik=cik,
                ticker=str(w.get("ticker") or ""),
                name=str(w.get("name") or ""),
                kind=kind,
                forms=tuple(str(f).strip().upper() for f in (w.get("forms") or ())),
                roles=str(w.get("roles") or "any"),
                min_value=float(w.get("min_value") or 0.0),
                note=str(w.get("note") or ""),
                lookback_days=int(w.get("lookback_days") or fallback),
            )
        )
    return out


def _ledger(state_dir) -> Path:
    return Path(state_dir) / "watch" / "seen.jsonl"


def load_seen(state_dir) -> set:
    p = _ledger(state_dir)
    if not p.exists():
        return set()
    out = set()
    for line in p.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        out.add((d.get("watch_id"), d.get("accession")))
    return out


def record_seen(state_dir, hits: list, run_date: date) -> None:
    if not hits:
        return
    p = _ledger(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for h in hits:
            fh.write(
                json.dumps(
                    {
                        "watch_id": h.watch_id,
                        "accession": h.accession,
                        "form": h.form,
                        "filed": h.filed,
                        "first_seen": run_date.isoformat(),
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def check_filings(client, w: Watch, since: str) -> list:
    """I depositi della forma cercata, dalla data indicata in poi."""
    rows = submission_rows(client, w.cik)
    wanted = set(w.forms)
    out = []
    for r in rows:
        form, filed, acc = r.get("form", ""), r.get("filed", ""), r.get("accession", "")
        if not acc or not filed or filed < since:
            continue
        if wanted and form not in wanted:
            continue
        out.append(
            Hit(
                watch_id=w.id,
                cik=w.cik,
                ticker=w.ticker,
                name=w.name,
                kind=w.kind,
                form=form,
                filed=filed,
                accession=acc,
                url=_url(w.cik, acc),
            )
        )
    return out


def _is_management(t) -> bool:
    """Director o officer, e NON 10% owner. Tre condizioni, non una."""
    return (t.is_director or t.is_officer) and not t.is_ten_pct


def check_form4_buys(client, w: Watch, since: str) -> list:
    """Acquisti di mercato aperto sull'emittente, filtrati per ruolo."""
    rows = submission_rows(client, w.cik)
    out = []
    for r in rows:
        if r.get("form", "") != "4":
            continue
        filed, acc = r.get("filed", ""), r.get("accession", "")
        if not acc or not filed or filed < since:
            continue

        xml = client.ownership_xml(w.cik, acc)
        if not xml:
            continue
        try:
            filed_at = date.fromisoformat(filed)
        except ValueError:
            filed_at = None
        txns = parse_ownership_xml(xml, accession=acc, filed_at=filed_at)
        buys = open_market_buys(txns, min_value=w.min_value)
        if w.roles == "management":
            buys = [t for t in buys if _is_management(t)]
        if not buys:
            continue

        #  Una riga per deposito, con dentro chi ha comprato e quanto. Il
        #  deposito e' l'unita' che si puo' aver gia' visto.
        who = "; ".join(
            "{} ({}) {:,.0f} az. a ${:,.2f} = ${:,.0f}".format(
                t.owner_name, t.role, t.shares, t.price, t.value
            )
            for t in buys
        )
        out.append(
            Hit(
                watch_id=w.id,
                cik=w.cik,
                ticker=w.ticker,
                name=w.name,
                kind=w.kind,
                form="4",
                filed=filed,
                accession=acc,
                url=_url(w.cik, acc),
                detail=who,
            )
        )
    return out


def run(client, watches: list, run_date: date, state_dir,
        lookback_days: int | None = None) -> list:
    """Tutte le sorveglianze, senza i depositi gia' segnalati.

    La finestra e' per sorveglianza (dal file); `lookback_days` la forza tutta,
    e serve alle prove. NON si legge un default di modulo dentro la firma: in
    Python quel valore si fissa alla definizione della funzione, e cambiarlo
    dopo l'import non ha effetto -- un modo silenzioso di non provare niente.
    """
    if not watches:
        return []
    seen = load_seen(state_dir)

    fresh = []
    for w in watches:
        days = lookback_days if lookback_days is not None else w.lookback_days
        since = (run_date - timedelta(days=days)).isoformat()
        try:
            hits = (
                check_filings(client, w, since)
                if w.kind == "filings"
                else check_form4_buys(client, w, since)
            )
        except Exception as exc:                      # noqa: BLE001
            #  Una sorveglianza che esplode non deve portarsi via il giro: il
            #  report principale vale piu' dell'alert.
            log.warning("watch %s: %s", w.id, exc)
            continue
        fresh.extend(h for h in hits if (h.watch_id, h.accession) not in seen)

    fresh.sort(key=lambda h: (h.filed, h.watch_id), reverse=True)
    return fresh


def render(hits: list, watches: list) -> list:
    """Le righe markdown della sezione. Vuota se non e' successo niente."""
    if not hits:
        return []
    by_note = {w.id: w for w in watches}

    L = ["## Sorveglianza", ""]
    L.append(
        "Nomi seguiti singolarmente, fuori dall'universo dello scanner. "
        "La forma di un deposito **non dice** se una registrazione e' di "
        "rivendita o di emissione primaria: quella distinzione sta nel testo, "
        "che questa sezione non apre."
    )
    L.append("")
    L.append("| data | ticker | forma | sorveglianza | deposito |")
    L.append("|---|---|---|---|---|")
    for h in hits:
        w = by_note.get(h.watch_id)
        note = (w.note if w else "") or h.watch_id
        L.append(
            "| {} | {} | `{}` | {} | [{}]({}) |".format(
                h.filed, h.ticker or h.cik, h.form, note, h.accession, h.url
            )
        )
    L.append("")
    for h in hits:
        if h.detail:
            L.append("**{} {}** — {}".format(h.ticker or h.cik, h.filed, h.detail))
            L.append("")
    return L
