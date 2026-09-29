# ADR 007 — market-data si sposta in edge-lab

**Data:** 2026-09-27 · **Stato:** accettata (decisione dell'utente) · **Specchio:** `DECISIONS.md` di edge-lab (confine con i repo esterni, market-data dentro edge-lab, percorso dell'archivio solo da configurazione)

## Contesto

market-data è nato il 17 settembre come package di un altro repo (ADR 001). Il 27 settembre l'utente ha deciso che
edge-lab non deve dipendere da un repo esterno in alcun modo. L'inventario di quel giorno ha trovato che market-data ha
un solo consumatore, edge-lab (6 moduli di backtest): il repo ospite non lo importa e il suo ambiente non lo installa.

## Decisione

1. **market-data vive in `edge-lab/market-data/`.** La storia di sviluppo è venuta con lui (`git subtree split` nel repo
   di allora, `git subtree add --prefix=market-data` in edge-lab); la copia nel repo di allora si toglie in un suo branch
   di pulizia.
2. **Installazione in sviluppo dal repo che lo contiene:** `pip install -e ./market-data[archivio]`. L'extra `archivio`
   porta duckdb, pyarrow e pandas (pandas aggiunto adesso: `api.py` restituisce DataFrame tramite `.df()`).
3. **Configurazione:** `REPO_ROOT = parents[2]` in `config.py` ora è la radice di edge-lab, quindi il `.env` letto è
   quello di edge-lab (`MARKET_DATA_DIR`, `EODHD_API_KEY`). Nessun cambio di logica: l'ambiente vince sul file, nessun
   valore predefinito, e l'archivio resta rifiutato se relativo, dentro edge-lab o dentro qualunque repo git.
4. **Il confine con chi lo usa non cambia** (ADR 004): fuori da `market-data/`, edge-lab usa solo `market_data.api`.
5. **Le protezioni git** (ADR 002) si portano alla radice di edge-lab: `.githooks/guard.py` identico dopo
   l'intestazione, test in `tests/test_guard_precommit.py` di edge-lab.
6. **I test restano pytest**, eccezione dichiarata nel `DECISIONS.md` di edge-lab; `test.sh` di edge-lab li lancia.

## Alternative scartate

- **Repo a sé, installato come pacchetto con versione:** nessun secondo consumatore oggi.
- **Copia senza storia:** si perderebbero le decisioni delle fasi 0-5 registrate nei commit.

## Conseguenze

- `api.fred()`, con le versioni storiche ALFRED, si costruirà qui, e nessuno studio scriverà un secondo lettore FRED.
- Due guasti trovati nel trasloco, non introdotti da esso: `quality/calendario.py` importa `exchange_calendars`, mai
  dichiarato in `pyproject.toml` (decisione aperta con l'utente, nuova dipendenza); `tests/test_update.py::
  test_barre_in_blocco_aggiunte_dopo_la_serie` falliva già nel repo di allora. *Nota della versione pubblica
  (2026-09-28): `exchange_calendars>=4.13` è ora dichiarata nell'extra `archivio` di `pyproject.toml` (4.13.2 è la
  versione della fase 1, ADR 005).*
- I comandi del README restano validi: `..\.venv\Scripts\python.exe` dalla cartella `market-data` è ora il venv di
  edge-lab.

## Verifica

Il secondo genitore del merge del subtree è il commit dello split; file tracciati e blob identici a quelli della copia
nel repo di allora (letti con `git ls-tree` nei due repo). Dopo la reinstallazione il `direct_url.json` del pacchetto
punta a `edge-lab/market-data`, `config.archivio()` restituisce l'archivio leggendo il `.env` di edge-lab e
`api.trading_days("US", ...)` legge le sedute.
