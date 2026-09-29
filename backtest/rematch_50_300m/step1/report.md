# Passo 1 — replica del test originale

Generato da `python backtest/rematch_50_300m/step1_analysis.py`, sull'output di `tools/backtest_event_time.py` invariato (comando al §11 della pre-registrazione). Pre-registrazione `130b0fe`, addendum 1 `e48cfb9`, addendum 2 per il ponte.

Nessuna chiamata a modelli linguistici: token e costo **0**.

## 1. Riproduzione

**RIPRODOTTO** — le righe delle tabelle aggregate del report rigenerato, confrontate carattere per carattere con [il report del 2026-09-01](../../../reports/backtest-event-time-2026-09-01-dilution-50-300M.md).

### (a) tutti gli eventi — identiche

```
| **21 giorni** | 7,785 | +0.85% | -0.55% | +16.99% | 48% | 4.43 | +0.50% – +1.24% |
| **63 giorni** | 7,782 | +2.68% | -1.21% | +32.39% | 47% | 7.31 | +1.94% – +3.37% |
| **126 giorni** | 7,665 | +4.13% | -2.34% | +48.19% | 47% | 7.50 | +3.15% – +5.21% |
```

### (b) un evento per emittente, cooldown 126gg — identiche

```
| **21 giorni** | 3,260 | +0.76% | -0.49% | +16.86% | 48% | 2.58 | +0.17% – +1.36% |
| **63 giorni** | 3,259 | +2.81% | -1.09% | +33.14% | 47% | 4.84 | +1.70% – +3.87% |
| **126 giorni** | 3,213 | +3.50% | -1.94% | +46.07% | 48% | 4.30 | +1.95% – +5.19% |
```

### Aggregato, excess netto del costo — identiche

```
| **21 giorni** | 3,260 | -0.24% | -1.49% | +16.86% | 44% | -0.81 | -0.83% – +0.36% |
| **63 giorni** | 3,259 | +1.81% | -2.09% | +33.14% | 45% | 3.12 | +0.70% – +2.87% |
| **126 giorni** | 3,213 | +2.50% | -2.94% | +46.07% | 46% | 3.07 | +0.95% – +4.19% |
```

## 2. La stessa replica, con l'inferenza clusterizzata

Popolazione: 7,811 eventi in fascia; variante (b) 3,276 eventi su 1,110 emittenti. La t semplice e il bootstrap semplice sono quelli dell'originale; t CR1, IC da t CR1 e bootstrap per emittente sono aggiunti (ADR-002, ADR-014).

### (b) lordo

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **21 sessioni** | 3,260 | +0.76% | -0.49% | 2.58 | 2.61 | 1,105 | +0.17% – +1.36% | +0.19% – +1.33% | +0.20% – +1.35% |
| **63 sessioni** | 3,259 | +2.81% | -1.09% | 4.84 | 5.03 | 1,105 | +1.70% – +3.87% | +1.71% – +3.91% | +1.78% – +3.85% |
| **126 sessioni** | 3,213 | +3.50% | -1.94% | 4.30 | 4.30 | 1,091 | +1.95% – +5.19% | +1.90% – +5.10% | +1.97% – +5.17% |

### (a) lordo

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **21 sessioni** | 7,785 | +0.85% | -0.55% | 4.43 | 3.24 | 1,105 | +0.49% – +1.23% | +0.34% – +1.37% | +0.36% – +1.40% |
| **63 sessioni** | 7,782 | +2.68% | -1.21% | 7.31 | 4.33 | 1,105 | +2.01% – +3.38% | +1.47% – +3.90% | +1.49% – +3.92% |
| **126 sessioni** | 7,665 | +4.13% | -2.34% | 7.50 | 3.50 | 1,092 | +3.07% – +5.27% | +1.82% – +6.44% | +1.99% – +6.69% |

### (b) netto 100bp

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **21 sessioni** | 3,260 | -0.24% | -1.49% | -0.81 | -0.82 | 1,105 | -0.83% – +0.36% | -0.81% – +0.33% | -0.80% – +0.35% |
| **63 sessioni** | 3,259 | +1.81% | -2.09% | 3.12 | 3.24 | 1,105 | +0.70% – +2.87% | +0.71% – +2.91% | +0.78% – +2.85% |
| **126 sessioni** | 3,213 | +2.50% | -2.94% | 3.07 | 3.07 | 1,091 | +0.95% – +4.19% | +0.90% – +4.10% | +0.97% – +4.17% |

## 3. Per anno di deposito — variante (b), 126 sessioni, lordo

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2015** | 218 | +3.25% | +1.16% | 1.88 | 1.86 | 179 | +0.04% – +6.91% | -0.20% – +6.71% | -0.02% – +6.84% |
| **2016** | 195 | +6.68% | +3.47% | 2.92 | 2.85 | 163 | +2.49% – +11.19% | +2.05% – +11.30% | +1.85% – +11.66% |
| **2017** | 197 | +6.09% | +2.35% | 2.20 | 2.20 | 163 | +0.74% – +11.73% | +0.62% – +11.57% | +1.16% – +11.70% |
| **2018** | 209 | +3.16% | +0.42% | 1.58 | 1.55 | 175 | -0.48% – +7.25% | -0.88% – +7.20% | -0.76% – +7.13% |
| **2019** | 227 | +0.44% | -4.87% | 0.19 | 0.18 | 194 | -4.04% – +5.30% | -4.28% – +5.16% | -3.63% – +5.14% |
| **2020** | 376 | +5.27% | -9.57% | 1.68 | 1.66 | 307 | -0.43% – +11.91% | -0.98% – +11.53% | -0.86% – +11.54% |
| **2021** | 246 | +3.88% | +4.90% | 1.61 | 1.58 | 200 | -0.51% – +8.81% | -0.97% – +8.73% | -0.59% – +8.70% |
| **2022** | 402 | +2.31% | -3.40% | 1.07 | 1.06 | 329 | -1.86% – +6.85% | -1.99% – +6.61% | -1.99% – +6.60% |
| **2023** | 415 | +2.31% | -5.50% | 1.00 | 1.02 | 348 | -2.18% – +6.72% | -2.14% – +6.77% | -2.02% – +7.11% |
| **2024** | 339 | +7.14% | +1.79% | 2.45 | 2.43 | 283 | +1.34% – +12.51% | +1.35% – +12.94% | +0.94% – +12.49% |
| **2025** | 351 | +0.19% | -8.99% | 0.06 | 0.06 | 289 | -5.52% – +6.42% | -6.11% – +6.49% | -5.67% – +6.53% |
| **2026** | 38 | -1.23% | -3.44% | -0.16 | -0.16 | 38 | -14.61% – +14.13% | -16.50% – +14.03% | -14.61% – +14.13% |

