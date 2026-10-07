# ADR 008 — Serie della Fed in market-data: `api.fred()` (FRED e ALFRED), `api.ebp()`, `api.gsw()`

**Data:** 2026-09-30 · **Stato:** accettata

## Contesto

Chi lavora con serie macroeconomiche in un backtest ha bisogno della loro **storia di pubblicazione**: il valore che si
leggeva a una data, non quello rivisto anni dopo. ADR 007 aveva già fissato che il lettore FRED con le versioni storiche
ALFRED si costruisce qui e che nessuno studio ne scrive un secondo. Oltre a FRED servono due file che la Fed pubblica
fuori da FRED: l'excess bond premium di Gilchrist-Zakrajšek e la curva zero-coupon di Gürkaynak-Sack-Wright
(`feds200628.csv`).

## Decisioni

1. **Tre funzioni in `api.py`, una implementazione in `market_data/fred.py`.** `fred(serie, *, inizio, fine, al_giorno)`,
   `ebp(*, inizio, fine)`, `gsw(*, inizio, fine)`; DataFrame con `date` e le colonne della fonte, come il resto di `api`.
   Si legge il file intero, parametri compresi, senza scegliere scadenze.
2. **Senza `al_giorno`: il CSV pubblico di FRED** (`fredgraph.csv?id=SERIE`), senza chiave: la serie come è oggi.
   **Con `al_giorno`: ALFRED** (`api.stlouisfed.org/fred/series/observations`, `realtime_start = realtime_end =
   al_giorno`), la serie come si leggeva quel giorno. Serve `FRED_API_KEY`, letta come le altre variabili (ambiente,
   poi `.env` di edge-lab; `config.chiave_fred()`; nome in `.env.example`).
3. **Chiave assente = errore prima di qualunque richiesta** (`ConfigError`), **versione assente = errore** (`ErroreFonte`
   se ALFRED risponde con `observations` vuoto, con un `error_message`, o con uno stato diverso da 200). Nessun ripiego
   sui dati di oggi: una versione storica sostituita in silenzio con la serie attuale è lookahead.
4. **Livello grezzo per fornitore.** `store/raw.py` prende il fornitore (`Grezzo(archivio, "fred")`):
   `<archivio>/fred/raw/<AAAA-MM-GG>/…` e `<archivio>/fred/manifest/grezzo.jsonl`, stessa forma di `eodhd/`. `api_key` si
   aggiunge a `api_token` fra i segreti che non entrano nel manifest, nella chiave né nel nome del file; `oscura()` del
   client copre tutti e due. Nessun cambiamento per EODHD (fornitore predefinito, test di `test_raw.py` invariati).
5. **Riuso.** Il CSV di FRED, l'EBP e la curva GSW cambiano nel tempo: si riscaricano al massimo una volta al giorno UTC
   e per il resto del giorno si rilegge il file; un secondo download in un altro giorno è un file nuovo, mai una
   sovrascrittura (l'EBP è ristimato a ogni aggiornamento e non ha versioni: la data del download è la sua versione).
   Una versione ALFRED è immutabile e si scarica una volta sola.
6. **Solo libreria standard per la rete** (`urllib`, come `eodhd/client.py`): nessuna dipendenza nuova. `fredapi` e
   `pandas-datareader` sarebbero pacchetti nuovi per due URL e un JSON.
7. **Test con rete finta** (`tests/test_fred.py`, 9 test): grezzo datato, filtro sulle date, riuso nello stesso giorno e
   nuovo file il giorno dopo, chiave mancante senza nessuna richiesta, chiave presente nell'URL ma mai nel manifest né nei
   nomi dei file, versione assente ed errori dell'API, EBP con date americane, GSW con le righe di nota e i `NA`.
8. **Il controllo pre-commit conosce anche la chiave FRED** (`.githooks/guard.py`): la chiave vera letta dall'ambiente
   o dal `.env`, la forma «32 esadecimali», `FRED_API_KEY=<valore>` e `api_key=<valore>` bloccano il commit.

## Fonti, verificate con una chiamata reale il 30-09-2026

| chiamata | URL | prima osservazione | ultima | osservazioni |
|---|---|---|---|---|
| `fred(SERIE)` | `fred.stlouisfed.org/graph/fredgraph.csv?id=SERIE` | provata su serie mensili, settimanali e giornaliere | | colonne `observation_date,SERIE`; `.` per il valore mancante |
| `ebp()` | `federalreserve.gov/econres/notes/feds-notes/ebp_csv.csv` | 1973-01-01 | 2026-07-01 | 643, mensile; date come `1/1/1973` |
| `gsw()` | `federalreserve.gov/data/yield-curve-tables/feds200628.csv` | 1961-06-14 | 2026-09-25 | 17.033, giornaliera, 100 colonne; 9 righe di nota prima dell'intestazione, `NA` per i mancanti |
| `fred(SERIE, al_giorno=…)` senza chiave | ALFRED | — | — | `ConfigError: FRED_API_KEY non impostata`, nessuna richiesta partita |
| ALFRED senza chiave, chiamata diretta | `api.stlouisfed.org/fred/series/observations?...` | — | — | HTTP 400 «Variable api_key is not set» |

Le versioni storiche in ALFRED non coprono tutta la storia di una serie: per ciascuna cominciano dalla prima
pubblicazione che ALFRED ha registrato (si legge nella pagina `alfred.stlouisfed.org/series?seid=…`, campo «Release
Dates»). Prima di quella data non c'è una versione da leggere e `api.fred(..., al_giorno=…)` si ferma con `ErroreFonte`:
che cosa fare per quel periodo (per esempio un ritardo di pubblicazione prudente e dichiarato) è una regola di chi usa
la serie e va scritta nel suo studio, non qui.

## Alternative scartate

- **Un lettore dentro uno studio:** ADR 007 e ADR 004 lo vietano; una cache dentro il repo sarebbe un debito.
- **Pacchetti `fredapi`/`pandas-datareader`:** dipendenze nuove per due URL e un JSON.
- **Scaricare a ogni chiamata:** uno studio rilegge le stesse serie decine di volte; una volta al giorno basta e il
  grezzo resta datato.
- **Serie FRED al posto dei file della Fed:** l'EBP non è su FRED; la curva GSW su FRED c'è solo per alcune scadenze,
  senza i parametri.

## Verifica

Letto: il log di `bash test.sh` (market-data 146 test quel giorno; ALL SUITES PASSED); l'uscita dello script di prova con
le chiamate reali di questa tabella; il manifest `<archivio>/fred/manifest/grezzo.jsonl` dopo la prova (un file `.gz`
per download nella cartella del giorno, nessuna chiave).
