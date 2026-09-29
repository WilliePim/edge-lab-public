"""Lo schema di un'estrazione, e la validazione di cio' che torna.

TRE COSE CHE QUESTO FILE FA E CHE UN VALIDATORE GENERICO NON FAREBBE.

1. **Fail-closed.** Un campo che non si e' potuto leggere vale `None` con
   confidence `low` e una nota che dice perche'. Non esiste il caso «campo
   assente quindi va bene»: l'assenza e' un esito, e va scritta.

2. **La citazione deve esistere.** `source_excerpt` viene cercato
   LETTERALMENTE nel testo che e' stato mandato al modello, a spazi
   normalizzati. Se non c'e', il campo scende a `low` e la nota lo dice. Un
   modello che cita cio' che non ha letto e' il modo tipico in cui
   un'estrazione sbagliata sembra sicura di se'.

3. **Nessun giudizio.** I sette tipi sono categorie di evento, non gradi di
   merito, e non c'e' nulla in questo file che li ordini o li pesi.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

#  I sette tipi dell'handoff, piu' l'esito che non e' un tipo.
TIPI = (
    "ATM",                  # at-the-market: vendita continua sul mercato
    "secondary_offering",   # collocamento secondario, underwritten
    "IPO",                  # prima quotazione
    "M&A_issuance",         # azioni emesse come corrispettivo di un'acquisizione
    "shelf_registration",   # registrazione di uno scaffale, senza prelievo
    "PIPE",                 # collocamento privato a investitori qualificati
    "other",
)
UNKNOWN = "UNKNOWN"

CONFIDENCES = ("high", "medium", "low")
CAMPI = ("tipo", "controparte", "importo_usd", "condizioni", "data_efficacia")

#  Sotto questa soglia il campo va in coda di revisione invece di popolare
#  qualcosa. Non e' una soglia di merito: e' il confine fra "letto" e "non
#  letto", e vale per tutti i campi allo stesso modo.
SOGLIA_REVISIONE = "medium"

_WS = re.compile(r"\s+")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#  Una citazione piu' corta di cosi' combacia con qualsiasi cosa e non prova
#  niente: "the" si trova in ogni prospetto del mondo.
MIN_EXCERPT = 12


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "")).strip().lower()


@dataclass(frozen=True)
class Field:
    """Un campo estratto, con cio' che lo giustifica.

    `source_url` non sta qui ma sull'evento: i cinque campi escono tutti dallo
    stesso documento, e ripeterlo cinque volte direbbe che potrebbero venire da
    documenti diversi, che e' falso.
    """

    value: object = None
    confidence: str = "low"
    source_excerpt: str = ""
    note: str = ""

    @property
    def known(self) -> bool:
        return self.value not in (None, "", UNKNOWN)

    @property
    def usable(self) -> bool:
        """Sopra la soglia di revisione. Sotto: coda, mai auto-popolamento."""
        return self.known and CONFIDENCES.index(self.confidence) <= CONFIDENCES.index(
            SOGLIA_REVISIONE)


@dataclass(frozen=True)
class OfferingEvent:
    issuer_cik: str
    accession: str
    form: str
    filed: str
    source_url: str

    tipo: Field = field(default_factory=Field)
    controparte: Field = field(default_factory=Field)
    importo_usd: Field = field(default_factory=Field)
    condizioni: Field = field(default_factory=Field)
    data_efficacia: Field = field(default_factory=Field)

    model: str = ""
    prompt_version: str = ""
    extracted_at: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    #  Perche' un campo e' finito dov'e' finito. Serve a chi rilegge, e alle
    #  evals per separare "il modello ha sbagliato" da "l'abbiamo declassato noi".
    notes: tuple = ()

    @property
    def tipo_value(self) -> str:
        return self.tipo.value if self.tipo.usable else UNKNOWN

    def as_dict(self) -> dict:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "OfferingEvent":
        kw = dict(d)
        kw["notes"] = tuple(d.get("notes") or ())
        for c in CAMPI:
            kw[c] = Field(**(d.get(c) or {}))
        return cls(**{k: v for k, v in kw.items()
                      if k in cls.__dataclass_fields__})


# ------------------------------------------------------ schema per il tool --
def _campo(descrizione: str, tipo_valore: dict) -> dict:
    return {
        "type": "object",
        "description": descrizione,
        "properties": {
            "value": tipo_valore,
            "confidence": {"type": "string", "enum": list(CONFIDENCES)},
            "source_excerpt": {
                "type": "string",
                "description": "Citazione LETTERALE dal testo fornito, almeno "
                               "{} caratteri, copiata parola per parola. Se il "
                               "campo non e' determinabile, stringa vuota."
                               .format(MIN_EXCERPT),
            },
        },
        "required": ["value", "confidence", "source_excerpt"],
    }


TOOL_NAME = "registra_evento_di_emissione"

TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "tipo": _campo(
            "Che genere di evento e'. `M&A_issuance` solo se le azioni sono il "
            "corrispettivo di un'acquisizione. `shelf_registration` se il "
            "documento registra soltanto, senza prelevare. `ATM` se la vendita "
            "e' continua e a prezzo di mercato.",
            {"type": ["string", "null"], "enum": list(TIPI) + [None]}),
        "controparte": _campo(
            "Underwriter, acquirente o agente di collocamento. null se assente.",
            {"type": ["string", "null"]}),
        "importo_usd": _campo(
            "Importo lordo in dollari, come numero. null se il documento non lo "
            "dice. Non stimare: se c'e' solo un massimo di scaffale, e' quello.",
            {"type": ["number", "null"]}),
        "condizioni": _campo(
            "Milestone, lock-up, earnout, warrant: una sintesi breve e "
            "descrittiva. null se non ce ne sono.",
            {"type": ["string", "null"]}),
        "data_efficacia": _campo(
            "Data di efficacia o di prezzatura, ISO YYYY-MM-DD. null se assente.",
            {"type": ["string", "null"]}),
    },
    "required": list(CAMPI),
}


# ------------------------------------------------------------ validazione --
def _coerce(nome, raw):
    """(valore, nota). Nessuna eccezione: un valore illeggibile e' None."""
    if raw is None:
        return None, ""
    if nome == "tipo":
        v = str(raw).strip()
        if v not in TIPI:
            return None, "tipo fuori dall'enumerazione: {!r}".format(v)[:120]
        return v, ""
    if nome == "importo_usd":
        try:
            return float(str(raw).replace(",", "").replace("$", "").strip()), ""
        except (TypeError, ValueError):
            return None, "importo non numerico: {!r}".format(raw)[:120]
    if nome == "data_efficacia":
        v = str(raw).strip()[:10]
        if not _ISO.match(v):
            return None, "data non ISO: {!r}".format(raw)[:120]
        try:
            date.fromisoformat(v)
        except ValueError:
            return None, "data inesistente: {!r}".format(raw)[:120]
        return v, ""
    v = str(raw).strip()
    return (v or None), ""


