"""Il golden set: cosa dice un umano che c'e' scritto nel documento.

IL REPO NON VERSIONA IL TESTO DEI FILING. Sono documenti pubblici, pesano
megabyte l'uno, e tenerli qui dentro renderebbe il package un archivio invece
che del codice. Ogni golden porta accession, URL e lo `sha256` del testo
estratto; `rehydrate` li riscarica da EDGAR su un clone pulito.

LO SHA E' UN CONTROLLO, NON UN'ETICHETTA. Se il testo che torna oggi non
combacia con quello su cui qualcuno ha etichettato, l'etichetta non vale piu':
il documento e' stato sostituito, o la conversione HTML->testo e' cambiata sotto
i piedi. In entrambi i casi va saputo, non aggirato — un golden set che si
adatta silenziosamente a cio' che il codice fa adesso non misura piu' niente.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .fetch import document_text
from .filings import Filing
from .schema import CAMPI

STORE = Path(__file__).resolve().parent / "goldens" / "labels.jsonl"


class GoldenChanged(RuntimeError):
    """Il documento non e' piu' quello su cui si era etichettato."""


@dataclass(frozen=True)
class Golden:
    cik: str
    accession: str
    form: str
    filed: str
    primary_document: str
    source_url: str
    text_sha256: str
    labels: dict = field(default_factory=dict)
    labelled_at: str = ""
    note: str = ""

    @property
    def filing(self) -> Filing:
        return Filing(cik=self.cik, accession=self.accession, form=self.form,
                      filed=self.filed, primary_document=self.primary_document)

    @property
    def key(self) -> str:
        return "{}:{}".format(self.cik, self.accession)


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def load(path: Path | None = None) -> list[Golden]:
    p = Path(path or STORE)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        out.append(Golden(**{k: v for k, v in d.items()
                             if k in Golden.__dataclass_fields__}))
    #  Append-only con l'ultima riga che vince: un'etichetta si corregge
    #  aggiungendo, non riscrivendo, cosi' la storia di cosa si e' pensato
    #  resta leggibile.
    per_chiave = {}
    for g in out:
        per_chiave[g.key] = g
    return list(per_chiave.values())


def append(g: Golden, path: Path | None = None) -> Path:
    p = Path(path or STORE)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "cik": g.cik, "accession": g.accession, "form": g.form,
            "filed": g.filed, "primary_document": g.primary_document,
            "source_url": g.source_url, "text_sha256": g.text_sha256,
            "labels": g.labels,
            "labelled_at": g.labelled_at or datetime.now(timezone.utc)
            .isoformat(timespec="seconds"),
            "note": g.note,
        }, ensure_ascii=False, sort_keys=True) + "\n")
    return p


def rehydrate(g: Golden, client, strict: bool = True) -> str:
    """Il testo del documento, verificato contro lo sha registrato."""
    text = document_text(client, g.filing)
    got = sha_of(text)
    if g.text_sha256 and got != g.text_sha256:
        msg = ("{} {}: il testo e' cambiato (sha {} != {}). L'etichetta e' "
               "stata data su un altro testo.".format(
                   g.form, g.accession, got[:12], g.text_sha256[:12]))
        if strict:
            raise GoldenChanged(msg)
    return text


def make(filing: Filing, text: str, labels: dict, note: str = "") -> Golden:
    ignoti = set(labels) - set(CAMPI)
    if ignoti:
        raise ValueError("campi fuori schema: {}".format(sorted(ignoti)))
    return Golden(cik=filing.cik, accession=filing.accession, form=filing.form,
                  filed=filing.filed,
                  primary_document=filing.primary_document,
                  source_url=filing.url, text_sha256=sha_of(text),
                  labels=labels, note=note,
                  labelled_at=datetime.now(timezone.utc)
                  .isoformat(timespec="seconds"))
