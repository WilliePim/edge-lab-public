# ADR 009 — Bilanci e depositi della SEC in market-data: `api.sec_azioni()`, `api.sec_bilancio()`, `api.sec_societa()`, `api.sec_depositi()`

**Data:** 2026-10-06 · **Stato:** accettata

## Contesto

Uno studio che costruisce un universo di società a una data ha bisogno delle azioni in circolazione note quel giorno
(per la capitalizzazione) e delle voci di bilancio con la loro data di deposito. La SEC pubblica tutto questo in due
file in blocco, `companyfacts.zip` e `submissions.zip`. I due file erano già nella cartella dei dati, letti da un
lettore che viveva dentro un backtest, fuori da `market_data.api`: la lettera di `tests/test_market_data_confine.py`
era rispettata, la regola «i dati fuori dal repo si leggono solo da `market_data.api`» no. Decisione: i lettori stanno
in market-data, con test e ADR; chi ne ha bisogno li usa tramite `market_data.api`.

## I file

| file | scaricato (UTC) | byte | sha256 | contenuto |
|---|---|---:|---|---|
| `sec_bulk/companyfacts.zip` | 2026-10-03 15:48:43 | 1.410.049.978 | `db35d36bd7b34ac7…` | 20.428 file `CIK##########.json`, 19,3 GB non compressi |
| `sec_bulk/submissions.zip` | 2026-10-03 15:50:26 | 1.567.247.172 | `066aff2f3ec2fa80…` | 992.859 file (987.470 testate), 5,8 GB non compressi |
| `sec_bulk/manifest.json` | | | | per file: URL, data, byte, sha256, testate HTTP (`Last-Modified` 2026-10-03) |

Origine: `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip` e
`…/bulkdata/submissions.zip`, due richieste. Dati pubblici della SEC, senza licenza restrittiva; stanno comunque fuori dal
repo perché pesano 2,8 GB e perché il controllo pre-commit rifiuta i file di dati. Letto: il manifest, la dimensione dei
due file e l'elenco dei nomi dentro gli zip, il 06-10-2026.

## Decisioni

1. **Cinque funzioni in `api.py`, una implementazione in `market_data/sec.py`.**
   - `sec_azioni(cik, *, cache=False)`: tutte le osservazioni di `dei:EntityCommonStockSharesOutstanding`,
     `us-gaap:CommonStockSharesOutstanding` e `us-gaap:WeightedAverageNumberOfSharesOutstandingBasic`.
   - `sec_bilancio(cik, voci, *, cache=False)`: le voci chieste (`Revenues` = `us-gaap:Revenues`; con tassonomia
     `dei:EntityPublicFloat`), una riga per fatto e per deposito che lo riporta: `cik`, `voce`, `unita`, `inizio`,
     `fine`, `valore`, `depositato`, `modulo`, `esercizio`, `periodo`, `accn`, `frame`.
   - `sec_cik(file)`: i CIK che hanno un file nello zip (per distinguere «società assente» da «voce assente»).
   - `sec_societa(cik, *, cache=False)` e `sec_depositi(cik, moduli=None, *, tutti=False, cache=False)`: testata e
     depositi da `submissions`. Servono a chi deve classificare le società per settore (SIC) e riconoscere dai depositi
     le uscite dalla quotazione (per esempio 8-K voce 1.03, moduli 25 e 15), che l'archivio dei prezzi non distingue.
   `cik` è un numero, un testo con o senza zeri, o un elenco.
2. **Nessuna scelta di merito nel lettore.** Restituisce tutte le unità, tutti i depositi, tutti i moduli, i valori come
   depositati. Quale osservazione vale a una data (`depositato <= data`), quale voce preferire, come trattare
   riesposizioni ed errori di scala: sono regole di chi legge e stanno nel suo codice, non qui.
3. **Senza rete, fail-closed.** Il modulo non importa nessuna libreria di rete (un test lo verifica sull'albero
   sintattico). Se manca il manifest, se il file non è nel manifest, se non c'è, se ha una dimensione diversa da quella
   del manifest o non è uno zip: `sec.FileMancante` con il nome del file e il motivo. Nessun download implicito. Un CIK
   senza file nello zip dà zero righe, non un errore. L'impronta sha256 non si ricalcola a ogni apertura (1,4 GB): si
   controlla la dimensione.
