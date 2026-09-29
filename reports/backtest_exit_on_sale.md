# Tenere fino a quando un CEO o un CFO vende — tabelle

Descrittivo. Nessuna raccomandazione. La lettura e' tua.


## 0. Da dove vengono le vendite

Il corpus del backfill **non contiene nessuna vendita**: `backfill_fetch.py:191` tiene solo `TRANS_CODE == "P"`, quindi tutte e 237.833 le righe sono acquisti. Le vendite erano pero' gia' su disco, non lette, dentro i 45 ZIP trimestrali `form345` scaricati allora — **questo lavoro non ha toccato la rete**.


Indicizzate **268,502** vendite di mercato (codice S, disposizione D) da chi ha un titolo di CEO o CFO sul Form 4, su **4,962** emittenti.


> **L'uscita usa la data di DEPOSITO, non quella di transazione.** Una vendita non e' azionabile prima di essere pubblica, e il Form 4 concede due giorni lavorativi. Uscire sulla data di transazione sarebbe un lookahead piccolo ma sistematico, e per giunta favorevole: venderebbe prima che il mercato abbia visto la notizia.


> **Cosa conta come vendita:** qualunque vendita di mercato di un CEO o CFO, non la liquidazione dell'intera posizione.


## 0b. Pianificate contro non pianificate

La maggior parte delle vendite di un dirigente non e' un giudizio sul titolo: e' vesting, liquidita', diversificazione, quasi sempre dentro un piano 10b5-1 deciso mesi prima. Una regola che esce su quelle esce su un calendario, non su un'informazione. Il documento le separa e misura entrambe le versioni.


Un deposito e' **pianificato** se la casella `AFF10B5ONE` e' spuntata, oppure se una sua footnote contiene 10b5-1 — stesso regex di `parse._PLAN_RE`, con cui sono stati classificati gli acquisti del corpus.


**La casella esiste solo dal 2023**, e questo cadrebbe esattamente sullo split fra i due periodi. La tabella serve a controllare che la classificazione non sia un artefatto del periodo: il regex sulle footnote trova una quota stabile in tutti gli anni, e la casella converge sugli stessi livelli quando arriva.


| anno | vendite CEO/CFO | pianificate |
|---|---:|---:|
| 2015 | 21,084 | 56.8% |
| 2016 | 16,909 | 49.6% |
| 2017 | 18,669 | 55.8% |
| 2018 | 21,451 | 69.3% |
| 2019 | 19,709 | 68.3% |
| 2020 | 26,044 | 73.6% |
| 2021 | 38,003 | 71.9% |
| 2022 | 20,089 | 67.4% |
| 2023 | 23,143 | 69.5% |
| 2024 | 29,550 | 72.2% |
| 2025 | 26,755 | 76.1% |
| 2026 | 7,096 | 69.2% |

**268,502** righe di transazione, di cui **68%** pianificate. Ridotte alle date distinte per emittente — che e' cio' che la regola di uscita usa — restano **90,620** date con almeno una vendita CEO/CFO e **35,673** con almeno una vendita **non pianificata** (39% delle date).


---

# Uscita su: ogni vendita CEO/CFO


---

## in-sample 2015-2021


| soglia | N | mediana | media | hit | giorni tenuti (mediana) | esce su vendita | mai venduto | delistato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | +13.4% | +29.8% | 65% | 921 | 65% | 35% | 0% |
| 5 | 989 | +27.9% | +45.7% | 65% | 1,206 | 63% | 37% | 0% |
| 6 | 592 | +37.0% | +55.9% | 66% | 1,455 | 58% | 42% | 0% |
| 7 | 201 | +29.8% | +53.2% | 64% | 1,697 | 55% | 45% | 0% |
| 8 | 0 | — | — | — | — | — | — | — |

### Il confronto onesto: la regola di uscita, non la durata

La tabella sopra **non** dice che la regola funziona. Dice che tiene le posizioni per anni: mediana di 921-1.697 giorni in-sample, e un terzo abbondante non vende mai e arriva alla fine dei dati. Confrontarla con dodici mesi fissi paragona quattro anni di mercato con uno, e in un mercato che sale vince sempre il piu' lungo.


Due correzioni. **Annualizzato** rende comparabili durate diverse. E il controllo giusto per una regola di USCITA non e' una durata fissa, e' **non uscire affatto**: stesse posizioni, stesso ingresso, tenute fino all'ultimo prezzo disponibile. Se vendere sul segnale del CEO aggiunge qualcosa, deve battere il non vendere.


| soglia | N | uscita su vendita | mai uscire | differenza | annualizz. uscita | annualizz. mai uscire |
|---|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | +13.4% | +49.9% | -36.5 pp | +6.8% | +5.1% |
| 5 | 989 | +27.9% | +54.1% | -26.2 pp | +9.8% | +6.3% |
| 6 | 592 | +37.0% | +58.5% | -21.6 pp | +9.9% | +7.0% |
| 7 | 201 | +29.8% | +42.9% | -13.1 pp | +8.4% | +5.0% |
| 8 | 0 | — | — | — | — | — |

