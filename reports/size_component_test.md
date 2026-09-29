# Il componente `size` discrimina? — tabelle

Descrittivo. Nessuna soglia, nessuna raccomandazione. La lettura e' tua.

Osservazioni unite a un rendimento: **342,962**. Senza riga di panel corrispondente: 0.

Base del criterio nel replay: `{'holdings_increase': 342962}` — comp.json non ha storia, quindi ogni osservazione del corpus e' passata dal proxy.


## 1. Importo in dollari dell'acquisto piu' grosso

Osservazioni con importo e rendimento 12m: **165,553**.


### Orizzonte 6m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1  < $50k             | 33,105 | -0.97% | +2.56% | -16.53% | +14.04% | +4.1% | 39 |
| Q2  $50k - $100k       | 33,111 | -1.37% | +2.03% | -17.60% | +13.62% | +3.4% | 59 |
| Q3  $100k - $210k      | 33,111 | -1.33% | +1.38% | -17.53% | +13.93% | +8.3% | 35 |
| Q4  $210k - $706k      | 33,113 | -2.20% | +0.69% | -18.71% | +14.15% | +2.9% | 47 |
| Q5  >= $706k           | 33,113 | -3.08% | -0.71% | -23.44% | +13.93% | +120.0% | 47 |
| **tutti**              | 165,553 | -1.72% | +1.19% | -18.69% | +13.95% | +27.7% | 227 |

### Orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1  < $50k             | 33,105 | -2.18% | +3.28% | -25.21% | +20.85% | +9.5% | 154 |
| Q2  $50k - $100k       | 33,111 | -2.35% | +2.04% | -27.50% | +19.05% | +7.0% | 169 |
| Q3  $100k - $210k      | 33,111 | -2.88% | +2.19% | -27.55% | +20.27% | +6.0% | 106 |
| Q4  $210k - $706k      | 33,113 | -4.12% | +1.73% | -29.39% | +21.65% | +6.4% | 129 |
| Q5  >= $706k           | 33,113 | -6.74% | -1.49% | -36.63% | +19.91% | +73.5% | 102 |
| **tutti**              | 165,553 | -3.52% | +1.55% | -29.24% | +20.32% | +20.5% | 660 |

Ampiezza delle bande, per leggere le tabelle sopra:

| bucket | N | importo mediano | importo max |
|---|---:|---:|---:|
| Q1  < $50k | 33,105 | $36k | $50k |
| Q2  $50k - $100k | 33,111 | $73k | $100k |
| Q3  $100k - $210k | 33,111 | $138k | $210k |
| Q4  $210k - $706k | 33,113 | $344k | $706k |
| Q5  >= $706k | 33,113 | $2.2M | $2.5e+15 |

## 2. Variazione percentuale della posizione

`nuova posizione` e' la posizione creata da zero: l'aumento e' infinito, non mancante, e tenerlo in un bucket a se' e' l'unico modo di non confonderlo con un dato assente.

Con percentuale: **135,600**. Nuova posizione: **29,795**. Assente: **158**.


### Orizzonte 6m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1  < 2.7%             | 27,033 | -1.97% | +2.31% | -18.32% | +13.89% | +2.5% | 8 |
| Q2  2.7% - 8.5%        | 27,142 | -2.17% | +1.48% | -18.59% | +13.75% | +147.7% | 21 |
| Q3  8.5% - 22.2%       | 27,118 | -1.01% | +1.43% | -17.61% | +14.28% | +9.3% | 30 |
| Q4  22.2% - 64.1%      | 27,181 | -0.77% | +2.16% | -17.57% | +14.94% | +3.9% | 46 |
| Q5  >= 64.1%           | 27,126 | -2.00% | +0.04% | -20.80% | +13.94% | +4.5% | 75 |
| nuova posizione        | 29,795 | -2.37% | -0.16% | -19.35% | +12.93% | +1.1% | 47 |
| assente                | 158 | +0.57% | +1.35% | -11.50% | +14.95% | +1.4% | 0 |
| **tutti**              | 165,553 | -1.72% | +1.19% | -18.69% | +13.95% | +27.7% | 227 |

### Orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1  < 2.7%             | 27,033 | -4.94% | +1.63% | -30.68% | +19.37% | +6.7% | 101 |
| Q2  2.7% - 8.5%        | 27,142 | -3.72% | +2.19% | -28.11% | +19.93% | +92.9% | 84 |
| Q3  8.5% - 22.2%       | 27,118 | -2.68% | +1.52% | -26.26% | +20.26% | +4.3% | 68 |
| Q4  22.2% - 64.1%      | 27,181 | -2.02% | +3.32% | -27.24% | +22.28% | +6.7% | 97 |
| Q5  >= 64.1%           | 27,126 | -3.79% | +0.53% | -32.37% | +20.55% | +8.9% | 189 |
| nuova posizione        | 29,795 | -4.17% | +0.26% | -30.63% | +19.15% | +5.0% | 121 |
| assente                | 158 | -0.64% | -5.58% | -36.07% | +10.97% | -5.6% | 0 |
| **tutti**              | 165,553 | -3.52% | +1.55% | -29.24% | +20.32% | +20.5% | 660 |

## 3. Il taglio che il rubric usa oggi, per riferimento

Il punto va a `nuova posizione` e a ogni aumento >= 25%. Questa e' la partizione in vigore, non una proposta.


### Orizzonte 6m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| punto assegnato        | 85,451 | -2.27% | +0.20% | -19.88% | +13.59% | +2.3% | 154 |
| nessun punto           | 89,991 | -2.01% | +1.38% | -18.69% | +13.67% | +48.3% | 82 |
| **tutti**              | 175,442 | -2.14% | +0.80% | -19.21% | +13.63% | +25.9% | 236 |

### Orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| punto assegnato        | 80,807 | -3.44% | +1.20% | -30.19% | +20.58% | +6.7% | 389 |
| nessun punto           | 84,746 | -3.64% | +1.88% | -28.37% | +20.02% | +33.6% | 271 |
| **tutti**              | 165,553 | -3.52% | +1.55% | -29.24% | +20.32% | +20.5% | 660 |

## 4. Il gradiente dell'importo regge?

`largest_value` e' contaminato in coda: il massimo del quintile alto e' dell'ordine di 10^18 dollari, che non e' un acquisto ma una serie prezzi rotta. I quintili sono per rango, quindi un artefatto sposta il confine del bucket alto e non gli altri quattro -- ma il confine e' proprio dove il gradiente si misura. Sotto, la mediana a 12m dei cinque quintili ricalcolata su sottoinsiemi via via piu' puliti, e poi separatamente sui due periodi.

| sottoinsieme | Q1 | Q2 | Q3 | Q4 | Q5 | N/bucket | Q5-Q1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| tutti | -2.19% | -2.35% | -2.88% | -4.12% | -6.74% | 33,110 | -4.55pp |
| importo <= $50M | -2.21% | -2.15% | -3.02% | -4.25% | -6.63% | 32,760 | -4.43pp |
| importo <= $10M | -2.07% | -2.06% | -3.60% | -3.55% | -5.40% | 31,794 | -3.33pp |
| | | | | | | | |
| 2015-2021 (calibrazione) | +0.31% | +0.92% | -1.18% | -1.64% | -4.43% | 19,195 | -4.74pp |
| 2022-2026 (verifica) | -6.63% | -6.73% | -6.48% | -8.26% | -8.76% | 13,914 | -2.13pp |

## 5. Le due domande

**L'importo discrimina?** Si', in modo monotono e **nella direzione opposta a quella che il criterio presuppone**: piu' grande e' l'acquisto, peggiore e' il rendimento a 12 mesi. Lo scarto fra quintile estremo e quintile basso e' dell'ordine di 4 punti percentuali sulla mediana, sopravvive all'esclusione degli artefatti e all'esclusione delle penny stock, ma **si dimezza fuori campione** e perde la monotonia nel periodo di verifica. Per lo standard che questo repo si e' gia' dato -- se un andamento esiste solo nel primo periodo, non esiste -- il gradiente non e' smentito, ma non e' nemmeno confermato.

**La percentuale discrimina?** No. I cinque quintili non sono monotoni: la mediana migliora fino al quarto quintile e poi peggiora, e `nuova posizione` -- a cui il rubric assegna il punto -- sta peggio della banda centrale. Lo scarto fra il quintile migliore e il peggiore e' di circa 3 pp senza ordine, contro i 4 pp ordinati dell'importo.

