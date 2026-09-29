# Il mancante di `market_cap` è ignorabile? — test in due passi

Sostituisce la soglia dell'80%. Non conta **quanto** manca ma **se** cio' che manca somiglia a cio' che c'e'.


## Passo 1 — definire prima l'universo

**681 CIK esclusi**: 665 che non depositano alcun 10-K o 10-Q — il 97% senza nemmeno un codice SIC, cioe' entita' nominate come emittente su un Form 4 senza essere registranti periodici — piu' le shell / blank check. Non possono avere una capitalizzazione e non appartengono a uno studio di societa' operative. Escluderli **prima** del confronto non e' selezione a posteriori: e' dire quale popolazione si sta misurando.


### Prima della restrizione


| | N | mediana | p25 | p75 |
|---|---:|---:|---:|---:|
| coperti | 139,354 | -11.64% | -40.40% | +18.11% |
| scoperti | 45,356 | -8.11% | -30.29% | +11.49% |
| **scarto mediano** | | **-3.53 pp** | | |

KS: D = **0.0858**, p < 0,001


### Dopo la restrizione


| | N | mediana | p25 | p75 |
|---|---:|---:|---:|---:|
| coperti | 139,354 | -11.64% | -40.40% | +18.11% |
| scoperti | 32,702 | -10.69% | -40.77% | +16.79% |
| **scarto mediano** | | **-0.95 pp** | | |

KS: D = **0.0360**, p < 0,001


**Lo scarto sul rendimento passa da -3.53 pp a -0.95 pp** e il KS da 0.0858 a 0.0360. Osservazioni escluse: 12,654.


## Passo 2 — quanto della copertura spiegano le variabili osservate


Regressione logistica di **coperto** su ruolo, anno, terzile di valore e tipo di filer, IRLS su 172,056 osservazioni.


| | |
|---|---|
| pseudo-R² (McFadden) | **0.475** |
| quota coperta osservata | 81.0% |

Un pseudo-R² di 0.475 dice che quelle quattro variabili spiegano una parte sostanziale della copertura. Se fosse alto, riponderare avrebbe senso; quel che conta comunque e' cosa resta DENTRO le celle.


### Il rendimento dentro ogni cella ruolo × anno

Se la differenza fosse solo composizione, dentro una cella dove ruolo e anno sono fissi coperti e scoperti dovrebbero rendere uguale.


| | |
|---|---|
| celle con N >= 100 da entrambi i lati | **50** |
| scarto mediano **assoluto** per cella | **9.61 pp** |
| scarto mediano **con segno** | **-2.61 pp** |
| celle in cui i coperti rendono **meno** | **30/50** (60%) |

Le dieci celle con lo scarto più grande:


| ruolo | anno | coperti | scoperti | scarto |
|---|---:|---:|---:|---:|
| altro | 2015 | 144 | 106 | **-83.9 pp** |
| CFO | 2019 | 514 | 221 | **-62.0 pp** |
| CFO | 2020 | 687 | 185 | **-42.4 pp** |
| 10% owner | 2014 | 186 | 512 | **-39.8 pp** |
| altro | 2019 | 259 | 520 | **+38.5 pp** |
| 10% owner | 2024 | 4,970 | 1,461 | **-27.2 pp** |
| 10% owner | 2021 | 3,594 | 1,674 | **+27.2 pp** |
| 10% owner | 2023 | 5,909 | 829 | **+25.8 pp** |
| altro | 2021 | 368 | 316 | **+25.1 pp** |
| 10% owner | 2020 | 4,100 | 2,122 | **+22.7 pp** |

| criterio dichiarato | valore | soglia | esito |
|---|---:|---:|---|
| scarto mediano assoluto per cella | **9.61 pp** | < 3 pp | **non passa** |
| celle discordi (|scarto| > 3 pp) | **84%** | < 30% | **non passa** |
| *(lettura alternativa: celle di segno minoritario)* | 40% | | |

