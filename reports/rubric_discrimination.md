# Il rubric discrimina? — tabelle

Descrittivo. Nessuna soglia, nessuna raccomandazione, nessun giudizio sul fatto che il rubric funzioni. La lettura e' tua.

Osservazioni: **342,962**, di cui con serie prezzi **184,741** (53.9%).


## 1. Rendimento in eccesso per bucket di score_partial

La colonna **dd>=25%** e' la quota di osservazioni del bucket che erano oltre il 25% dai massimi, e **dd mediano** la profondita' mediana. Servono a distinguere un gradiente di punteggio da un gradiente di drawdown: finche' il criterio assegnava un punto i due erano legati per costruzione.

| bucket | N | dd>=25% | dd mediano |
|---|---:|---:|---:|
| score 0-1 | 55,703 | 39.5% | 18.7% |
| score 2-3 | 75,273 | 44.9% | 21.7% |
| score 4-5 | 33,339 | 54.0% | 28.0% |
| score 6-7 | 13,480 | 59.8% | 32.7% |

### Orizzonte 6m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| score 0-1              | 55,044 | -1.60% | +1.03% | -17.13% | +13.22% | +76.7% | 38 |
| score 2-3              | 74,222 | -1.61% | +1.46% | -18.35% | +13.81% | +2.6% | 76 |
| score 4-5              | 32,890 | -3.36% | -0.19% | -22.38% | +14.01% | +3.6% | 101 |
| score 6-7              | 13,286 | -5.01% | -1.33% | -26.17% | +13.74% | +0.8% | 21 |
| **tutti**              | 175,442 | -2.14% | +0.80% | -19.21% | +13.63% | +25.9% | 236 |

### Orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| score 0-1              | 52,182 | -2.68% | +1.50% | -26.27% | +19.58% | +49.9% | 146 |
| score 2-3              | 70,207 | -2.89% | +2.22% | -27.57% | +20.32% | +6.9% | 266 |
| score 4-5              | 30,846 | -5.61% | +0.53% | -35.11% | +21.09% | +6.6% | 159 |
| score 6-7              | 12,318 | -6.73% | +0.50% | -37.33% | +21.58% | +8.0% | 89 |
| **tutti**              | 165,553 | -3.52% | +1.55% | -29.24% | +20.32% | +20.5% | 660 |

## 2. Split temporale: calibrazione contro verifica

Se un andamento esiste solo nel primo periodo, non esiste.


### 2015-2021 (calibrazione), orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| score 0-1              | 32,089 | -0.93% | +3.18% | -22.71% | +20.60% | +6.0% | 104 |
| score 2-3              | 39,921 | -0.60% | +4.00% | -24.06% | +21.48% | +8.8% | 165 |
| score 4-5              | 17,277 | -1.73% | +5.67% | -30.16% | +24.32% | +15.0% | 130 |
| score 6-7              | 6,692 | -2.82% | +4.16% | -33.77% | +23.89% | +12.8% | 52 |
| **tutti**              | 95,979 | -1.04% | +4.03% | -25.13% | +21.76% | +9.3% | 451 |

### 2022-2026 (verifica), orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| score 0-1              | 20,093 | -6.04% | -1.18% | -32.29% | +17.67% | +120.1% | 42 |
| score 2-3              | 30,286 | -6.04% | -0.12% | -32.14% | +18.39% | +4.4% | 101 |
| score 4-5              | 13,569 | -10.62% | -5.97% | -41.31% | +16.21% | -4.1% | 29 |
| score 6-7              | 5,626 | -12.25% | -3.85% | -41.45% | +19.04% | +2.3% | 37 |
| **tutti**              | 69,574 | -7.33% | -1.87% | -34.67% | +17.82% | +36.0% | 209 |

## 3. Contributo marginale di ciascun componente

Rendimento in eccesso a 12 mesi condizionato al fatto che quel componente abbia assegnato punti, contro il resto.

| componente | N con punti | mediana con | N senza | mediana senza | scarto |
|---|---:|---:|---:|---:|---:|
| buyer_quality | 123,027 | -3.94% | 42,526 | -2.51% | -1.43 pp |
| cluster | 47,035 | -4.47% | 118,518 | -3.23% | -1.24 pp |
| role | 70,242 | -4.70% | 95,311 | -2.71% | -2.00 pp |
| size | 80,807 | -3.44% | 84,746 | -3.64% | +0.20 pp |

## 3b. Il criterio drawdown, isolato per intensita'