**Il taglio in vigore** (sezione 3) separa due gruppi che rendono praticamente uguale: 0,20 pp di differenza sulla mediana a 12 mesi, su 165 mila osservazioni. E' lo stesso numero che `rubric_discrimination.md` riporta nella tabella dei contributi marginali.

**Cio' che queste tabelle NON possono dire.** Il criterio non misura ne' l'importo ne' la percentuale: misura il **rapporto fra l'acquisto e il compenso in contanti**. Nel corpus quel rapporto non esiste in nessuna delle 342.962 osservazioni, perche' comp.json non ha storia e il replay e' passato interamente dal proxy. Un rapporto normalizza la dimensione dell'impresa, che e' il candidato piu' ovvio a spiegare perche' gli acquisti grandi in valore assoluto rendano meno. Il segno negativo dell'importo quindi **non trasferisce** al criterio, e nessuna misura su questo corpus puo' validare o smentire il rapporto.

Non e' misurato qui: la capitalizzazione, che il panel non porta. Senza di essa l'effetto dimensione resta un confondente ipotizzato e non controllato.


## 6. L'importo, stratificato per ruolo del compratore

Il ruolo e' quello del compratore PIU' GROSSO, perche' e' l'unico che il criterio guarda. Viene dal Form 4 (`reportingOwnerRelationship`), non da un'inferenza: `parse.py` lo riduce a CFO / CEO / COO / Officer / 10% Owner / Director / Other.

`entita'` non e' un ruolo del Form 4 e non puo' esserlo: un fondo che detiene oltre il 10% e' marcato `10% Owner` esattamente come una persona fisica. La riga qui sotto e' un'**euristica sul nome** (suffissi LP, LLC, Inc, Trust, Partners, Capital, Management...), quindi e' indicativa e non un dato.


| strato | Q1 | Q2 | Q3 | Q4 | Q5 | N/bucket | Q5-Q1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **officer** (CEO+CFO+COO+Officer) | -2.10% | -5.02% | -4.67% | -4.81% | -4.92% | 11,232 | -2.82pp |
| &nbsp;&nbsp;CEO | -5.68% | -5.41% | -6.35% | -5.33% | -5.91% | 6,050 | -0.24pp |
| &nbsp;&nbsp;CFO | +1.67% | +2.12% | -5.96% | -9.30% | -5.91% | 1,420 | -7.58pp |
| &nbsp;&nbsp;Officer (altro) | -2.44% | -4.96% | -0.93% | -2.34% | -2.89% | 3,417 | -0.44pp |
| &nbsp;&nbsp;COO | -2.75% | -8.69% | +5.31% | +7.22% | -1.05% | 344 | +1.70pp |
| **director** | -2.07% | -0.50% | -1.61% | -2.72% | -3.45% | 16,919 | -1.38pp |
| **10% owner** | -10.41% | -8.33% | -7.95% | -12.50% | -13.01% | 4,032 | -2.60pp |
| **Other** | +0.60% | +2.03% | +0.71% | -1.79% | -10.19% | 926 | -10.78pp |
| *euristica: nome societario* | -11.54% | -8.45% | -12.56% | -11.68% | -13.56% | 3,141 | -2.02pp |
| *euristica: persona fisica* | -2.05% | -1.80% | -3.19% | -3.13% | -4.63% | 29,968 | -2.58pp |
| combinazione: officer **e** 10% owner nel cluster | -18.01% | -18.51% | -14.97% | -12.39% | -22.14% | 919 | -4.13pp |
| combinazione: solo officer nel cluster | -3.04% | -3.78% | -4.34% | -3.62% | -5.33% | 13,129 | -2.29pp |
| combinazione: solo 10% owner nel cluster | -8.90% | -6.86% | -7.16% | -11.52% | -12.27% | 3,760 | -3.37pp |

Lo stesso, spezzato sui due periodi. Solo gli estremi e lo scarto: il dettaglio dei quintili intermedi non cambia la lettura.

