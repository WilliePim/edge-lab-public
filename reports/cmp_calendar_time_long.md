# Cohen-Malloy-Pomorski in calendar time, solo long — tabelle

Descrittivo. Nessuna raccomandazione. La lettura e' tua.


## Aspettativa, scritta prima di girare

> **alfa(OPP) > 0, alfa(ROUT) ≈ 0, OPP − ROUT > 0.**


E' quello che il paper trova. Scriverlo prima e' cio' che rende il risultato leggibile in entrambe le direzioni: se fallisce, fallisce contro qualcosa.


## Deviazioni dal paper

| | CMP (2012) | qui |
|---|---|---|
| periodo | 1986-2007 | **2018-2026** (classificazione dal 2015, portafogli da gennaio 2018) |
| universo | CRSP, tutti gli acquisti di mercato | acquisti Form 4 codice P, non-piano, **con valore ≥ $25.000** (`backfill_fetch.py:45`) |
| prezzi | CRSP per PERMNO | `adj_close` yfinance **per ticker**: su undici anni i simboli vengono riassegnati, e il repo stima le collisioni ticker-CIK al 2,53% |
| delisting | rendimento di delisting CRSP | **ultimo prezzo disponibile**, che sopravvaluta: un fallimento vale l'ultimo scambio, non zero |
| pesi | VW e EW | **solo EW.** La capitalizzazione non esiste nel corpus: `backfill_score.py:242` costruisce `MarketSnapshot(market_cap=None)` e 0 osservazioni su 342.962 ne hanno una |
| tagli dimensionali | per quintili di size | **assenti.** Le tabelle sotto-2e9 richieste non sono costruibili per lo stesso motivo |
| sopravvivenza | CRSP completo | i nomi senza serie prezzi non entrano affatto; sono i falliti e i delistati, e la loro assenza alza ogni alfa qui sotto |

## Insider per categoria, per anno

Etichette assegnate ogni 1 gennaio sui tre anni precedenti. Un insider conta una volta per anno.


| anno | opportunistic | routine | unclassified | totale |
|---|---:|---:|---:|---:|

**acquisti >= $25.000 (come il corpus)**


| anno | opportunistic | routine | unclassified | totale | quota classificata |
|---|---:|---:|---:|---:|---:|
| 2018 | 575 | 161 | 30,277 | 31,013 | 2.4% |
| 2019 | 598 | 148 | 30,267 | 31,013 | 2.4% |
| 2020 | 637 | 167 | 30,209 | 31,013 | 2.6% |
| 2021 | 698 | 193 | 30,122 | 31,013 | 2.9% |
| 2022 | 596 | 159 | 30,258 | 31,013 | 2.4% |
| 2023 | 642 | 155 | 30,216 | 31,013 | 2.6% |
| 2024 | 553 | 163 | 30,297 | 31,013 | 2.3% |
| 2025 | 521 | 142 | 30,350 | 31,013 | 2.1% |
| 2026 | 513 | 112 | 30,388 | 31,013 | 2.0% |

****ogni acquisto > $0****


| anno | opportunistic | routine | unclassified | totale | quota classificata |
|---|---:|---:|---:|---:|---:|
| 2018 | 1,008 | 545 | 39,464 | 41,017 | 3.8% |
| 2019 | 1,002 | 444 | 39,571 | 41,017 | 3.5% |
| 2020 | 1,035 | 461 | 39,521 | 41,017 | 3.6% |
| 2021 | 1,213 | 461 | 39,343 | 41,017 | 4.1% |
| 2022 | 999 | 438 | 39,580 | 41,017 | 3.5% |
| 2023 | 1,003 | 433 | 39,581 | 41,017 | 3.5% |
| 2024 | 939 | 423 | 39,655 | 41,017 | 3.3% |
| 2025 | 925 | 353 | 39,739 | 41,017 | 3.1% |
| 2026 | 812 | 324 | 39,881 | 41,017 | 2.8% |

## 2. Sotto 2e9 — non costruibile

