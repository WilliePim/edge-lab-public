# E3 — conteggi, con le decisioni della fermata 1

Nessun rendimento extra calcolato o guardato. Generato da `backtest/ipo_e3/conteggi.py`.

## 1. Imbuto per anno

| passo | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | totale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CIK con un prospetto 424B4/B1 (o B3) | 310 | 647 | 397 | 305 | 284 | 274 | 328 | 283 | 552 | 1162 | 245 | 216 | 282 | 5285 |
| − classe già quotata | 123 | 109 | 87 | 73 | 67 | 78 | 91 | 68 | 115 | 213 | 66 | 47 | 41 | 1178 |
| − SPAC (SIC 6770) | 5 | 3 | 4 | 9 | 3 | 5 | 11 | 9 | 86 | 360 | 51 | 22 | 39 | 607 |
| − emittente estero o ADR | 14 | 25 | 54 | 27 | 16 | 40 | 54 | 47 | 54 | 91 | 33 | 61 | 88 | 604 |
| − entità non operativa (co-registrante o garante) | 20 | 281 | 1 | 37 | 59 | 4 | 2 | 5 | 4 | 2 | 0 | 4 | 1 | 420 |
| − REIT (SIC 6798) | 8 | 19 | 8 | 9 | 5 | 6 | 4 | 3 | 4 | 7 | 0 | 0 | 2 | 75 |
| − banca o cassa di risparmio (SIC 6022) | 3 | 6 | 10 | 5 | 4 | 5 | 8 | 5 | 0 | 3 | 1 | 0 | 0 | 50 |
| − fondo chiuso (N-2) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | 22 | 5 | 1 | 8 | 41 |
| − banca o cassa di risparmio (SIC 6021) | 4 | 0 | 3 | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 11 |
| − banca o cassa di risparmio (SIC 6029) | 1 | 0 | 1 | 0 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| − banca o cassa di risparmio (SIC 6036) | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 3 |
| − banca o cassa di risparmio (SIC 6035) | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| **restano dopo le esclusioni senza testo** | 130 | 204 | 228 | 144 | 129 | 132 | 157 | 146 | 284 | 463 | 89 | 81 | 102 | 2289 |
| − SPAC (trust account dichiarato) | 3 | 6 | 8 | 10 | 7 | 24 | 27 | 39 | 131 | 167 | 26 | 9 | 15 | 472 |
| − nessun prezzo di collocamento nel prospetto | 29 | 26 | 16 | 9 | 42 | 6 | 12 | 5 | 13 | 23 | 12 | 12 | 13 | 218 |
| − meno dell'80% di barre fra la prima barra e il controllo | 7 | 16 | 31 | 21 | 10 | 7 | 24 | 19 | 23 | 40 | 7 | 4 | 1 | 210 |
| − unit | 5 | 9 | 15 | 5 | 4 | 6 | 5 | 2 | 7 | 18 | 10 | 4 | 2 | 92 |
| − durata del lock-up non trovata | 2 | 6 | 9 | 4 | 4 | 2 | 5 | 7 | 9 | 10 | 4 | 10 | 3 | 75 |
| − senza serie di prezzi entro 10 sedute | 5 | 3 | 8 | 4 | 2 | 3 | 3 | 8 | 10 | 8 | 2 | 2 | 17 | 75 |
| − società in accomandita o LLC con «common units» | 7 | 17 | 16 | 9 | 2 | 6 | 2 | 1 | 1 | 5 | 1 | 2 | 1 | 70 |
| − prezzo di collocamento sotto $5 | 4 | 2 | 2 | 5 | 4 | 1 | 2 | 3 | 1 | 7 | 8 | 13 | 15 | 67 |
| − prima chiusura incoerente con il prezzo di collocamento | 2 | 2 | 2 | 2 | 1 | 1 | 3 | 0 | 0 | 1 | 1 | 0 | 0 | 15 |
| − REIT dichiarato | 0 | 7 | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 13 |
| − serie finita prima della data di controllo | 1 | 1 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 5 |
| − serie non caricata | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| **classificate alla data di controllo** | 65 | 109 | 119 | 75 | 51 | 75 | 73 | 62 | 89 | 181 | 18 | 24 | 35 | 976 |
| · rotta | 9 | 4 | 19 | 24 | 3 | 6 | 14 | 12 | 9 | 74 | 3 | 8 | 10 | 195 |
| · forte | 26 | 67 | 43 | 20 | 23 | 35 | 28 | 28 | 52 | 31 | 1 | 2 | 10 | 366 |
| · intermedia | 30 | 38 | 57 | 31 | 25 | 34 | 31 | 22 | 28 | 76 | 14 | 14 | 15 | 415 |
| rotte che passano i filtri all'ingresso A | 3 | 0 | 2 | 2 | 0 | 2 | 2 | 1 | 0 | 5 | 0 | 0 | 0 | 17 |
| rotte che passano i filtri all'ingresso B | 1 | 0 | 2 | 2 | 0 | 2 | 3 | 1 | 0 | 6 | 0 | 0 | 0 | 17 |
| rotte che passano i filtri all'ingresso C | 3 | 0 | 1 | 3 | 0 | 2 | 3 | 0 | 0 | 6 | 0 | 0 | 0 | 18 |
| forti senza fusioni annunciate | 24 | 65 | 43 | 20 | 23 | 35 | 27 | 28 | 52 | 31 | 1 | 2 | 10 | 361 |