| strato | periodo | Q1 | Q5 | N/bucket | Q5-Q1 |
|---|---|---:|---:|---:|---:|
| **officer** (CEO+CFO+COO+Officer) | 2015-2021 | +0.77% | -2.09% | 6,335 | -2.86pp |
| **officer** (CEO+CFO+COO+Officer) | 2022-2026 | -6.73% | -8.97% | 4,897 | -2.24pp |
| &nbsp;&nbsp;CEO | 2015-2021 | -1.33% | -3.82% | 3,299 | -2.49pp |
| &nbsp;&nbsp;CEO | 2022-2026 | -10.43% | -8.11% | 2,751 | +2.32pp |
| &nbsp;&nbsp;CFO | 2015-2021 | +5.43% | -1.64% | 749 | -7.07pp |
| &nbsp;&nbsp;CFO | 2022-2026 | -2.74% | -10.62% | 670 | -7.88pp |
| &nbsp;&nbsp;Officer (altro) | 2015-2021 | -0.67% | +0.83% | 2,089 | +1.50pp |
| &nbsp;&nbsp;Officer (altro) | 2022-2026 | -8.33% | -8.69% | 1,328 | -0.36pp |
| &nbsp;&nbsp;COO | 2015-2021 | — | — | (troppo piccolo) | — |
| &nbsp;&nbsp;COO | 2022-2026 | — | — | (troppo piccolo) | — |
| **director** | 2015-2021 | -0.32% | -1.59% | 10,133 | -1.26pp |
| **director** | 2022-2026 | -5.11% | -6.05% | 6,786 | -0.94pp |
| **10% owner** | 2015-2021 | -2.23% | -16.40% | 2,178 | -14.16pp |
| **10% owner** | 2022-2026 | -19.16% | -11.29% | 1,854 | +7.87pp |
| **Other** | 2015-2021 | +2.62% | -5.25% | 549 | -7.87pp |
| **Other** | 2022-2026 | -6.54% | -7.09% | 376 | -0.55pp |
| *euristica: nome societario* | 2015-2021 | -3.77% | -11.62% | 1,667 | -7.85pp |
| *euristica: nome societario* | 2022-2026 | -17.52% | -13.55% | 1,474 | +3.97pp |
| *euristica: persona fisica* | 2015-2021 | +0.33% | -2.89% | 17,528 | -3.21pp |
| *euristica: persona fisica* | 2022-2026 | -6.02% | -7.56% | 12,440 | -1.54pp |
| combinazione: officer **e** 10% owner nel cluster | 2015-2021 | -12.62% | -23.42% | 564 | -10.80pp |
| combinazione: officer **e** 10% owner nel cluster | 2022-2026 | -23.46% | -19.10% | 355 | +4.37pp |
| combinazione: solo officer nel cluster | 2015-2021 | -0.15% | -2.54% | 7,472 | -2.39pp |
| combinazione: solo officer nel cluster | 2022-2026 | -7.94% | -9.96% | 5,656 | -2.03pp |
| combinazione: solo 10% owner nel cluster | 2015-2021 | +0.74% | -15.32% | 1,981 | -16.05pp |
| combinazione: solo 10% owner nel cluster | 2022-2026 | -19.60% | -10.10% | 1,778 | +9.51pp |

### La domanda secca: fra i soli officer, l'importo discrimina?

Lo scarto Q5-Q1 puo' nascondere un gradino invece di un gradiente, quindi accanto c'e' anche **Q5-Q2**: se il primo quintile e' un caso a se' e il resto e' piatto, il secondo scarto lo dice e il primo no.

| | Q1 | Q2 | Q3 | Q4 | Q5 | N | Q5-Q1 | Q5-Q2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| officer, tutto il periodo | -2.10% | -5.02% | -4.67% | -4.81% | -4.92% | 56,162 | -2.82pp | +0.10pp |
| officer, 2015-2021 | +0.77% | -0.27% | -1.21% | -1.40% | -2.09% | 31,676 | -2.86pp | -1.82pp |
| officer, 2022-2026 | -6.73% | -11.66% | -9.93% | -9.20% | -8.97% | 24,486 | -2.24pp | +2.68pp |
| CEO, tutto il periodo | -5.68% | -5.41% | -6.35% | -5.33% | -5.91% | 30,253 | -0.24pp | -0.50pp |
| CEO, 2015-2021 | -1.33% | +0.95% | -3.06% | -2.03% | -3.82% | 16,497 | -2.49pp | -4.78pp |
| CEO, 2022-2026 | -10.43% | -14.92% | -11.80% | -12.03% | -8.11% | 13,756 | +2.32pp | +6.81pp |