Richiede la capitalizzazione, che il corpus non ha. Non e' stata approssimata: un taglio dimensionale fatto con un proxy sarebbe un taglio su qualcos'altro con l'etichetta della dimensione. `reports/marketcap_feasibility.md` misura che ricostruirla costerebbe ~33 minuti e ~10.000 chiamate, con copertura point-in-time 81,9% [75,5-87,1].


---

# Universo: acquisti >= $25.000 (come il corpus)


## Tutto il corpus, equipesato

**Mesi-titolo scartati perche' la barra non e' un rendimento** (oltre +/-500%, stessa soglia di `backfill_analyse.ARTEFACT`): **12**. Senza questo filtro un solo titolo rotto a maggio 2022 portava la media di 109 nomi a +9.170% e l'alfa UNCL a +98% al mese.

**Uscite per delisting all'ultimo prezzo: 0** — e questo numero non e' una buona notizia. Il meccanismo e' inerte perche' nel campione le serie non finiscono: 599 file su 600 arrivano al 2026. I nomi falliti **non hanno affatto un file**, quindi non entrano nei portafogli e non possono perdere. Sono i **14,507** mesi-titolo senza serie prezzi qui sotto, ed e' survivorship, non assenza di fallimenti.


### Alfa contro CAPM, FF3, FF4


| portafoglio | modello | alfa mensile | t (NW 6) | N mesi | N titoli medio |
|---|---|---:|---:|---:|---:|
| OPPO | CAPM | +0.213% | +0.35 | 99 | 21 |
| OPPO | FF3 | +0.531% | +1.13 | 99 | 21 |
| OPPO | FF4 | +0.611% | +1.32 | 99 | 21 |
| ROUT | CAPM | +0.272% | +0.49 | 99 | 14 |
| ROUT | FF3 | +0.597% | +1.34 | 99 | 14 |
| ROUT | FF4 | +0.647% | +1.48 | 99 | 14 |
| UNCL | CAPM | -0.166% | -0.41 | 99 | 165 |
| UNCL | FF3 | +0.179% | +0.78 | 99 | 165 |
| UNCL | FF4 | +0.210% | +0.93 | 99 | 165 |
| **OPP−ROUT** | CAPM | -0.058% | -0.10 | 99 | — |
| **OPP−ROUT** | FF3 | -0.066% | -0.13 | 99 | — |
| **OPP−ROUT** | FF4 | -0.037% | -0.07 | 99 | — |

## Almeno due compratori opportunistici distinti nel mese

Il taglio sotto-2e9 non e' applicabile; quello sul **numero di compratori** non richiede la capitalizzazione ed e' costruito. Cambia solo OPP: ROUT e UNCL sono ripetuti perche' il confronto OPP−ROUT abbia senso.

**Mesi-titolo scartati perche' la barra non e' un rendimento** (oltre +/-500%, stessa soglia di `backfill_analyse.ARTEFACT`): **12**. Senza questo filtro un solo titolo rotto a maggio 2022 portava la media di 109 nomi a +9.170% e l'alfa UNCL a +98% al mese.

**Uscite per delisting all'ultimo prezzo: 0** — e questo numero non e' una buona notizia. Il meccanismo e' inerte perche' nel campione le serie non finiscono: 599 file su 600 arrivano al 2026. I nomi falliti **non hanno affatto un file**, quindi non entrano nei portafogli e non possono perdere. Sono i **13,396** mesi-titolo senza serie prezzi qui sotto, ed e' survivorship, non assenza di fallimenti.


### Alfa contro CAPM, FF3, FF4


