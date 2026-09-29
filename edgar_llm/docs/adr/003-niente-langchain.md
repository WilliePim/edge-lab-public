# ADR-003 — Nessun framework di orchestrazione

Data: 2026-09-02 · Stato: accettata

## Contesto

Richiesta esplicita nell'handoff: niente LangChain.

## Decisione

SDK `anthropic` diretto, dietro un'astrazione sottile in `client.py` che isola
il nome del modello, la chiave e il retry. Nient'altro.

## Alternative scartate

LangChain, LlamaIndex e simili. Questo modulo fa una cosa sola: un documento,
una chiamata, uno schema. Non c'e' catena, non c'e' agente, non c'e' retrieval.
Un framework qui aggiungerebbe superficie e nasconderebbe l'unica cosa che
questo package vuole mostrare, cioe' com'e' fatta la chiamata.

## Conseguenze

Retry, timeout e conteggio dei token sono codice nostro. E' il costo accettato.