**No.** Su 56,162 osservazioni il cui compratore piu' grosso e' un officer, quello che sembra un gradiente e' **un solo gradino fra il quintile piu' basso e tutti gli altri**: da Q2 in poi le mediane stanno entro un decimo di punto l'una dall'altra (+0.10 pp fra Q2 e Q5). E il gradino non regge fuori campione -- nel 2022-2026 l'ordine sopra Q1 si **inverte**, con Q5 migliore di Q2.

Fra i soli CEO -- 30,253 osservazioni, lo strato pulito piu' grande, perche' e' un ruolo unico per emittente e non un insieme di titoli -- non c'e' nemmeno il gradino: i cinque quintili stanno tutti fra il -5% e il -6,4%.

Il gradiente della sezione 1 vive quindi **fuori** dai ruoli che il criterio vuole premiare. Gli strati che lo portano sono `10% owner` e i nomi societari -- ed e' proprio li' che il segno si capovolge fra i due periodi, il che li rende inservibili in entrambe le direzioni.


## 7. Il contatore del cluster e gli affiliati

Il conteggio non usa il nome del proprietario. Unisce i CIK che **condividono un accession number** -- cioe' che hanno firmato lo stesso Form 4 -- e li unisce transitivamente, poi conta i gruppi. Il codice e' `cluster.py:34-72`, e `max_window_buyers` (`cluster.py:105`) conta indici di gruppo, non CIK.

Verificato su `2026-08-31.jsonl`: la replica dell'algoritmo riproduce `distinct_buyers` su **341/341** cluster.

Il dedup fa lavoro vero: **53** dei 341 cluster contengono almeno un gruppo con piu' di un firmatario. Dimensione dei gruppi: `{1: 470, 2: 22, 3: 20, 4: 5, 5: 7, 6: 5, 7: 3, 8: 1}`.


**La risposta e' quindi: dipende da come depositano.** Affiliati che co-firmano lo stesso Form 4 contano **uno**. Affiliati che depositano Form 4 **separati** contano **uno ciascuno**, perche' niente li lega: il nome non viene mai guardato.


### Esempio reale dal run del 2026-08-31

**John Hancock GA Mortgage Trust** (CIK 1742952), score 4/11. Note: `+2 opportunistic buyer`, `+2 4 distinct buyers within 30d`.

| proprietario | CIK | accession | data | ruolo | valore |
|---|---|---|---|---|---:|
| Manufacturers Life Insurance Co (Bermuda Branch) | 1833683 | `0001833683-26-000016` | 2026-07-15 | 10% Owner | $36,586,000 |
| Manufacturers Life Reinsurance Ltd | 1765496 | `0001765496-26-000015` | 2026-07-15 | 10% Owner | $12,999,314 |
| Manufacturers Life Reinsurance Ltd | 1765496 | `0001765496-26-000016` | 2026-07-31 | 10% Owner | $3,999,935 |
| Manulife (International) Ltd | 1765518 | `0001765518-26-000004` | 2026-07-15 | 10% Owner | $21,998,838 |
| Manulife (International) Ltd | 1765518 | `0001765518-26-000005` | 2026-07-31 | 10% Owner | $3,999,935 |
| Manulife (Singapore) Pte. Ltd. | 1837478 | `0001837478-26-000015` | 2026-07-15 | 10% Owner | $6,999,630 |
| Manulife (Singapore) Pte. Ltd. | 1837478 | `0001837478-26-000016` | 2026-07-31 | 10% Owner | $1,999,968 |

Quattro controllate dello stesso gruppo -- John Hancock e' il marchio statunitense di Manulife -- comprano lo stesso emittente negli stessi due giorni, ognuna con il proprio Form 4. Nessun accession condiviso, quindi quattro gruppi, quindi `+2 4 distinct buyers within 30d`: il punto pieno del criterio cluster per una sola decisione di allocazione. Meta' dei 4 punti di questo emittente viene da li'.

Da notare che il ruolo e' `10% Owner` su tutte e quattro le righe: l'informazione per riconoscere il caso c'e' gia' nel record, non viene usata dal contatore.


---

Rendimenti in eccesso. La colonna "scartati" conta le osservazioni oltre +/-500% escluse dalla sola media trimmata; mediane e percentili le contengono tutte.

