# ADR-002 — dataclass frozen e JSON-Schema a mano, non pydantic

Data: 2026-09-02 · Stato: accettata

## Contesto

Structured output con un LLM e' idiomaticamente pydantic. `CLAUDE.md` dice
«Dataclass frozen + JSONL. No pydantic, no database», e pydantic non e'
installato in questo repo.

## Decisione

`OfferingEvent` e' una dataclass frozen. Lo schema per il tool-use e' un dict
JSON-Schema scritto a mano in `schema.py`, con validazione esplicita al ritorno.

## Alternative scartate

- **pydantic solo dentro `edgar_llm/`**: due convenzioni nello stesso repo, per
  un guadagno che e' quasi solo di apparenza.
- **pydantic ovunque**: riapre una decisione presa, e non e' questo lavoro a
  doverla riaprire.

Il punto che ha deciso: lo schema JSON per il tool-use va comunque scritto o
generato, e la validazione al ritorno e' una trentina di righe. pydantic
risparmierebbe quelle trenta righe al prezzo di una dipendenza e di un vincolo
infranto.

## Conseguenze

La validazione e' codice nostro e va testata come tale — inclusa la verifica che
`source_excerpt` compaia **letteralmente** nel testo inviato, che pydantic non
avrebbe fatto comunque.
