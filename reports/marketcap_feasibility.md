# Market cap nel panel: e' ricostruibile? — studio di fattibilita'

**Non scrive nel panel.** Misura se il dato mancante si puo' ottenere, a che costo e con quale copertura.

Il panel porta gia' `price` alla data. Manca solo il numero di azioni, cioe' `dei:EntityCommonStockSharesOutstanding` — il conteggio di copertina di ogni 10-K, 10-Q e 20-F.

Corpus: **342,962** osservazioni su **7,102** CIK emittenti distinti. Campione casuale di **200** CIK (seed `20260831`, riproducibile), che portano con se' **9,270** osservazioni (2.7% del corpus).


> **Point-in-time applicato, non assunto.** Un fatto vale a `as_of` solo se era gia' stato **depositato**: il filtro e' `filed <= as_of`, mai `end`. Il conteggio di copertina di un trimestre chiuso il 30 giugno non e' pubblico fino al 10-Q di agosto, e usarlo a giugno sarebbe esattamente il lookahead che `dilution.py:150` commette oggi.


## 1. Copertura per anno

`dei` e' il tag primario. `+ ripiego` aggiunge `us-gaap:CommonStockSharesOutstanding` per i soli CIK dove il primario manca del tutto — tenuto separato, perche' e' un tag diverso con una definizione diversa e mescolarli in silenzio nasconderebbe quale numero si sta usando.


| anno | osservazioni | `dei` | copertura | + ripiego | copertura |
|---|---:|---:|---:|---:|---:|
| 2015 | 783 | 687 | 87.7% | 687 | 87.7% |
| 2016 | 875 | 750 | 85.7% | 771 | 88.1% |
| 2017 | 823 | 668 | 81.2% | 720 | 87.5% |
| 2018 | 1,071 | 902 | 84.2% | 920 | 85.9% |
| 2019 | 915 | 793 | 86.7% | 808 | 88.3% |
| 2020 | 993 | 774 | 77.9% | 792 | 79.8% |
| 2021 | 860 | 602 | 70.0% | 631 | 73.4% |
| 2022 | 843 | 707 | 83.9% | 728 | 86.4% |
| 2023 | 760 | 665 | 87.5% | 703 | 92.5% |
| 2024 | 614 | 435 | 70.8% | 495 | 80.6% |
| 2025 | 605 | 513 | 84.8% | 528 | 87.3% |
| 2026 | 128 | 97 | 75.8% | 107 | 83.6% |
| **totale** | **9,270** | **7,593** | **81.9%** | **7,890** | **85.1%** |

**Incertezza del campione.** L'unita' di campionamento e' il CIK, non l'osservazione: un solo emittente porta fino a qualche centinaio di righe correlate, quindi un intervallo binomiale su 9,270 osservazioni sarebbe falsamente stretto. Bootstrap a grappoli su 2000 ricampionamenti dei CIK:


| stima | puntuale | IC 95% |
|---|---:|---:|
| solo `dei` | 81.9% | 75.5% – 87.1% |
| con ripiego | 85.1% | 79.5% – 90.0% |

Quota di ricampionamenti in cui il solo `dei` resta **sotto l'80%**: **26.8%**.


## 2. Quanto e' vecchio il dato che si vedrebbe

Due distanze, e servono entrambe. `as_of - end` e' l'eta' del **conteggio**: l'errore che si accetterebbe sul numero di azioni. `as_of - filed` e' da quanto e' **pubblico**: la prova che non si sta guardando nel futuro.