4. **Nessun aggiornamento automatico.** I file sono un'istantanea del 03-10-2026; `eodhd.update` non li tocca. Per
   aggiornarli si riscaricano a mano e si riscrive il manifest: è una decisione da prendere quando servirà, con il suo
   User-Agent e il suo limite di frequenza. Un backtest che li usa deve dichiarare la data dell'istantanea.
5. **Cache opzionale nella cartella dei dati**, `sec_bulk/cache/`: con `cache=True` le società già lette per una data
   combinazione di voci (o di moduli) restano in una tabella Parquet, con l'elenco dei CIK già cercati; la chiave
   contiene l'impronta dello zip scritta nel manifest, quindi un file nuovo non rilegge una cache vecchia. Senza cache
   leggere una società costa da qualche decina di millisecondi a un secondo (la prima apre lo zip e ne legge l'indice);
   leggere tutte le società di un universo, minuti. La cache non è un dato: cancellarla non perde niente.
6. **Dove stanno i file.** Restano in `<archivio>/sec_bulk/`; non si spostano sotto un fornitore con `store/raw.py`
   perché quel livello è fatto di risposte piccole compresse una per una, e qui ci sono due zip da 1,4 GB che si
   leggono dall'interno.

## Che cosa i file contengono e che cosa no (visto sui dati veri)

- **Niente fatti con una dimensione.** `companyfacts` porta solo i fatti senza dimensioni XBRL: per una società con più
  classi di azioni mancano il frontespizio e lo stato patrimoniale per classe. Alcuni grandi emittenti con più classi
  hanno solo la media ponderata; altri nessuna delle tre voci.
- **Errori di scala nei depositi.** Azioni mille o un milione di volte più grandi del vero, in tutte e tre le voci: un
  grande emittente riporta le azioni in migliaia in un deposito e in unità nel successivo. Fra le società con almeno
  due voci utili a una data di formazione, 20-45 per data (su circa 5.000) hanno voci che differiscono di oltre 100
  volte. Il lettore non li corregge.
- **Lo stesso periodo più volte**: una riga per ogni deposito che lo riporta, con il suo `depositato`.
- **Chi non c'è**: 11.897 dei 24.853 CIK dell'anagrafica USA (`Common Stock`) non hanno un file in `companyfacts`
  (codici OTC, società estere che non depositano XBRL, fondi chiusi); 6 non hanno testata in `submissions`.
- **Emittenti esteri**: chi deposita 20-F o 40-F ha i fatti sotto quei moduli (e spesso sotto `ifrs-full`).
- **`submissions`**: nome, SIC, ticker e borsa sono quelli di oggi; la testata porta i 1.000 depositi più recenti, i più
  vecchi stanno nei file `-submissions-NNN` (`tutti=True`).

## Alternative scartate

- **Lasciare il lettore nel backtest**: è ciò che la regola del confine vieta, ed è il motivo della decisione.
- **API `companyfacts` per società o API `frames`**: migliaia di chiamate la prima; la seconda tiene un solo fatto per
  periodo e società, l'ultimo depositato, quindi non è punto-nel-tempo.
- **Normalizzare tutto `companyfacts` in Parquet**: 19 GB di JSON per usare una ventina di voci; la cache per voci
  chieste dà lo stesso tempo di rilettura con qualche decina di MB.
- **Scegliere dentro il lettore «le azioni a una data»**: sarebbe una regola di backtest dentro la libreria dei dati.

## Verifica

`market-data/tests/test_sec.py`, 9 test su due zip finti costruiti nel test (nessuna rete, nessuno dei file veri):
voci, unità, deposito, fatti senza valore, valori istantanei, tre voci delle azioni con un errore di scala lasciato
com'è, più società, CIK come testo, CIK assente, testata e depositi, cache (stesso risultato, nessuna rilettura), file
mancante, dimensione diversa dal manifest, nessun modulo di rete. Letto sui file veri il 06-10-2026: `api.sec_azioni(320193)`
448 righe, ultimo frontespizio 14.594.180.000 azioni al 2026-07-17 depositato il 2026-07-31; `api.sec_cik()` 20.428 CIK;
`api.sec_depositi(719739, ["8-K"])` con la voce 1.03 del 2023-03-10.