La soglia del rubric e' 25%: sotto non assegna punti, sopra ne assegna 1. Le prime due bande sono quindi il gruppo di controllo.


### tutto il periodo, orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-20% (non segna)      | 76,486 | -0.32% | +1.82% | -18.49% | +17.27% | +4.0% | 157 |
| 20-25% (non segna)     | 12,777 | -4.38% | -1.10% | -26.65% | +17.82% | +0.3% | 20 |
| 25-40%                 | 30,704 | -6.17% | -0.45% | -33.75% | +21.45% | +2.6% | 101 |
| 40-60%                 | 26,578 | -9.49% | +3.58% | -41.61% | +30.00% | +6.7% | 88 |
| oltre 60%              | 19,008 | -19.94% | +2.66% | -57.66% | +40.70% | +148.4% | 294 |
| **senza drawdown noto** | 0 | — | — | — | — | — | — |

### 2015-2021, orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-20% (non segna)      | 50,168 | +1.19% | +3.46% | -16.35% | +18.53% | +6.3% | 128 |
| 20-25% (non segna)     | 7,407 | -3.45% | -0.29% | -25.86% | +19.59% | +1.8% | 16 |
| 25-40%                 | 16,824 | -4.92% | +0.61% | -32.41% | +22.92% | +5.5% | 82 |
| 40-60%                 | 13,757 | -5.89% | +7.13% | -39.12% | +34.38% | +12.0% | 68 |
| oltre 60%              | 7,823 | -13.98% | +13.95% | -53.61% | +58.59% | +38.4% | 157 |
| **senza drawdown noto** | 0 | — | — | — | — | — | — |

### 2022-2026, orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0-20% (non segna)      | 26,318 | -3.17% | -1.29% | -22.27% | +14.65% | -0.4% | 29 |
| 20-25% (non segna)     | 5,370 | -5.72% | -2.22% | -28.24% | +15.45% | -1.6% | 4 |
| 25-40%                 | 13,880 | -7.69% | -1.72% | -35.43% | +19.35% | -0.8% | 19 |
| 40-60%                 | 12,821 | -12.84% | -0.22% | -44.09% | +24.94% | +1.0% | 20 |
| oltre 60%              | 11,185 | -23.49% | -5.17% | -60.85% | +28.90% | +225.3% | 137 |
| **senza drawdown noto** | 0 | — | — | — | — | — | — |

## 3c. Il componente `size`, e il suo sotto-criterio

`size` e' l'unico criterio con un input umano: con `comp.json` compilato misura l'acquisto contro il compenso in contanti; senza, misura di quanto l'acquisto ha fatto crescere la posizione. Nel replay il compenso non ha storia, quindi **ogni** osservazione del corpus e' passata dal proxy — ed e' l'unico posto dove il proxy si puo' guardare da solo.


### Il taglio in vigore, orizzonte 12m

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| punto assegnato        | 80,807 | -3.44% | +1.20% | -30.19% | +20.58% | +6.7% | 389 |
| nessun punto           | 84,746 | -3.64% | +1.88% | -28.37% | +20.02% | +33.6% | 271 |
| **tutti**              | 165,553 | -3.52% | +1.55% | -29.24% | +20.32% | +20.5% | 660 |

Scarto sulla mediana: **+0.20 pp** su 165,553 osservazioni. Il taglio separa due gruppi che rendono praticamente uguale.


### Il sotto-criterio `nuova posizione`, orizzonte 12m

Il punto va a ogni aumento di posizione >= 25% **e** a chi crea la posizione da zero. Quest'ultimo caso e' un aumento infinito, quindi non ha un quintile: va guardato a se'. Sotto, i quintili della variazione percentuale e la banda `nuova posizione` accanto.

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1  0.0% - 2.7%        | 27,120 | -4.92% | +1.64% | -30.63% | +19.34% | +6.7% | 101 |
| Q2  2.7% - 8.5%        | 27,120 | -3.76% | +2.16% | -28.15% | +19.86% | +92.9% | 84 |
| Q3  8.5% - 22.2%       | 27,120 | -2.58% | +1.57% | -26.23% | +20.38% | +4.3% | 68 |
| Q4  22.2% - 64.1%      | 27,120 | -2.04% | +3.31% | -27.27% | +22.25% | +6.7% | 97 |
| Q5  64.1% - 56,715,100% | 27,120 | -3.79% | +0.53% | -32.38% | +20.55% | +8.9% | 189 |
| **nuova posizione**    | 29,795 | -4.17% | +0.26% | -30.63% | +19.15% | +5.0% | 121 |