| portafoglio | modello | alfa mensile | t (NW 6) | N mesi | N titoli medio |
|---|---|---:|---:|---:|---:|
| OPPO | CAPM | +0.695% | +0.77 | 94 | 5 |
| OPPO | FF3 | +1.207% | +1.46 | 94 | 5 |
| OPPO | FF4 | +1.290% | +1.49 | 94 | 5 |
| ROUT | CAPM | +0.272% | +0.49 | 99 | 14 |
| ROUT | FF3 | +0.597% | +1.34 | 99 | 14 |
| ROUT | FF4 | +0.647% | +1.48 | 99 | 14 |
| UNCL | CAPM | -0.166% | -0.41 | 99 | 165 |
| UNCL | FF3 | +0.179% | +0.78 | 99 | 165 |
| UNCL | FF4 | +0.210% | +0.93 | 99 | 165 |
| **OPP−ROUT** | CAPM | +0.521% | +0.61 | 94 | — |
| **OPP−ROUT** | FF3 | +0.657% | +0.76 | 94 | — |
| **OPP−ROUT** | FF4 | +0.714% | +0.79 | 94 | — |

---

# Universo: **ogni acquisto > $0**


## Tutto il corpus, equipesato

**Mesi-titolo scartati perche' la barra non e' un rendimento** (oltre +/-500%, stessa soglia di `backfill_analyse.ARTEFACT`): **17**. Senza questo filtro un solo titolo rotto a maggio 2022 portava la media di 109 nomi a +9.170% e l'alfa UNCL a +98% al mese.

**Uscite per delisting all'ultimo prezzo: 0** — e questo numero non e' una buona notizia. Il meccanismo e' inerte perche' nel campione le serie non finiscono: 599 file su 600 arrivano al 2026. I nomi falliti **non hanno affatto un file**, quindi non entrano nei portafogli e non possono perdere. Sono i **23,710** mesi-titolo senza serie prezzi qui sotto, ed e' survivorship, non assenza di fallimenti.


### Alfa contro CAPM, FF3, FF4


| portafoglio | modello | alfa mensile | t (NW 6) | N mesi | N titoli medio |
|---|---|---:|---:|---:|---:|
| OPPO | CAPM | -0.153% | -0.31 | 99 | 42 |
| OPPO | FF3 | +0.163% | +0.48 | 99 | 42 |
| OPPO | FF4 | +0.229% | +0.69 | 99 | 42 |
| ROUT | CAPM | -0.123% | -0.34 | 99 | 41 |
| ROUT | FF3 | +0.126% | +0.52 | 99 | 41 |
| ROUT | FF4 | +0.157% | +0.63 | 99 | 41 |
| UNCL | CAPM | -0.071% | -0.19 | 99 | 239 |
| UNCL | FF3 | +0.245% | +1.26 | 99 | 239 |
| UNCL | FF4 | +0.279% | +1.43 | 99 | 239 |
| **OPP−ROUT** | CAPM | -0.030% | -0.09 | 99 | — |
| **OPP−ROUT** | FF3 | +0.038% | +0.11 | 99 | — |
| **OPP−ROUT** | FF4 | +0.072% | +0.22 | 99 | — |

## Almeno due compratori opportunistici distinti nel mese

Il taglio sotto-2e9 non e' applicabile; quello sul **numero di compratori** non richiede la capitalizzazione ed e' costruito. Cambia solo OPP: ROUT e UNCL sono ripetuti perche' il confronto OPP−ROUT abbia senso.

**Mesi-titolo scartati perche' la barra non e' un rendimento** (oltre +/-500%, stessa soglia di `backfill_analyse.ARTEFACT`): **17**. Senza questo filtro un solo titolo rotto a maggio 2022 portava la media di 109 nomi a +9.170% e l'alfa UNCL a +98% al mese.

**Uscite per delisting all'ultimo prezzo: 0** — e questo numero non e' una buona notizia. Il meccanismo e' inerte perche' nel campione le serie non finiscono: 599 file su 600 arrivano al 2026. I nomi falliti **non hanno affatto un file**, quindi non entrano nei portafogli e non possono perdere. Sono i **21,378** mesi-titolo senza serie prezzi qui sotto, ed e' survivorship, non assenza di fallimenti.


### Alfa contro CAPM, FF3, FF4