### Le due celle indicate: 10% owner 2021 e 2024

Sono le due celle grandi che si contraddicono, +27,2 pp contro −27,2 pp. La quota di CIK con **primo 10-K nei 24 mesi precedenti** dice se la differenza sia composizione di societa' appena quotate — la spiegazione candidata, perche' un emittente nuovo non ha ancora storia XBRL e ha rendimenti piu' dispersi.


| cella | lato | N | mediana | quota primo 10-K < 24 mesi |
|---|---|---:|---:|---:|
| 10% owner 2021 | coperti | 3,594 | -11.84% | **22.5%** |
| 10% owner 2021 | scoperti | 1,674 | -39.04% | **15.2%** |
| 10% owner 2024 | coperti | 4,970 | -23.02% | **9.5%** |
| 10% owner 2024 | scoperti | 1,461 | +4.17% | **21.4%** |

---

## Verdetto

### RESTA NON CORREGGIBILE — ma non per la ragione che l'aggregato suggerisce


I due criteri danno risposte opposte, e la contraddizione **e'** il risultato:


| criterio | valore | esito |
|---|---:|---|
| scarto aggregato dopo restrizione | **-0.95 pp** | passa (< 1 pp) |
| scarto mediano assoluto per cella | **9.61 pp** | **non passa** |
| segno per cella | 30/50 in una direzione | non sistematico |

**L'aggregato e' piccolo perche' le celle si annullano, non perche' siano d'accordo.** Fissati ruolo e anno, coperti e scoperti rendono in modo molto diverso — e la direzione cambia di anno in anno anche su celle grandi: 10% owner nel 2024 e' −27,2 pp su 4.970 contro 1.461 nomi, e nel 2021 e' **+27,2 pp** su 3.594 contro 1.674. Non sono code rumorose: sono migliaia di osservazioni per lato che dicono cose opposte in anni diversi.


E questo e' **peggio** di una distorsione sistematica, non meglio. Uno scarto costante si correggerebbe con uno spostamento; uno che cambia segno con l'anno significa che la copertura e' legata a qualcosa di variabile nel tempo — dimensione, adozione XBRL, appartenenza a un indice — la cui relazione col rendimento dipende dal regime di mercato.


E l'argomento e' piu' forte di quanto sembri, perche' la regressione logistica **funziona**: pseudo-R² **0.475**, cioe' ruolo, anno, taglia e tipo di filer spiegano una parte sostanziale di *chi* e' coperto. Il punto e' che spiegare chi non basta — dentro le celle in cui quelle variabili sono fissate il rendimento differisce lo stesso, e di molto. Un modello di missingness buono sulle covariate e inutile sull'esito e' precisamente il caso in cui riponderare produce una stima **piu'** sicura di se' e altrettanto sbagliata.


### Quale sottogruppo degli scoperti porta la differenza


| sottogruppo degli scoperti | N | mediana | contro i coperti |
|---|---:|---:|---:|
| ruolo: 10% owner | 16,269 | -11.77% | **-0.13 pp** |
| ruolo: director indipendente | 6,497 | -6.91% | **+4.73 pp** |
| ruolo: CEO | 3,763 | -10.07% | **+1.57 pp** |
| ruolo: altri officer | 3,392 | -3.42% | **+8.22 pp** |
| tipo di filer: operativa (dei) | 20,187 | -11.12% | **+0.52 pp** |
| tipo di filer: multi-classe | 8,699 | -11.09% | **+0.55 pp** |
| tipo di filer: operativa (us-gaap) | 3,480 | +5.10% | **+16.74 pp** |
| tipo di filer: operativa | 336 | -61.27% | **-49.63 pp** |
| terzile: alto | 15,452 | -8.89% | **+2.75 pp** |
| terzile: medio | 9,370 | -8.13% | **+3.51 pp** |
| terzile: basso | 7,880 | -11.77% | **-0.13 pp** |

**`role_size_by_marketcap` non e' stato eseguito.**