def validate(payload: dict, sent_text: str) -> tuple[dict, list]:
    """Da cio' che ha risposto il modello a cinque `Field` e le note.

    `sent_text` e' il testo REALMENTE mandato -- le finestre, non il documento
    intero -- perche' e' l'unica cosa che il modello ha potuto leggere. Cercare
    la citazione nel documento completo perdonerebbe proprio l'errore che qui
    interessa: una citazione presa da una parte che non era nel prompt.
    """
    payload = payload or {}
    haystack = _norm(sent_text)
    campi, notes = {}, []

    for nome in CAMPI:
        blob = payload.get(nome)
        if not isinstance(blob, dict):
            campi[nome] = Field(note="campo assente nella risposta")
            notes.append("{}: assente".format(nome))
            continue

        value, nota = _coerce(nome, blob.get("value"))
        if nota:
            notes.append("{}: {}".format(nome, nota))

        conf = str(blob.get("confidence") or "").strip().lower()
        if conf not in CONFIDENCES:
            notes.append("{}: confidence non valida ({!r}) -> low".format(nome, conf))
            conf = "low"

        excerpt = str(blob.get("source_excerpt") or "").strip()
        if value is not None:
            if len(excerpt) < MIN_EXCERPT:
                nota = "citazione troppo corta ({} car.)".format(len(excerpt))
                notes.append("{}: {} -> low".format(nome, nota))
                conf = "low"
            elif _norm(excerpt) not in haystack:
                #  Il caso che giustifica tutto questo file.
                nota = "citazione non presente nel testo inviato"
                notes.append("{}: {} -> low".format(nome, nota))
                conf = "low"

        campi[nome] = Field(value=value, confidence=conf,
                            source_excerpt=excerpt, note=nota)

    return campi, notes
