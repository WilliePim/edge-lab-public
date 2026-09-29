# Backtest v1 sul corpus backfill

Descrittivo. Nessuna raccomandazione. La lettura e' tua.


## 0. Cosa i dati permettono, prima dei numeri

| | |
|---|---|
| **prezzi giornalieri** | **si'.** `adj_close` 2014-01 -> 2026-08, 3.582 ticker. La variante stop/target e' quindi inclusa. |
| **capitalizzazione** | **assente ovunque.** `backfill_score.py:242` costruisce `MarketSnapshot(market_cap=None)`. Il benchmark "emittenti sotto 2e9" **non e' costruibile**. |
| **scala del punteggio** | `score_partial`, massimo **7**, non 11. Tutte le righe sono `partial_rubric: true`, mancano `coverage` e `specialist_overlap`. **La soglia 8 e' vuota per costruzione.** |

Il benchmark usato al posto di quello richiesto e' **ogni emittente scorato, prima occorrenza, stesse meccaniche** — cioe' questa stessa strategia a soglia 0. Il corpus non e' filtrato per capitalizzazione mentre la pipeline viva taglia a 2e9: questo backtest gira su un universo **piu' largo** della produzione.


Meccaniche: ingresso al primo `adj_close` **a partire da** `as_of` (non a `as_of`, che e' il prezzo da cui l'osservazione stessa e' costruita); una sola entrata per emittente, alla **prima** osservazione che qualifica; chi smette di quotare esce **all'ultimo prezzo disponibile**.


---

## in-sample 2015-2021


### Rendimenti per orizzonte

Rendimento assoluto (non in eccesso). `hit` e' la quota di posizioni chiuse in positivo. La media e' trimmata oltre +/-500%, come nel resto dei report.


| soglia | N | 12m med | 12m med.a | 12m hit | 24m med | 24m med.a | 24m hit | 36m med | 36m med.a | 36m hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | +4.7% | +8.6% | 56% | +12.9% | +18.4% | 61% | +18.1% | +24.0% | 63% |
| 5 | 989 | +7.2% | +19.4% | 56% | +15.2% | +27.7% | 59% | +19.9% | +29.3% | 60% |
| 6 | 592 | +7.3% | +22.0% | 56% | +15.7% | +30.5% | 60% | +21.8% | +35.7% | 62% |
| 7 | 201 | +3.6% | +21.6% | 53% | +7.1% | +28.8% | 54% | +13.0% | +40.1% | 56% |
| 8 | **0** | — | — | — | — | — | — | — | — | — |

**Survivorship, sull'universo del benchmark:** 2,538 emittenti entrano, **3,396 sono scartati** perche' non esiste una serie prezzi per il loro ticker — il **57% dei candidati** — piu' 0 senza barra utilizzabile all'ingresso. Non e' un campione neutro che manca: sono i falliti e i delistati, e la loro assenza **alza ogni numero di questo documento** di una quantita' non misurata.


La perdita per soglia, perche' se non fosse uniforme il confronto fra le righe sarebbe distorto e non solo il livello:


| soglia | entrano | scartati | perdita |
|---|---:|---:|---:|
| benchmark | 2,538 | 3,396 | 57.2% |
| 5 | 989 | 1,311 | 57.0% |
| 6 | 592 | 765 | 56.4% |
| 7 | 201 | 221 | 52.4% |
| 8 | 0 | 0 | — |

### Portafoglio equipesato, acquisto al segnale, 12m, ribilancio mensile

**Una barra mensile oltre il +/-500% non e' un rendimento** ed e' esclusa, con la stessa costante e per la stessa ragione di `backfill_analyse.ARTEFACT`. Non e' un dettaglio di pulizia: la prima versione di questa tabella le mediava dentro, e **tre singole barre** — BSAI +31.204%, DUSYF +9.900%, FLCX +8.150%, un mese ciascuna — portavano da sole il CAGR del benchmark a +68,6%. Una media equipesata e' esattamente dove una serie rotta fa il danno massimo: viene divisa per N e poi capitalizzata per sempre.


La colonna **CAGR (±100%)** rifa' lo stesso conto scartando anche le barre oltre il +/-100% mensile. Se le due colonne divergono molto, il risultato dipende da poche barre estreme e non dalla strategia.


| soglia | N | CAGR | CAGR (±100%) | max drawdown | anni positivi | totale | barre scartate |
|---|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | +16.5% | +9.7% | -23.7% | 6/7 | +184.7% | 7 |
| 5 | 989 | +20.2% | +12.5% | -25.7% | 6/7 | +252.6% | 3 |
| 6 | 592 | +20.1% | +12.9% | -28.3% | 6/7 | +249.0% | 1 |
| 7 | 201 | -1.0% | -3.2% | -57.9% | 3/7 | -6.6% | 0 |
| 8 | 0 | — | — | — | — | — | — |

### Variante: comprare e tenere 12 mesi, **senza ribilanciare**

Stesse posizioni e stesso periodo di detenzione della tabella sopra. L'unica differenza e' cosa succede a un vincitore mentre lo si tiene: il ribilancio mensile lo rivende a peso uguale ogni mese e rimpingua i perdenti, qui lo si lascia stare e compone. I pesi quindi derivano, e il rendimento mensile e' pesato per valore fra le posizioni presenti in **entrambi** i mesi — entrate e uscite spostano capitale, non performance.


Una posizione il cui rendimento a 12 mesi supera gia' il +/-500% e' esclusa del tutto, non limitata mese per mese: senza ribilancio una serie rotta non fa una punta e passa, si prende il libro e non lo restituisce piu'.


| soglia | N | CAGR senza ribilancio | CAGR con ribilancio | max drawdown | anni positivi | totale | posizioni escluse |
|---|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,529 | +11.5% | +16.5% | -26.9% | 4/7 | +111.2% | 9 |
| 5 | 984 | +10.4% | +20.2% | -33.6% | 4/7 | +96.3% | 5 |
| 6 | 588 | +10.8% | +20.1% | -43.5% | 5/7 | +101.3% | 4 |
| 7 | 200 | -6.5% | -1.0% | -72.6% | 3/7 | -36.8% | 1 |
| 8 | 0 | — | — | — | — | — | — |

**Tenere senza ribilanciare e' peggio ovunque**, sul rendimento e sul drawdown insieme, e non di poco. Non e' un paradosso: su titoli con deriva mediana vicina a zero e volatilita' enorme, resettare i pesi ogni mese vende meccanicamente cio' che e' salito e ricompra cio' che e' sceso, e su una popolazione che torna verso la media quello e' un guadagno reale. Lasciar correre concentra invece il libro su ciò che è già salito, che è precisamente cio' che poi scende.


Il che toglie ancora terreno alla lettura ottimista: **una parte del vantaggio del portafoglio ribilanciato non e' selezione, e' raccolta di volatilita'** — la si otterrebbe da qualunque paniere ugualmente volatile, senza guardare un solo Form 4.


### Variante stop -25% / target +75%, orizzonte 12m

Stop e target verificati **sulla chiusura**: `adj_close` non porta massimo e minimo di giornata, quindi una barra che ha attraversato lo stop e ha chiuso sopra qui non esce. La variante e' ottimistica di quel tanto, e non e' modellato.


| soglia | N | mediana | media | hit | stop | target | tenuti | delistati |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | -0.1% | +6.9% | 50% | 41% | 14% | 45% | 1% |
| 5 | 989 | -2.3% | +11.2% | 49% | 45% | 21% | 34% | 1% |
| 6 | 592 | -3.9% | +11.4% | 48% | 46% | 23% | 29% | 2% |
| 7 | 201 | -5.8% | +11.2% | 46% | 47% | 22% | 30% | 0% |
| 8 | 0 | — | — | — | — | — | — | — |

---

## holdout 2022-2026


### Rendimenti per orizzonte

Rendimento assoluto (non in eccesso). `hit` e' la quota di posizioni chiuse in positivo. La media e' trimmata oltre +/-500%, come nel resto dei report.


| soglia | N | 12m med | 12m med.a | 12m hit | 24m med | 24m med.a | 24m hit | 36m med | 36m med.a | 36m hit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | +0.6% | +3.6% | 50% | +1.6% | +10.5% | 52% | +2.6% | +11.9% | 54% |
| 5 | 565 | -1.1% | +4.9% | 49% | +2.8% | +14.6% | 54% | +4.0% | +17.0% | 54% |
| 6 | 418 | +0.1% | +7.9% | 50% | +1.2% | +12.5% | 52% | +3.4% | +17.9% | 53% |
| 7 | 230 | +1.1% | +17.0% | 53% | +11.3% | +24.4% | 57% | +9.3% | +27.3% | 57% |
| 8 | **0** | — | — | — | — | — | — | — | — | — |

**Survivorship, sull'universo del benchmark:** 726 emittenti entrano, **442 sono scartati** perche' non esiste una serie prezzi per il loro ticker — il **38% dei candidati** — piu' 0 senza barra utilizzabile all'ingresso. Non e' un campione neutro che manca: sono i falliti e i delistati, e la loro assenza **alza ogni numero di questo documento** di una quantita' non misurata.


La perdita per soglia, perche' se non fosse uniforme il confronto fra le righe sarebbe distorto e non solo il livello:


| soglia | entrano | scartati | perdita |
|---|---:|---:|---:|
| benchmark | 726 | 442 | 37.8% |
| 5 | 565 | 239 | 29.7% |
| 6 | 418 | 184 | 30.6% |
| 7 | 230 | 112 | 32.7% |
| 8 | 0 | 0 | — |

### Portafoglio equipesato, acquisto al segnale, 12m, ribilancio mensile

**Una barra mensile oltre il +/-500% non e' un rendimento** ed e' esclusa, con la stessa costante e per la stessa ragione di `backfill_analyse.ARTEFACT`. Non e' un dettaglio di pulizia: la prima versione di questa tabella le mediava dentro, e **tre singole barre** — BSAI +31.204%, DUSYF +9.900%, FLCX +8.150%, un mese ciascuna — portavano da sole il CAGR del benchmark a +68,6%. Una media equipesata e' esattamente dove una serie rotta fa il danno massimo: viene divisa per N e poi capitalizzata per sempre.


La colonna **CAGR (±100%)** rifa' lo stesso conto scartando anche le barre oltre il +/-100% mensile. Se le due colonne divergono molto, il risultato dipende da poche barre estreme e non dalla strategia.


| soglia | N | CAGR | CAGR (±100%) | max drawdown | anni positivi | totale | barre scartate |
|---|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | +3.7% | -8.0% | -26.5% | 4/5 | +18.0% | 8 |
| 5 | 565 | +9.9% | +1.3% | -24.6% | 4/5 | +52.9% | 3 |
| 6 | 418 | +10.9% | +2.9% | -21.4% | 4/5 | +59.5% | 1 |
| 7 | 230 | +12.0% | +4.8% | -21.0% | 4/5 | +66.3% | 0 |
| 8 | 0 | — | — | — | — | — | — |

### Variante: comprare e tenere 12 mesi, **senza ribilanciare**

Stesse posizioni e stesso periodo di detenzione della tabella sopra. L'unica differenza e' cosa succede a un vincitore mentre lo si tiene: il ribilancio mensile lo rivende a peso uguale ogni mese e rimpingua i perdenti, qui lo si lascia stare e compone. I pesi quindi derivano, e il rendimento mensile e' pesato per valore fra le posizioni presenti in **entrambi** i mesi — entrate e uscite spostano capitale, non performance.


Una posizione il cui rendimento a 12 mesi supera gia' il +/-500% e' esclusa del tutto, non limitata mese per mese: senza ribilancio una serie rotta non fa una punta e passa, si prende il libro e non lo restituisce piu'.


| soglia | N | CAGR senza ribilancio | CAGR con ribilancio | max drawdown | anni positivi | totale | posizioni escluse |
|---|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 721 | -2.6% | +3.7% | -40.7% | 3/5 | -11.3% | 5 |
| 5 | 560 | -1.0% | +9.9% | -31.9% | 3/5 | -4.5% | 5 |
| 6 | 415 | +3.8% | +10.9% | -26.8% | 3/5 | +18.3% | 3 |
| 7 | 230 | +11.0% | +12.0% | -27.6% | 4/5 | +60.1% | 0 |
| 8 | 0 | — | — | — | — | — | — |

**Tenere senza ribilanciare e' peggio ovunque**, sul rendimento e sul drawdown insieme, e non di poco. Non e' un paradosso: su titoli con deriva mediana vicina a zero e volatilita' enorme, resettare i pesi ogni mese vende meccanicamente cio' che e' salito e ricompra cio' che e' sceso, e su una popolazione che torna verso la media quello e' un guadagno reale. Lasciar correre concentra invece il libro su ciò che è già salito, che è precisamente cio' che poi scende.


Il che toglie ancora terreno alla lettura ottimista: **una parte del vantaggio del portafoglio ribilanciato non e' selezione, e' raccolta di volatilita'** — la si otterrebbe da qualunque paniere ugualmente volatile, senza guardare un solo Form 4.


### Variante stop -25% / target +75%, orizzonte 12m

Stop e target verificati **sulla chiusura**: `adj_close` non porta massimo e minimo di giornata, quindi una barra che ha attraversato lo stop e ha chiuso sopra qui non esce. La variante e' ottimistica di quel tanto, e non e' modellato.


| soglia | N | mediana | media | hit | stop | target | tenuti | delistati |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | -10.5% | +5.9% | 47% | 48% | 17% | 26% | 9% |
| 5 | 565 | -13.2% | +5.3% | 43% | 48% | 15% | 28% | 10% |
| 6 | 418 | -15.6% | +4.0% | 42% | 49% | 15% | 27% | 9% |
| 7 | 230 | -4.9% | +9.0% | 47% | 46% | 19% | 25% | 10% |
| 8 | 0 | — | — | — | — | — | — | — |

---

## Perche' questo backtest sembra contraddire gli altri report

`rubric_discrimination.md` mostra che al salire del punteggio il rendimento **in eccesso** peggiora. Qui il portafoglio a soglia alta batte il benchmark nell'holdout. Le due cose non si contraddicono, e la ragione e' la sola che conta in tutto questo documento.


Due candidati sono stati provati ed esclusi. **Non e' la deduplica**: tenendo una sola osservazione per emittente il gradiente in eccesso resta negativo e anzi si accentua (−3,73 / −6,41 / −7,79 / −9,60 per soglia 0 / 5 / 6 / 7). E' invece **assoluto contro eccesso**:


| soglia | N | rendimento assoluto 12m | in eccesso | differenza = mercato |
|---|---:|---:|---:|---:|
| benchmark | 3.300 | **+3,14%** | −3,73% | +6,88 pp |
| 5 | 1.476 | **+3,12%** | −6,41% | +9,53 pp |
| 6 | 927 | **+3,50%** | −7,79% | +11,28 pp |
| 7 | 385 | **+3,26%** | −9,60% | +12,86 pp |

*(mediane, prima occorrenza per emittente, tutto il periodo)*


**Il rendimento assoluto e' piatto**: da +3,12% a +3,50% fra soglia 0 e soglia 7, nessun ordine. Cio' che cresce in modo monotono e' la terza colonna, cioe' **quanto e' salito il mercato nei dodici mesi dopo il segnale**: +6,88 pp al benchmark, +12,86 pp a soglia 7.


Detto in chiaro: **il rubric non sceglie titoli migliori, sceglie momenti migliori.** Segna piu' spesso dopo le discese — cosa che ha senso, gli insider comprano nei ribassi, e il criterio drawdown premiava letteralmente questo — e a quei momenti segue una ripresa di mercato. Il portafoglio qui sopra misura rendimenti assoluti, quindi incassa quella ripresa e la fa sembrare selezione.


Rispetto al mercato che si porta dietro, i nomi a punteggio alto fanno **peggio**, e tanto peggio quanto piu' alto e' il punteggio. Il CAGR crescente per soglia nell'holdout e' beta di mercato comprato al momento giusto, non alpha di selezione.


---

## Limiti che questo backtest non supera

- **Survivorship.** I nomi senza serie prezzi non entrano. Non e' neutro: sono i falliti e i delistati, e la loro assenza alza ogni numero qui sopra.

- **Prezzi per ticker, non per CIK.** Su undici anni i simboli vengono riassegnati; `rubric_discrimination.md` stima le collisioni al 2,53% e le dichiara il difetto residuo piu' serio dopo il survivorship, in direzione ignota.

- **Nessun costo.** Ne' commissioni ne' spread ne' impatto. Su nomi sotto i 2 miliardi con acquisti insider lo spread non e' trascurabile, e il ribilancio mensile lo paga ogni mese.

- **Universo piu' largo della produzione**, perche' il cap a 2e9 non e' applicabile senza capitalizzazione.

- **Scala 0-7, non 0-11.** Le soglie non sono confrontabili con quelle di un run vero.

