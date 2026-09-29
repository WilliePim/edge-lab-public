# ADR 001 — Struttura di market-data e scelte dello scaffolding

**Data:** 2026-09-17 · **Stato:** accettata

## Contesto

Direttiva dell'utente del 17 settembre: package nuovo e indipendente `market-data` nel repo che allora lo ospitava,
archivio EODHD fuori dal repo, accesso solo tramite `market_data.api`, schema logico
`packages/market-data/src/market_data/...` con l'indicazione di adattare nomi e cartelle alle convenzioni esistenti.

## Decisioni e motivi

1. **`market-data/market_data/`, non `packages/market-data/src/market_data/`.** Il repo ospite teneva i sottoprogetti
   come cartelle sorelle in cima, con il package subito dentro e i test in `<progetto>/tests/`; il README diceva «zero
   packaging» e `conftest.py` metteva i path a posto. `market-data/tests/` ha un suo `conftest.py` che fa lo stesso,
   così il package si testa anche da solo.
2. **Nomi dei moduli come nello schema** (`config.py`, `eodhd/client.py`, `store/raw.py`, …, `api.py`); commenti e
   messaggi in italiano, come il resto del codice dell'utente; nomi delle funzioni di `api.py` in inglese come nello
   schema (`prices()`, `listings()`, …), perché sono l'interfaccia verso gli altri package.
3. **Solo libreria standard nelle fasi 0-2** (client HTTP con `urllib`, gzip, json). `duckdb` e `pyarrow` sono chiesti
   dalla direttiva per la fase 3: dichiarati in `pyproject.toml` come extra `archivio`, installati quando servono.
   Oggi non sono installati in nessun ambiente della macchina.
4. **Chiave e percorso solo da ambiente o `.env`** alla radice del repo ospite (l'ambiente vince). `MARKET_DATA_DIR` è
   obbligatoria e **rifiutata se sta dentro il repo ospite o dentro qualsiasi altro repo git**: test in
   `tests/test_config.py`.
5. **Limiti con margine del 10%** (`config.Limiti`), consumo registrato per giorno UTC in un registro append-only;
   il consumo reale si confronta con quello dichiarato dal fornitore.
6. **ADR del package in `market-data/docs/adr/`**, non nel changelog del repo ospite: il package deve poter vivere da
   solo, come `edgar_llm/docs/adr/`.
7. **`api.py` esiste già con le firme** e solleva `NonAncoraDisponibile` finché l'archivio non c'è: un chiamante non
   riceve mai una tabella vuota scambiandola per un dato.

## Aperto (per l'utente)

- Lo scanner e i suoi backtest stavano in un **repo separato**, con la regola «questo repo non conosce il repo
  ospite». Come i suoi backtest arrivano a `market_data.api` va deciso prima della fase 3.
- Disco: 18,4 GB liberi, nessun altro disco collegato. Lo spazio dell'archivio si stima alla fermata 2.

## Aggiornamento del 2026-09-27

market-data non vive più nel repo di allora: è in `edge-lab/market-data/` (ADR 007). Le scelte di struttura qui sopra
restano; «repo ospite» nel testo di questa ADR va letto come il repo di allora.