La colonna **differenza** e' il valore della regola di uscita a parita' di ingresso. Le due colonne annualizzate dicono se quel valore sopravvive una volta tolta la durata.


---

## holdout 2022-2026


| soglia | N | mediana | media | hit | giorni tenuti (mediana) | esce su vendita | mai venduto | delistato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | +2.6% | +5.1% | 54% | 502 | 31% | 69% | 0% |
| 5 | 565 | +4.6% | +15.5% | 58% | 536 | 31% | 69% | 0% |
| 6 | 418 | +5.1% | +16.3% | 57% | 556 | 32% | 68% | 0% |
| 7 | 230 | +9.7% | +23.6% | 60% | 549 | 29% | 71% | 0% |
| 8 | 0 | — | — | — | — | — | — | — |

### Il confronto onesto: la regola di uscita, non la durata

La tabella sopra **non** dice che la regola funziona. Dice che tiene le posizioni per anni: mediana di 921-1.697 giorni in-sample, e un terzo abbondante non vende mai e arriva alla fine dei dati. Confrontarla con dodici mesi fissi paragona quattro anni di mercato con uno, e in un mercato che sale vince sempre il piu' lungo.


Due correzioni. **Annualizzato** rende comparabili durate diverse. E il controllo giusto per una regola di USCITA non e' una durata fissa, e' **non uscire affatto**: stesse posizioni, stesso ingresso, tenute fino all'ultimo prezzo disponibile. Se vendere sul segnale del CEO aggiunge qualcosa, deve battere il non vendere.


| soglia | N | uscita su vendita | mai uscire | differenza | annualizz. uscita | annualizz. mai uscire |
|---|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | +2.6% | +3.5% | -0.9 pp | +2.6% | +3.0% |
| 5 | 565 | +4.6% | +9.4% | -4.8 pp | +4.4% | +4.6% |
| 6 | 418 | +5.1% | +8.2% | -3.1 pp | +4.3% | +4.5% |
| 7 | 230 | +9.7% | +15.6% | -5.9 pp | +6.1% | +6.9% |
| 8 | 0 | — | — | — | — | — |

La colonna **differenza** e' il valore della regola di uscita a parita' di ingresso. Le due colonne annualizzate dicono se quel valore sopravvive una volta tolta la durata.


---

# Uscita su: solo vendite NON pianificate


---

## in-sample 2015-2021


| soglia | N | mediana | media | hit | giorni tenuti (mediana) | esce su vendita | mai venduto | delistato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | +15.6% | +33.1% | 64% | 1,613 | 57% | 43% | 0% |
| 5 | 989 | +31.4% | +48.7% | 64% | 1,726 | 54% | 46% | 0% |
| 6 | 592 | +37.4% | +56.9% | 64% | 1,781 | 49% | 51% | 0% |
| 7 | 201 | +28.3% | +52.7% | 60% | 1,845 | 45% | 55% | 0% |
| 8 | 0 | — | — | — | — | — | — | — |

### Il confronto onesto: la regola di uscita, non la durata

La tabella sopra **non** dice che la regola funziona. Dice che tiene le posizioni per anni: mediana di 921-1.697 giorni in-sample, e un terzo abbondante non vende mai e arriva alla fine dei dati. Confrontarla con dodici mesi fissi paragona quattro anni di mercato con uno, e in un mercato che sale vince sempre il piu' lungo.


Due correzioni. **Annualizzato** rende comparabili durate diverse. E il controllo giusto per una regola di USCITA non e' una durata fissa, e' **non uscire affatto**: stesse posizioni, stesso ingresso, tenute fino all'ultimo prezzo disponibile. Se vendere sul segnale del CEO aggiunge qualcosa, deve battere il non vendere.


| soglia | N | uscita su vendita | mai uscire | differenza | annualizz. uscita | annualizz. mai uscire |
|---|---:|---:|---:|---:|---:|---:|
| **benchmark** | 2,538 | +15.6% | +49.9% | -34.3 pp | +6.2% | +5.1% |
| 5 | 989 | +31.4% | +54.1% | -22.7 pp | +8.9% | +6.3% |
| 6 | 592 | +37.4% | +58.5% | -21.2 pp | +8.7% | +7.0% |
| 7 | 201 | +28.3% | +42.9% | -14.5 pp | +7.3% | +5.0% |
| 8 | 0 | — | — | — | — | — |

La colonna **differenza** e' il valore della regola di uscita a parita' di ingresso. Le due colonne annualizzate dicono se quel valore sopravvive una volta tolta la durata.


---

## holdout 2022-2026


| soglia | N | mediana | media | hit | giorni tenuti (mediana) | esce su vendita | mai venduto | delistato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | +2.5% | +7.3% | 53% | 564 | 25% | 75% | 0% |
| 5 | 565 | +6.4% | +16.9% | 58% | 578 | 25% | 75% | 0% |
| 6 | 418 | +4.7% | +17.3% | 55% | 619 | 28% | 72% | 0% |
| 7 | 230 | +11.2% | +23.5% | 59% | 567 | 24% | 76% | 0% |
| 8 | 0 | — | — | — | — | — | — | — |