**Società in accomandita e LLC con «common units»** (escluse, decisione dell'utente alla fermata 1): 92 segnate nel prospetto.

**Serie incoerenti con il prezzo di collocamento** (ADR-051-052: prima chiusura fuori da 0,5-3 volte il prezzo di collocamento, escluse): 15 IPO (elenco per nome e rapporto tolto nella copia pubblica).

**Costituite fuori dagli Stati Uniti ma domestiche** (restano, contate): 31 classificate.

**Escluse per le barre a causa di un `salto_sospetto`** (`salti.py`; restano fuori, decisione dell'utente alla fermata 1): delle 213 IPO con meno dell'80% di barre, classificabile 180, prima chiusura incoerente (ADR-051) 17, nessun salto_sospetto segnalato 9, salto o frazionamento dentro la finestra 7. Le classificabili sulle chiusure grezze, con il salto dopo la data di controllo, sarebbero:

| passo | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | totale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| · rotta | 0 | 3 | 4 | 6 | 2 | 1 | 9 | 6 | 3 | 19 | 3 | 1 | 1 | 58 |
| · forte | 1 | 0 | 4 | 3 | 1 | 2 | 5 | 4 | 9 | 2 | 0 | 0 | 0 | 31 |
| · intermedia | 5 | 9 | 18 | 7 | 7 | 3 | 9 | 7 | 9 | 14 | 2 | 1 | 0 | 91 |

## 2. Coperture per anno

| passo | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | totale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| prospetto letto | 130 | 204 | 228 | 144 | 129 | 132 | 157 | 146 | 284 | 463 | 89 | 81 | 102 | 2289 |
| serie di prezzi entro 10 sedute (identità per CIK) | 103 | 167 | 204 | 125 | 76 | 112 | 136 | 125 | 220 | 361 | 59 | 63 | 53 | 1804 |
| prezzo di collocamento trovato | 97 | 174 | 204 | 130 | 84 | 118 | 137 | 131 | 247 | 402 | 73 | 67 | 82 | 1946 |
| lock-up trovato | 97 | 168 | 195 | 122 | 77 | 116 | 132 | 124 | 244 | 387 | 62 | 45 | 74 | 1843 |
| data dalla copertina | 42 | 92 | 115 | 67 | 50 | 62 | 76 | 62 | 97 | 194 | 26 | 32 | 35 | 950 |
| data dalla seduta prima della prima barra | 35 | 42 | 47 | 35 | 17 | 23 | 30 | 26 | 24 | 38 | 4 | 7 | 4 | 332 |
| data della copertina a più di 5 sedute dalla prima barra | 2 | 2 | 2 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 8 |

**Durate del lock-up** fra le classificate: 30 giorni: 4, 60 giorni: 2, 90 giorni: 19, 121 giorni: 1, 125 giorni: 2, 150 giorni: 2, 165 giorni: 1, 175 giorni: 1, 180 giorni: 927, 181 giorni: 11, 240 giorni: 1, 360 giorni: 3, 365 giorni: 2.

Prospetti con più di una durata nelle frasi di lock-up (eccezioni registrate): 216.

**Filtri delle rotte**, per ingresso: passa / non passa / non verificabile.

| ingresso | filtro | passa | non passa | non verificabile |
|---|---:|---:|---:|---:|
| A | f1 | 38 | 123 | 34 |
| A | f2 | 167 | 4 | 24 |
| A | f3 | 146 | 29 | 20 |
| A | f4 | 194 | 1 | 0 |
| B | f1 | 41 | 146 | 7 |
| B | f2 | 155 | 15 | 24 |
| B | f3 | 128 | 52 | 14 |
| B | f4 | 191 | 3 | 0 |
| C | f1 | 42 | 149 | 4 |
| C | f2 | 158 | 14 | 23 |
| C | f3 | 135 | 46 | 14 |
| C | f4 | 192 | 3 | 0 |
| forte | f4 | 361 | 5 | 0 |

Filtro 1 con l'opzione (b) scelta alla fermata 1: dove i 12 mesi non sono calcolabili, il flusso di cassa operativo progressivo di 6-12 mesi deve essere positivo (addendum §1).

## 3. Casi disponibili per orizzonte e per cella

Un caso è disponibile per un orizzonte se l'ingresso più l'orizzonte sta nell'archivio (ultima seduta 2026-09-16). Il placebo sposta la finestra di 252 sedute in avanti di 126. Con peer = i 5 peer sono stati trovati.

| ingresso | passano i filtri | con peer | 63 | 126 | 252 | placebo 252 |
|---|---:|---:|---:|---:|---:|---:|
| A | 17 | 1 | 1 | 1 | 1 | 1 |
| B | 17 | 17 | 17 | 17 | 17 | 17 |
| C | 18 | 18 | 18 | 18 | 18 | 18 |
| forte | 361 | 333 | 333 | 333 | 332 | 332 |

**Peer**, esito per ingresso: A ok: 1; A rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia): 16; B ok: 17; C ok: 18; base capitalizzazione non calcolabile: 37; base ok: 905; base rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia): 34; forte capitalizzazione non calcolabile: 17; forte ok: 333; forte rendimento a 6 mesi non calcolabile (meno di 126 sedute di storia): 11.

