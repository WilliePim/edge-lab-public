# market-data

Archivio locale dei prezzi scaricati da **EOD Historical Data** (EODHD) e **unico punto di accesso** per gli altri
package: `market_data.api`. Nessun altro codice legge i file dell'archivio.

I dati **non stanno nel repo**: licenza EODHD per uso personale, senza ridistribuzione. Vivono in `MARKET_DATA_DIR`,
una cartella fuori da qualsiasi repo git (la configurazione rifiuta il contrario).

## Abbonamento

Serve una chiave EODHD con un piano a pagamento (il piano gratuito ha 20 chiamate al giorno). Il client legge i limiti
del piano dalla configurazione e ne usa il 90%. Prima di disdire un abbonamento: download finito, controlli fatti,
copia di sicurezza dell'archivio.

## Stato

| fase | cosa | stato |
|---|---|---|
| scaffolding | package, configurazione, protezioni git, test | fatto |
| 0 | prova del piano (ADR 003) | fatta |
| 1 | copertura del piano (ADR 005) | fatta |
| 2 | piano di download | confermato il 17-09-2026 |
| — | download in massa | codice pronto |
| 3 | grezzo compresso, Parquet, anagrafica, calendario, viste DuckDB, `market_data.api` | codice pronto |
| 4 | controlli di qualità | codice pronto |
| 5 | aggiornamento incrementale | codice pronto |

## Configurazione

`.env` alla radice di edge-lab (modello in `.env.example` di edge-lab); l'ambiente vince sul file:

```
MARKET_DATA_DIR=<percorso assoluto fuori da ogni repo git>
EODHD_API_KEY=<chiave>
EDGAR_USER_AGENT=Nome Cognome email@dominio      # solo per i controlli con EDGAR
```

Il client usa il 90% dei limiti del piano (`EODHD_DAILY_LIMIT`, `EODHD_MINUTE_LIMIT`: 100.000 al giorno, 1.000 al minuto).

## Comandi

Dalla cartella `market-data` (così `market_data` è importabile), con il Python di edge-lab:

```
cd market-data
..\.venv\Scripts\python.exe -m market_data.eodhd.download --blocchi 1,2,3     # download in massa, ripartibile
..\.venv\Scripts\python.exe -m market_data.store.ricostruisci                 # Parquet, anagrafica, calendario, catalogo
..\.venv\Scripts\python.exe -m market_data.quality.esegui                     # controlli della fase 4 e segnalazioni
..\.venv\Scripts\python.exe -m market_data.eodhd.update --prova               # aggiornamento: solo il piano e le chiamate
..\.venv\Scripts\python.exe -m market_data.eodhd.update                       # aggiornamento incrementale
..\.venv\Scripts\python.exe scripts\copia_sicurezza.py E:\backup              # copia su disco esterno (a download finito)
```

**Download**: si ferma da solo se lo spazio non basta o se più del 2% delle chiamate di un blocco fallisce; al tetto
giornaliero aspetta la mezzanotte UTC. Per fermarlo a mano: creare il file `<MARKET_DATA_DIR>/eodhd/manifest/STOP`
(poi cancellarlo e rilanciare: riparte da dove era). Stato in `manifest/stato_download.json`, registro in
`manifest/download.log`.

