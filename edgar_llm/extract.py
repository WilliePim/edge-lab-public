"""Da un deposito a un `OfferingEvent`. Il percorso completo, e le sue uscite.

    documento -> testo -> finestre -> [cache] -> modello -> validazione -> evento

QUATTRO MODI DI FALLIRE, TUTTI VERSO LO STESSO POSTO. EDGAR non da' il file, il
file non si converte in testo, l'API non risponde, la risposta non passa la
validazione: in ogni caso esce un evento con i campi vuoti e una nota che dice
quale dei quattro e' stato. Mai un valore inventato, mai un silenzio.

LA VALIDAZIONE NON STA IN CACHE. In cache va la risposta grezza del modello; la
validazione gira a ogni lettura. Cosi' una correzione al validatore vale subito
su tutto lo storico, senza ripagare una sola chiamata -- e le note di
declassamento restano allineate al codice che le ha prodotte, non a quello che
girava il giorno dell'estrazione.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .cache import Cache, CacheMiss, key_for
from .client import LLMClient, MissingApiKey, ModelUnavailable
from .fetch import UnreadableDocument, document_text, windows
from .schema import TOOL_NAME, TOOL_SCHEMA, Field, OfferingEvent, validate

log = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_VERSION = "v1"


def load_prompt(version: str = PROMPT_VERSION) -> str:
    p = PROMPT_DIR / "{}.md".format(version)
    if not p.exists():
        raise FileNotFoundError("prompt {} inesistente: {}".format(version, p))
    return p.read_text(encoding="utf-8")


def _empty(filing, note: str, prompt_version: str, model: str) -> OfferingEvent:
    """L'esito quando non c'e' niente da estrarre. Dichiarato, non silenzioso."""
    return OfferingEvent(
        issuer_cik=filing.cik, accession=filing.accession, form=filing.form,
        filed=filing.filed, source_url=filing.url,
        model=model, prompt_version=prompt_version,
        extracted_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        notes=(note,),
    )


def extract_filing(filing, edgar, llm: LLMClient | None = None,
                   cache: Cache | None = None,
                   prompt_version: str = PROMPT_VERSION) -> OfferingEvent:
    """Estrae da un deposito. Non alza mai: ogni guasto e' un evento con note."""
    llm = llm or LLMClient()
    cache = cache or Cache()
    model = llm.model

    try:
        text = document_text(edgar, filing)
    except UnreadableDocument as e:
        return _empty(filing, "documento illeggibile: {}".format(e)[:200],
                      prompt_version, model)
    if not text:
        return _empty(filing, "EDGAR non ha restituito il documento",
                      prompt_version, model)

    sent = windows(text)
    key = key_for(sent, prompt_version, model)

    try:
        cached = cache.get(key)
    except CacheMiss as e:
        return _empty(filing, str(e)[:200], prompt_version, model)

    if cached is not None:
        payload = cached.get("payload") or {}
        usage = cached.get("usage") or {}
    else:
        try:
            payload, usage = llm.extract(load_prompt(prompt_version), sent,
                                         TOOL_NAME, TOOL_SCHEMA)
        except (MissingApiKey, ModelUnavailable) as e:
            return _empty(filing, "{}: {}".format(type(e).__name__, e)[:200],
                          prompt_version, model)
        cache.put(key, {"payload": payload, "usage": usage, "model": model,
                        "prompt_version": prompt_version,
                        "source_url": filing.url,
                        "extracted_at": datetime.now(timezone.utc)
                        .isoformat(timespec="seconds")})

    campi, notes = validate(payload, sent)
    return OfferingEvent(
        issuer_cik=filing.cik, accession=filing.accession, form=filing.form,
        filed=filing.filed, source_url=filing.url,
        model=model, prompt_version=prompt_version,
        extracted_at=(cached or {}).get(
            "extracted_at",
            datetime.now(timezone.utc).isoformat(timespec="seconds")),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        notes=tuple(notes),
        **campi)


def latest_issuance(edgar, cik: str, since: str = "", until: str = "",
                    llm=None, cache=None,
                    prompt_version: str = PROMPT_VERSION) -> OfferingEvent | None:
    """L'estrazione sul deposito piu' recente in finestra. None se non ce n'e'.

    UN documento per emittente, non tutti: chi legge il report vuole sapere
    cos'e' l'ultima emissione, e ogni documento in piu' e' una chiamata in piu'
    per una riga che nessuno leggera'. Chi vuole la serie intera chiama
    `extract_filing` su `offering_filings`.
    """
    from .filings import offering_filings

    fs = offering_filings(edgar, cik, since=since, until=until)
    if not fs:
        return None
    return extract_filing(fs[0], edgar, llm=llm, cache=cache,
                          prompt_version=prompt_version)


def render(ev: OfferingEvent | None) -> str:
    """Cio' che finisce nella colonna del report. Solo materiale.

    Nessun aggettivo, nessun ordinamento, nessuna soglia: il tipo cosi' com'e'
    e la confidence che lo accompagna. Sotto la soglia di revisione non si
    scrive un tipo -- si scrive che non lo si sa.
    """
    if ev is None:
        return "—"
    f: Field = ev.tipo
    if not f.usable:
        return "UNKNOWN"
    return "{} ({})".format(f.value, f.confidence)
