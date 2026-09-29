# Russell 2000, uscite verso il basso — inventario dei dati (fase 0)

**16 settembre 2026**, ramo `feat/russell-exits`. Verifiche fatte oggi; le cifre sulle fonti esterne vengono dalle pagine
indicate. Scelte dell'utente nel piano: composizione dalle partecipazioni SEC trimestrali, prezzi Yahoo.

## 1. Date per anno — `date_ricostituzione.csv`

| anno | Rank Day | liste preliminari | ricostituzione (dopo la chiusura) | fonte |
|---|---|---|---|---|
| 2015 | 29 mag | 12 giu | 26 giu | comunicato FTSE Russell su BusinessWire (lettura automatica rifiutata: estratto) e ristampa del comunicato sulle liste 2015 |
| 2016 | 27 mag | 10 giu | 24 giu | **solo fonti terze** (blog, Cboe); pagina ufficiale non trovata |
| 2017 | 12 mag | 9 giu | 23 giu | avviso FTSE Russell id 2062382 |
| 2018 | 11 mag | 8 giu | 22 giu | comunicato ufficiale ristampato da Mondovisione (pagina LSEG: 404) |
| 2019 | 10 mag | 7 giu | 28 giu | comunicato LSEG (PDF) |
| 2020 | 8 mag | 5 giu | 26 giu | comunicato LSEG |
| 2021 | 7 mag | 4 giu | 25 giu | avviso FTSE Russell id 2599440 |
| 2022 | 6 mag | 3 giu | 24 giu | comunicato LSEG |
| 2023 | 28 apr | 19 mag | 23 giu | comunicato LSEG |
| 2024 | 30 apr | 24 mag | 28 giu | comunicato LSEG |
| 2025 | 30 apr | 23 mag | 27 giu | comunicato LSEG |
| dic 2026 | 30 ott | 13 nov | 11 dic | comunicato LSEG |

Tutte le date 2015-2025 sono sedute del calendario di IWM (verificato). URL completi nel CSV.

## 2. Composizione dell'indice

**File storici iShares: non disponibili.** `latest-holdings.csv` ignora `asOfDate`; il vecchio endpoint `.ajax`
restituisce la pagina HTML del prodotto (verifica del 15 settembre, ripetuta oggi).

**Depositi SEC di iShares Trust** (CIK 1100663; IWM serie S000004344 classe C000012074, IWB serie S000004347 classe
C000012077, da `company_tickers_mf.json`). Elenco dei depositi in `risultati/fase0_depositi.json`
(`fase0_depositi.py`); lettura in `partecipazioni_sec.py`; file in `state/backfill/russell/holdings/` con impronte.

| periodo | fonte | contenuto |
|---|---|---|
| 31 marzo 2015-2019 | N-CSR annuale, voce 6 «Full schedules of investments» (prospetto completo, non il riassuntivo) | nome, azioni, valore |
| 30 giugno 2015-2018 | N-Q | nome, azioni, valore |
| **30 giugno 2019** | **nessun deposito**: dopo l'ultimo N-Q (marzo 2019) e prima del primo N-PORT-P pubblico (periodo 30 settembre 2019) | — |
| 31 marzo e 30 giugno 2020-2025 | N-PORT-P, `primary_doc.xml` (azioni ordinarie, `assetCat` EC) | nome, titolo, CUSIP, ISIN, azioni, valore; nessun ticker |

Istantanee lette: 42 su 44; IWM 1.920-2.116 titoli, IWB 974-1.036; valori totali coerenti con il patrimonio dei fondi.
Tre formati HTML diversi (2015-2017, 2018, 2019) gestiti dallo stesso lettore. Chiamate EDGAR per i fondi: 226.

**Liste FTSE Russell**: online solo le cancellazioni finali 2025 (`ru3000-deletions-20250627.pdf`, 5 pagine, circa 230
righe con nome, simbolo e settore); usate come controllo esterno per il 2025 (`lista_ftse_pdf.py`, libreria standard).

## 3. Prezzi e volumi

Yahoo via `yfinance` (`scarica_ohlcv.py`): `Close`, `Adj Close`, `Volume`, `Stock Splits`, dal 2014-01-01 al 2026-08-28,
per i ticker dei candidati all'identità. **I titoli delistati non ci sono** (Yahoo non li serve): esclusi come «identità:
nessun prezzo Yahoo» o «prezzi e volumi insufficienti» e contati. Copertura in `risultati/conteggi.md`.

## 4. Bilanci

Companyfacts XBRL di EDGAR (`https://data.sec.gov/api/xbrl/companyfacts/`), cache del repo per circa 6.800 emittenti,
mancanti scaricati sul tetto di 3.000 chiamate EDGAR per il backtest. Solo fatti con `filed` < Rank Day. Tag, alternative
e costruzione dei 12 mesi in `2026-09-16_preregistrazione.md` §4; copertura di ogni filtro in `conteggi.md`.

## 5. Prova parallela FTSE Russell di novembre 2025

**No.** FTSE Russell ha fatto una prova interna del nuovo calendario semestrale, con data di rango 30 settembre 2025, e ne
ha pubblicato solo un riepilogo con dati aggregati; liste di aggiunte e cancellazioni pubbliche non trovate.
[LSEG — insights from the November 2025 parallel run](https://www.lseg.com/en/ftse-russell/research/insights-from-the-november-2025-russell-us-indexes-parallel-run).