**verdetto 1 (rotte, B × 252)**: 17 casi in 7 anni di coorte (2012 1, 2014 2, 2015 2, 2017 2, 2018 3, 2019 1, 2021 6). Criterio 1 del verdetto: almeno 80 casi e 8 anni.

**verdetto 2 (forti × 252)**: 332 casi in 13 anni di coorte (2012 23, 2013 63, 2014 41, 2015 18, 2016 22, 2017 31, 2018 26, 2019 25, 2020 48, 2021 25, 2022 1, 2023 2, 2024 7). Criterio 1 del verdetto: almeno 80 casi e 8 anni.

## 4. Giorno d'ingresso B e controllo di degenerazione

Sedute dalla scadenza del lock-up all'ingresso B, sulle 194 rotte con un ingresso B: primo giorno possibile (S + 30) 31 (16.0%), forzati (S + 126) 70 (36.1%), quartili 39 / 76 / 126.

**Degenerazione**: 52.1% dei casi agli estremi (più di metà: DICHIARATO).

Esiti della regola B: REGOLA 124, FORZATO 70, VOLUME_DI_RIFERIMENTO_ASSENTE 1.

## 5. Verifica a mano di 30 prospetti

| campo | estratti | giusti | precisione | non trovati |
|---|---:|---:|---:|---:|
| prezzo | 27 | 27 | 100.0% | 0 |
| data | 30 | 29 | 96.7% | 0 |
| lockup | 25 | 24 | 96.0% | 3 |
| offerte | 26 | 24 | 92.3% | 3 |
| dopo | 27 | 25 | 92.6% | 2 |

Dettaglio caso per caso: `backtest/ipo_e3/verifica_30.md`.

## 6. Un caso completo per gruppo (senza rendimenti)

*Copia pubblica: sezione tolta. Mostrava, per il primo caso rotto e il primo forte, date, filtri e i cinque peer con
capitalizzazione e rendimento a 6 mesi titolo per titolo, calcolati sui prezzi dell'archivio.*

## 7. Chiamate EDGAR

2699 su 3000 (i due zip in blocco contano una chiamata ciascuno).

