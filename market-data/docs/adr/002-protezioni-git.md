# ADR 002 — Protezioni git: controllo pre-commit senza dipendenze

**Data:** 2026-09-17 · **Stato:** accettata

## Contesto

I dati EODHD non devono mai finire su git (licenza per uso personale, senza ridistribuzione) e la chiave non deve
comparire in codice, log o ADR. La direttiva chiede un controllo pre-commit che blocchi file di dati, file sopra 5 MB e
stringhe simili alla chiave.

## Decisioni e motivi

1. **Hook git semplice in `.githooks/`, attivato con `git config core.hooksPath .githooks`**, invece del framework
   `pre-commit`: nessuna dipendenza nuova, e il file dell'hook è versionato con il repo. Limite: l'attivazione è una
   configurazione locale da ripetere su ogni clone (scritto nel README).
2. **Il controllo è a livello di repo** (`.githooks/guard.py`, test in `tests/test_guard_precommit.py`), non dentro
   market-data: protegge qualsiasi commit, anche quelli che non toccano il package.
3. **Si guarda la staging area** (`git show :<file>`), non la cartella di lavoro: è il contenuto che il commit
   conterrebbe davvero.
4. **Regole:** estensioni `.parquet`, `.duckdb`, `.gz`, `.feather`, `.arrow`; file `.env` (ammesso `.env.example`);
   dimensione sopra 5 MB; contenuto con la chiave vera (letta da ambiente o `.env`, confronto esatto), con la forma delle
   chiavi EODHD (esadecimale, punto, cifre), con `api_token=` o `EODHD_API_KEY=` seguiti da un valore. Il messaggio dice
   file e motivo, **mai la stringa trovata**.
5. **I test non contengono chiavi finte intere**: sono costruite per concatenazione, altrimenti il controllo bloccherebbe
   i test stessi.
6. **`.gitignore` come seconda rete**: `.env`, `*.parquet`, `*.duckdb`, `*.json.gz`, `*.csv.gz`, `invest-data/`.

## Aggiornamento del 2026-09-27

Il controllo pre-commit vive ora alla radice di edge-lab (`.githooks/guard.py`, test in `tests/test_guard_precommit.py`),
perché market-data si è spostato lì (ADR 007). Il punto 2 resta vero: protegge ogni commit del repo che contiene
market-data, non solo quelli che toccano il package.