### Il confronto onesto: la regola di uscita, non la durata

La tabella sopra **non** dice che la regola funziona. Dice che tiene le posizioni per anni: mediana di 921-1.697 giorni in-sample, e un terzo abbondante non vende mai e arriva alla fine dei dati. Confrontarla con dodici mesi fissi paragona quattro anni di mercato con uno, e in un mercato che sale vince sempre il piu' lungo.


Due correzioni. **Annualizzato** rende comparabili durate diverse. E il controllo giusto per una regola di USCITA non e' una durata fissa, e' **non uscire affatto**: stesse posizioni, stesso ingresso, tenute fino all'ultimo prezzo disponibile. Se vendere sul segnale del CEO aggiunge qualcosa, deve battere il non vendere.


| soglia | N | uscita su vendita | mai uscire | differenza | annualizz. uscita | annualizz. mai uscire |
|---|---:|---:|---:|---:|---:|---:|
| **benchmark** | 726 | +2.5% | +3.5% | -1.0 pp | +2.3% | +3.0% |
| 5 | 565 | +6.4% | +9.4% | -3.0 pp | +4.5% | +4.6% |
| 6 | 418 | +4.7% | +8.2% | -3.5 pp | +3.5% | +4.5% |
| 7 | 230 | +11.2% | +15.6% | -4.4 pp | +6.1% | +6.9% |
| 8 | 0 | — | — | — | — | — |

La colonna **differenza** e' il valore della regola di uscita a parita' di ingresso. Le due colonne annualizzate dicono se quel valore sopravvive una volta tolta la durata.


---

## Risposta

**La regola sembra ottima e non lo e'.** Contro dodici mesi fissi guadagna fino a +29,7 pp di mediana, ma quel confronto e' senza senso: la regola tiene le posizioni **921-1.697 giorni** in mediana e in un terzo abbondante dei casi non vende mai. Sta paragonando quattro anni di mercato con uno.


Controllata contro **non uscire affatto** — stesse posizioni, stesso ingresso, tenute fino all'ultimo prezzo disponibile — la regola **perde** su tutte le righe e in entrambi i periodi: da −0,9 a −36,5 pp di rendimento totale. Uscire alla vendita del CEO significa lasciare sul tavolo quello che il titolo fa dopo.


**L'unica cosa che restava in piedi era il rendimento annualizzato**, e non replica.


| | uscita su vendita | mai uscire |
|---|---:|---:|
| in-sample, soglia 5 | **+9,8%** | +6,3% |
| in-sample, soglia 6 | **+9,9%** | +7,0% |
| holdout, soglia 5 | +4,4% | **+4,6%** |
| holdout, soglia 6 | +4,3% | **+4,5%** |

In-sample uscire rende ~3 punti annui in piu' a parita' di tempo investito: il capitale si libera e non resta fermo. Nell'holdout il vantaggio **sparisce e si inverte leggermente**. Per lo standard che questo repo usa da sempre — se un andamento esiste solo nel primo periodo, non esiste — la regola non e' dimostrata.


### E filtrando alle sole vendite non pianificate?

Era l'ipotesi naturale: la maggior parte delle vendite di un dirigente e' vesting o liquidita' dentro un piano deciso mesi prima, quindi uscire su quelle e' uscire su un calendario. Togliendole, il 39% delle date resta, e la regola diventa piu' selettiva — esce nel 24-28% dei casi nell'holdout invece del 29-32%.


**Non aiuta. Peggiora.**


| annualizzato | ogni vendita | solo non pianificate | mai uscire |
|---|---:|---:|---:|
| in-sample, soglia 5 | **+9,8%** | +8,9% | +6,3% |
| in-sample, soglia 6 | **+9,9%** | +8,7% | +7,0% |
| holdout, soglia 5 | +4,4% | +4,5% | **+4,6%** |
| holdout, soglia 6 | +4,3% | +3,5% | **+4,5%** |
| holdout, soglia 7 | +6,1% | +6,1% | **+6,9%** |

In-sample il filtro **toglie** circa un punto annuo rispetto all'uscire su qualunque vendita. Nell'holdout le tre colonne sono indistinguibili e vince comunque il non uscire. Il vantaggio in-sample dell'uscita, gia' fragile, non migliora affinando la definizione del segnale: **si comporta come rumore raffinato, non come segnale diluito**.


Questo chiude anche la spiegazione comoda del paragrafo precedente. Non e' che la regola falliva perche' mescolava vendite di routine con vendite informate: separate le due, il risultato non cambia. La vendita di un CEO, pianificata o no, **non dice quando uscire da una posizione aperta sul suo acquisto**.


Cio' che resta da provare non e' un filtro migliore sulle vendite, ma un'uscita di natura diversa — sul deterioramento dei fondamentali, sulla diluizione, o su nessuna uscita affatto, che e' la colonna che vince quasi ovunque qui sopra.