**Il sotto-criterio va nella direzione sbagliata.** `nuova posizione` rende **-4.17%** in mediana, contro **-2.04%** del quintile centrale migliore: -2.13 pp peggio, e sotto quattro quintili su cinque. Il rubric gli assegna il punto pieno.


### Classificazione

**Piatto, con sotto-criterio in direzione sbagliata.** Il criterio nel suo complesso non separa (lo scarto sopra). Il sotto-criterio `nuova posizione` decide da solo il **37%** dei punti assegnati, e quelle osservazioni rendono meno della banda centrale.

Non e' una smentita del criterio come e' scritto: `size` misura il **rapporto** acquisto/compenso, e quel rapporto non esiste in nessuna delle osservazioni del corpus. Cio' che e' misurato qui e' il proxy in uso, non il criterio previsto. Stratificazione per ruolo del compratore, robustezza e costo del controllo per capitalizzazione: `reports/size_component_test.md`.


## 4. Due predicati di bilancio (definiti, non validati)

Applicati con XBRL point-in-time, registrati senza escludere nulla. Sono predicati **definiti per questa misura, non validati**: la tabella e' descrittiva, su dati sovrapposti e senza pre-registrazione, e non dice che uno dei due funzioni come filtro. *(Copia pubblica: nel testo originale il primo era descritto come blocco e il secondo come declassato ad advisory; qui si tiene solo la misura.)*

| | N | mediana | media trim | p25 | p75 | media grezza | scartati |
|---|---:|---:|---:|---:|---:|---:|---:|
| NO_EBITDA_WITH_NET_DEBT vero  | 7,985 | -18.01% | -0.73% | -54.31% | +30.50% | +16.0% | 118 |
| NO_EBITDA_WITH_NET_DEBT falso | 147,520 | -3.55% | +1.92% | -29.40% | +21.44% | +22.2% | 537 |
|   NO_EBITDA_WITH_NET_DEBT          | 7,985 | -18.01% | -0.73% | -54.31% | +30.50% | +16.0% | 118 |
|   NEGATIVE_EQUITY_LEVERED          | 1,263 | -3.30% | +9.11% | -40.03% | +32.77% | +13.0% | 7 |

`NEGATIVE_EQUITY_LEVERED` taglia trasversalmente le altre due righe: un nome puo' averlo vero insieme all'altro predicato, oppure da solo. Il suo scarto rispetto alla riga «falso» e' quasi nullo: non separa niente.


Osservazioni senza XBRL utilizzabile: 23,609 (6.9%). Per loro nessuno dei due predicati si puo' calcolare.


## 5. Survivorship — la distribuzione dei mancanti

Se i mancanti si concentrano su uno degli estremi, tutto quanto sopra e' distorto in quella direzione.

| bucket | osservazioni | senza prezzi | quota |
|---|---:|---:|---:|
| score 0-1 | 109,396 | 51,336 | 46.9% |
| score 2-3 | 142,014 | 64,185 | 45.2% |
| score 4-5 | 65,595 | 30,903 | 47.1% |
| score 6-7 | 25,957 | 11,797 | 45.4% |
| **totale** | 342,962 | 158,221 | 46.1% |

La quota di mancanti **decresce in modo monotono al crescere dello score**: 45.9% nei bucket bassi contro 45.4% in quelli alti.

Un ticker senza serie prezzi e' quasi sempre un delisting, cioe' un esito pessimo. I bucket bassi perdono quindi una quota molto maggiore dei propri disastri rispetto ai bucket alti, e i loro rendimenti misurati sono **distorti verso l'alto** piu' di quanto lo siano quelli dei bucket alti. Qualunque confronto fra bucket nelle sezioni 1-3 eredita questa asimmetria.

Lo `0.0%` del bucket 8+ va guardato con sospetto prima che con sollievo: 2.433 osservazioni senza un solo ticker mancante e' un risultato che merita una verifica indipendente, non una spiegazione.


Motivi registrati:

- `no price series` — 158,221
- `horizon beyond available history` — 12,238
- `no price at one end` — 6,946
- `series ends early (delisted?)` — 4

## 5b. Componenti ricostruiti, e l'artefatto che c'era nel bucket alto