| portafoglio | modello | alfa mensile | t (NW 6) | N mesi | N titoli medio |
|---|---|---:|---:|---:|---:|
| OPPO | CAPM | +0.977% | +1.49 | 99 | 9 |
| OPPO | FF3 | +1.360% | +2.27 | 99 | 9 |
| OPPO | FF4 | +1.444% | +2.41 | 99 | 9 |
| ROUT | CAPM | -0.123% | -0.34 | 99 | 41 |
| ROUT | FF3 | +0.126% | +0.52 | 99 | 41 |
| ROUT | FF4 | +0.157% | +0.63 | 99 | 41 |
| UNCL | CAPM | -0.071% | -0.19 | 99 | 239 |
| UNCL | FF3 | +0.245% | +1.26 | 99 | 239 |
| UNCL | FF4 | +0.279% | +1.43 | 99 | 239 |
| **OPP−ROUT** | CAPM | +1.100% | +1.95 | 99 | — |
| **OPP−ROUT** | FF3 | +1.235% | +2.23 | 99 | — |
| **OPP−ROUT** | FF4 | +1.286% | +2.37 | 99 | — |

---

## Contro l'aspettativa scritta prima

Alfa FF4 mensile, con t Newey-West, per i due universi. La colonna a destra e' quella che la domanda ha aperto: **cosa cambia togliendo il filtro da $25.000**.


| | atteso | >= $25.000 | ogni acquisto > $0 |
|---|---|---|---|
| alfa(OPP) | > 0 | +0.611%, t=+1.32 | +0.229%, t=+0.69 |
| alfa(ROUT) | ≈ 0 | +0.647%, t=+1.48 | +0.157%, t=+0.63 |
| **OPP − ROUT** | > 0 | -0.037%, t=-0.07 | +0.072%, t=+0.22 |
| *titoli/mese, OPP* | | 21 | 42 |
| *titoli/mese, ROUT* | | 14 | 41 |
| *errore std. dello spread* | | 0.50% | 0.32% |

**Il risultato centrale di CMP non si replica in nessuno dei due universi.** La distinzione fra opportunistici e routine — che nel paper e' l'intera tesi — non separa: i due portafogli rendono la stessa cosa e la loro differenza resta indistinguibile da zero anche con l'universo raddoppiato.


### La potenza del test, che e' cambiata

Un alfa non significativo puo' voler dire due cose molto diverse — l'effetto non c'e', oppure il test non lo vedrebbe comunque — e la differenza si misura.


| | >= $25.000 | ogni acquisto > $0 |
|---|---:|---:|
| errore standard dello spread | 0.50% al mese | **0.32%** |
| effetto minimo rilevabile a 2σ | 1.01% al mese | **0.65%** |
| spread riportato da CMP | ~0,8% | ~0,8% |
| il test lo vedrebbe? | **no** | **si'** |

**Ed e' qui che togliere il filtro cambia la conclusione, non il risultato.** Con la soglia a $25.000 il test non aveva la potenza per vedere l'effetto di CMP: serviva 1.01% al mese e il paper ne riporta 0,8. Il documento poteva solo dire "non riesco a misurarlo".


Raddoppiando l'universo — 450,974 record contro 233,820, e i portafogli passano da 21 e 14 titoli al mese a 42 e 41 — l'errore standard scende a 0.32% e la soglia di rilevabilita' a **0.65% al mese**, cioe' **sotto** lo spread che CMP riporta. Il test adesso vedrebbe un effetto di quella grandezza.


E non lo vede: **+0.072% al mese, t = +0.22**.


Questo e' un risultato piu' forte di quello del primo giro, e va detto con la stessa prudenza: **non e' una smentita di CMP**, perche' le deviazioni elencate in cima restano tutte — periodo 2018-2026 contro 1986-2007, prezzi per ticker, nessun peso VW, e soprattutto il survivorship, che qui toglie 23,710 mesi-titolo e non toglie a caso. E' invece un'affermazione precisa su questi dati: **con la potenza per vedere l'effetto, su questo periodo e questo universo, l'effetto non c'e'**.


---

Alfa mensili in percentuale. Errori standard Newey-West con 6 ritardi. I fattori vengono dalla Ken French Data Library, scaricati in `data/ff/`.