| distanza | mediana | p25 | p75 | p95 | N |
|---|---:|---:|---:|---:|---:|
| `as_of - end` (eta' del conteggio) | 53 gg | 32 gg | 77 gg | 712 gg | 7,593 |
| `as_of - filed` (da quanto e' pubblico) | 46 gg | 25 gg | 69 gg | 712 gg | 7,593 |

Il p95 dice il caso peggiore: **6.5%** delle osservazioni coperte userebbero un conteggio piu' vecchio di un anno. Su un emittente che ha emesso azioni nel frattempo, quella capitalizzazione e' sbagliata di quanto e' stata la diluizione.


## 3. Piu' classi di azioni

**La domanda non si puo' porre come un conteggio di valori multipli.** `companyconcept` e `companyfacts` restituiscono solo i fatti riportati **senza dimensioni**. Un emittente con Classe A e Classe B tagga il conteggio di copertina una volta per classe, sull'asse della classe, e le API scartano tutte quelle righe: il multi-classe non appare come "due valori", appare come **nessun valore**.

Cercare valori fratelli avrebbe quindi trovato zero casi e concluso che non ce ne sono. Il criterio usato qui e' l'unico che i dati permettono: un filer che tagga `dei:EntityPublicFloat` — quindi deposita davvero una copertina strutturata — ma non ha alcun fatto sul numero di azioni.


| | CIK | % del campione | osservazioni | % del campione |
|---|---:|---:|---:|---:|
| senza il tag `dei` | 41 | 20.5% | 1,677 | 18.1% |
| di cui **multi-classe probabile** | 29 | 14.5% | 751 | 8.1% |
| di cui recuperabili col ripiego | 12 | 6.0% | 331 | 3.6% |

E per questi la capitalizzazione **non e' azioni x prezzo**: il `price` del panel e' quello di una classe sola — quella quotata — mentre il conteggio, se si riuscisse a leggerlo, comprende classi che non hanno quel prezzo e spesso non hanno prezzo affatto. Vanno trattati a parte o esclusi, mai sommati alla cieca.


## 4. Costo per l'intero corpus

**282** chiamate in 15 s. Di queste **211** sono state servite dalla cache su disco e **71** sono andate in rete. Il taglio e' a 100 ms: una chiamata che attraversa la rete non puo' scendere sotto i 150 ms che il throttle impone da solo.


La stima usa la **mediana delle sole chiamate di rete**, **0.20 s**. Estrapolare dal tempo totale misurerebbe il filesystem su una cache calda e prometterebbe pochi minuti per un lavoro che a freddo ne richiede dieci volte tanti.


| | |
|---|---|
| CIK da interrogare | 7,102 |
| chiamate per CIK che risponde | 1 |
| chiamate per CIK che non risponde | 3 (primario, ripiego, companyfacts) |
| quota che non risponde | 20.5% |
| **chiamate totali stimate** | **~10,014** |
| throttle del client | 0,15 s (`edgar.py:31`), ~6,7 req/s |
| limite SEC dichiarato | 10 req/s |
| **tempo stimato** | **~33 min** |
| rilanci | quasi gratis: `EdgarClient` mette in cache su disco |

Il throttle non va alzato per questo lavoro: e' lo stesso client che serve la pipeline quotidiana, e un 403 preso qui si propagherebbe li'. `companyfacts` per tutti invece di `companyconcept` eviterebbe il secondo passaggio se un giorno servissero altri tag, al prezzo di molta piu' banda per CIK.


## 5. Conclusione: si arriva all'80%?

**Si', ma di misura e non con il solo tag primario.**


Col solo `dei:EntityCommonStockSharesOutstanding` la copertura point-in-time e' **81.9%**, con intervallo **75.5%–87.1%**: la soglia dell'80% cade **dentro** l'intervallo, e in **26.8%** dei ricampionamenti il risultato e' sotto. Su questo dato la risposta "supera l'80%" non e' distinguibile da "non lo supera".


Aggiungendo il ripiego `us-gaap:CommonStockSharesOutstanding` si sale a **85.1%** (79.5%–90.0%), e li' l'80% e' superato in modo netto.


**Ma la copertura non e' la correttezza.** Restano fuori dal numero sopra tre cose, tutte misurate nelle sezioni precedenti e nessuna risolta:


1. **Il conteggio e' vecchio**: mediana 53 giorni, p95 oltre l'anno. Per un emittente che ha diluito nel frattempo la capitalizzazione ricostruita e' sbagliata esattamente di quanto ha diluito — e la diluizione e' proprio cio' che questo scanner cerca.
2. **I multi-classe sono invisibili**, non assenti: 14.5% dei CIK del campione. Per loro azioni x prezzo non e' la capitalizzazione, e il ripiego che li recupera restituisce un conteggio di una definizione diversa.
3. **`price` nel panel e' rettificato per split, il conteggio di copertina no.** Su una serie di undici anni il disallineamento non e' piccolo, ed e' silenzioso: produce capitalizzazioni plausibili e sbagliate.


Quindi: il dato **si puo' prendere** in circa 33 minuti, e per l'uso a cui serviva — stratificare `size` per fascia di capitalizzazione, non stimare un valore — bande larghe assorbono i primi due problemi. Il terzo no: va verificato prima, su un campione, confrontando la capitalizzazione ricostruita con una fonte indipendente.