**Tre componenti e mezzo su sei.** Il rubric ha oggi sei criteri: il drawdown e' stato rimosso dopo questo stesso backfill. Di quei sei, il replay ricostruisce `buyer_quality`, `cluster` e `role` per intero, e `size` **solo a meta'** -- assegna fino a 2 punti confrontando l'acquisto con il compenso annuo in `comp.json`, che e' mantenuto a mano e senza storia, quindi il ramo non scatta mai e resta il fallback da 1 punto. `coverage` e `specialist_overlap` restano nulli.

La scala di `score_partial` e' quindi **0-7**, contro un massimo live di 11. Non e' il rubric, e' la sua parte ricostruibile.

**L'artefatto che c'era prima.** Nella versione precedente di questo report il bucket piu' alto non aveva un solo ticker mancante, e l'ipotesi benigna era strutturale. Non lo era: il punteggio massimo conteneva obbligatoriamente il punto del drawdown, che si poteva assegnare solo con una serie prezzi, quindi **appartenere a quel bucket presupponeva avere i prezzi** e lo 0% era meccanico. Con il criterio rimosso quel legame non esiste piu', ed e' la ragione per cui la sezione 5 va riletta su questi numeri e non su quelli di prima.


## 6. LIMITI


**Due componenti su sette non sono ricostruiti.** `coverage` e
`specialist_overlap` non hanno una fonte point-in-time: yfinance restituisce il
numero di analisti solo di oggi, e la watchlist non ha storia. Non sono stati
inventati: valgono `null`, e `score_partial` somma i cinque ricostruibili. Ogni
riga porta `partial_rubric: true`. Il rubric misurato qui **non e' il rubric a 12
punti**, e' la sua parte ricostruibile su 9.

**Le osservazioni non sono indipendenti.** Lo stesso cluster genera una riga ogni
lunedi' per tutta la finestra di 60 giorni, quindi fino a nove righe descrivono
lo stesso evento con rendimenti forward quasi sovrapposti. Gli N delle tabelle
sono **gonfiati** e qualunque test di significativita' standard su questi numeri
e' invalido. Non ne e' stato calcolato nessuno.

**Survivorship residua.** I nomi delistati spariscono da yfinance e sono
sistematicamente i peggiori. La sezione 5 misura quanti sono e come si
distribuiscono, ma non li recupera: il rendimento vero di quei nomi non e' zero,
e' quello che non abbiamo.

**La storia CMP e' troncata prima del 2018.** Il corpus parte da 2015Q1 e la
classificazione routine/opportunistic guarda tre anni indietro, quindi le
osservazioni fino al 2018 vedono meno acquisti precedenti di quanti ce ne siano
stati e classificano gli insider come piu' opportunistici del vero. Le righe
interessate portano `history_truncated: true`.

**Cadenza settimanale.** Le osservazioni sono ai lunedi'. Un cluster nato di
martedi' viene visto sei giorni dopo, con un prezzo di ingresso diverso da quello
che avrebbe avuto la pipeline live.

**Il prezzo e' Adj Close.** Split e dividendi sono corretti, ma il drawdown dal
massimo a 52 settimane e' calcolato su serie aggiustata mentre la pipeline live
legge un valore grezzo da yfinance. Le due misure non coincidono esattamente.

**Le medie grezze non sono utilizzabili; le mediane si.** Le serie prezzi di
yfinance contengono discontinuita' non corrette su titoli OTC e delistati: AURX
segna +3.949.900% su sei mesi, che e' un reverse split non aggiustato, non un
rendimento. Ottanta osservazioni superano il +1000%. Bastano a spostare ogni
media di decine di punti lasciando ogni mediana intatta -- si confrontino le due
colonne "media trim" e "media grezza" nella sezione 1. La colonna "scartati"
conta le osservazioni oltre il +/-500% escluse dalla media trimmata. Non sono
state escluse dalle mediane ne' dai conteggi, perche' li' non fanno danno.

**I prezzi sono presi per TICKER, non per CIK.** Su undici anni i simboli vengono
riassegnati: un'osservazione del 2016 su un ticker poi passato a un'altra societa'
riceve i prezzi della societa' sbagliata. Non ho misurato quanto e' frequente e
non ho una mappatura storica ticker-CIK per farlo. E' il difetto residuo piu'
serio dopo il survivorship, e agisce in direzione ignota.

**`score_max_possible` non aggiunge informazione.** E' sempre `score_partial + 3`,
quindi ordina i nomi allo stesso modo. I bucket usano `score_partial`.