**Aggiornamento** (a download finito, finché l'abbonamento è attivo): per ogni borsa
1. riscarica le liste e le confronta con le precedenti: titoli attivi senza serie, delistati nuovi (come `X_old` dopo
   un riuso) e ticker riusati (ISIN cambiato, o nome molto diverso se manca l'ISIN) diventano **lavori in coda** nel
   registro `manifest/aggiornamenti.jsonl`, scritti prima di scaricare;
2. scarica in blocco (prezzi, split, dividendi: 300 chiamate a seduta) le sedute dopo la **copertura registrata**, non
   dopo l'ultima barra di un titolo qualsiasi. Una seduta con un blocco non valido o con meno di metà delle righe attese
   si ripete all'esecuzione successiva (solo i blocchi che mancano); corta in 3 giorni diversi si accetta;
3. mette in coda prezzi, dividendi e split dei titoli con uno split, prezzi e dividendi di quelli con un dividendo (la
   chiusura rettificata passata cambia);
4. esegue la coda, compresi i lavori rimasti dalle esecuzioni precedenti: un'interruzione non perde nulla. Un lavoro si
   chiude quando è fatto, dopo 404 in 5 giorni diversi, o quando il titolo esce dalle liste;
5. riscarica cambi, indici, Tesoro dell'anno corrente e precedente, e la mappatura identificativi (salvata solo se
   completa);

poi ricostruisce Parquet, anagrafica, calendario, controlli senza fonti esterne e catalogo. Con `--prova` si vedono prima
le chiamate stimate (quelle in blocco; titoli nuovi ed eventi si sanno solo dopo); con `--fino-a AAAA-MM-GG` si sceglie
l'ultima seduta; `--senza-identificativi` salta la mappatura. Non parte mentre gira il download (stesso chiavistello).
Regole in `docs/adr/006-download-archivio-controlli.md`, punti 39-61.

## Leggere i dati

Da un altro package (lo scanner e i backtest di questo repo, dove `market-data` si installa come libreria: ADR 004):

```python
from market_data import api

api.listings(ticker="P")                             # P (Everpure) e P_old (Pandora): due società, due codici
api.prices(["P_old.US"], start="2015-01-01")        # puliti: senza i periodi esclusi e senza le barre a prezzo zero
api.prices("ICON_old.US", clean=False)              # tutto, compresi i periodi esclusi e gli zeri
api.dividends("AAPL.US"); api.splits("AAPL.US")
api.fx("EURUSD", start="2020-01-01")
api.trading_days("XETRA", "2024-01-01", "2024-12-31")
api.treasury("yield-rates", start="2024-01-01")
api.flags("ICON_old.US")                            # periodi segnalati; `esclude` divide le esclusioni dalle note
api.liquidity("ICON_old.US")                        # quota di barre senza prezzo, e il segno oltre il 20%
```

In SQL, con le viste già pronte:

```python
import duckdb
con = duckdb.connect(r"<MARKET_DATA_DIR>/catalog.duckdb", read_only=True)
con.execute("SELECT exchange, count(*) FROM anagrafica WHERE downloaded GROUP BY exchange").fetchall()
```

Viste: `prezzi`, `prezzi_puliti`, `dividendi`, `split`, `cambi`, `tesoro`, `identificativi`, `anagrafica`, `calendario`,
`barre_tolte`, `doppioni`, `segnalazioni`, `verifiche`, `liquidita`. Colonne e regole d'uso:
[DATA_DICTIONARY.md](DATA_DICTIONARY.md).

## Archivio

```
<MARKET_DATA_DIR>/
  eodhd/
    raw/<AAAA-MM-GG>/...          risposte così come arrivano, compresse gzip; mai sovrascritte
    parquet/<tabella>/exchange=<BORSA>/part-*.parquet
    manifest/grezzo.jsonl         un file grezzo per riga: endpoint, parametri, data, righe, sha256
    manifest/normalizzato.jsonl   un file Parquet per riga: tabella, borsa, righe, sha256, impronta delle sorgenti
    manifest/sorgenti/            per ogni partizione, i file grezzi da cui viene
    manifest/chiamate.jsonl       una riga per richiesta partita: giorno UTC, costo, stato HTTP
    manifest/piano_<blocco>.json, esiti_<blocco>.jsonl, stato_download.json, download.log
    qualita/qualita.json          risultati dei controlli della fase 4
    edgar_cache/                  risposte EDGAR dei controlli
    verifiche.jsonl               periodi segnalati verificati con un'altra fonte (a mano)
  catalog.duckdb                  viste
```

## Protezioni git (una volta per clone)

```
git config core.hooksPath .githooks
```

Il controllo `.githooks/guard.py` blocca il commit se nella staging area ci sono file di dati, file `.env`, file sopra
5 MB o stringhe che somigliano alla chiave. `.gitignore` è la seconda rete.

## Test

Solo dati finti, nessuna chiamata reale:

```
.venv/Scripts/python.exe -m pytest market-data/tests tests/test_guard_precommit.py
```

## Decisioni

`docs/adr/`. I resoconti delle fasi 0-2 e l'inventario dell'archivio non sono in questo repository: riportano
misure per singolo titolo derivate dai dati EODHD, che la licenza non permette di ridistribuire.