Sotto 10 emittenti la t con cluster non si calcola.

## 4. Il ponte sul calendario comune

Gli stessi 3,276 eventi della variante (b), 126 sessioni, sulle sessioni IWM con l'ingresso dell'addendum 2: prima barra del titolo dopo il deposito entro 5 sessioni, mai un prezzo anteriore.

| stato | eventi |
|---|---:|
| `OK` | 3,213 |
| `TOO_RECENT` | 42 |
| `NO_SERIES` | 12 |
| `ARTEFACT` | 5 |
| `ENDED_IN_WINDOW` | 2 |
| `NO_ENTRY_BAR` | 2 |

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| originale (barre del titolo) | 3,213 | +3.50% | -1.94% | 4.30 | 4.30 | 1,091 | +1.95% – +5.19% | +1.90% – +5.10% | +1.97% – +5.17% |
| comune, delistati esclusi | 3,213 | +3.50% | -1.94% | 4.30 | 4.30 | 1,091 | +1.95% – +5.19% | +1.90% – +5.10% | +1.97% – +5.17% |
| comune, ultimo prezzo piatto | 3,215 | +3.50% | -1.94% | 4.31 | 4.30 | 1,093 | +2.07% – +5.32% | +1.90% – +5.10% | +1.98% – +5.20% |

### Ponte per anno — calendario comune, ultimo prezzo piatto

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2015** | 218 | +3.25% | +1.16% | 1.88 | 1.86 | 179 | +0.04% – +6.91% | -0.20% – +6.71% | -0.02% – +6.84% |
| **2016** | 195 | +6.68% | +3.47% | 2.92 | 2.85 | 163 | +2.49% – +11.19% | +2.05% – +11.30% | +1.85% – +11.66% |
| **2017** | 197 | +6.09% | +2.35% | 2.20 | 2.20 | 163 | +0.74% – +11.73% | +0.62% – +11.57% | +1.16% – +11.70% |
| **2018** | 211 | +3.18% | +0.42% | 1.61 | 1.57 | 177 | -0.63% – +7.13% | -0.82% – +7.18% | -0.75% – +7.00% |
| **2019** | 227 | +0.44% | -4.87% | 0.19 | 0.18 | 194 | -4.04% – +5.30% | -4.28% – +5.16% | -3.63% – +5.14% |
| **2020** | 376 | +5.27% | -9.57% | 1.68 | 1.66 | 307 | -0.43% – +11.91% | -0.98% – +11.53% | -0.86% – +11.54% |
| **2021** | 246 | +3.88% | +4.90% | 1.61 | 1.58 | 200 | -0.51% – +8.81% | -0.97% – +8.73% | -0.59% – +8.70% |
| **2022** | 402 | +2.31% | -3.40% | 1.07 | 1.06 | 329 | -1.86% – +6.85% | -1.99% – +6.61% | -1.99% – +6.60% |
| **2023** | 415 | +2.31% | -5.50% | 1.00 | 1.02 | 348 | -2.18% – +6.72% | -2.14% – +6.77% | -2.02% – +7.11% |
| **2024** | 339 | +7.14% | +1.79% | 2.45 | 2.43 | 283 | +1.34% – +12.51% | +1.35% – +12.94% | +0.94% – +12.49% |
| **2025** | 351 | +0.19% | -8.99% | 0.06 | 0.06 | 289 | -5.52% – +6.42% | -6.11% – +6.49% | -5.67% – +6.53% |
| **2026** | 38 | -1.23% | -3.44% | -0.16 | -0.16 | 38 | -14.61% – +14.13% | -16.50% – +14.03% | -14.61% – +14.13% |

### Perche' le prime due righe coincidono

L'excess sul calendario comune e' ricalcolato da capo dalle serie prezzi, non riletto dal CSV dell'originale. Su 3,213 eventi confrontati la differenza massima fra i due excess e' **0.12%**, e la data di uscita cambia per **1** eventi: le serie hanno una barra per ogni sessione di borsa, quindi contare barre del titolo e contare sessioni IWM porta quasi sempre alla stessa data.

Gli eventi `ENDED_IN_WINDOW` entrano solo nella terza riga. Una serie che finisce prima dell'uscita puo' essere un delisting o un cambio di ticker: la regola dell'ADR-010 non li distingue.

Eventi `ENDED_IN_WINDOW` in questo confronto: **2** (copia pubblica: tolti ticker, date ed excess per titolo).

## 5. Cosa non c'e' in questo passo

Nessun matching, nessun placebo, nessuna scomposizione: sono il passo 2 e il passo 3, sulla popolazione primaria dell'addendum 1 (un evento per emittente ogni 365 giorni). La popolazione di questa pagina e' la replica, variante (b) a 126 giorni, e non entra nel verdetto.
