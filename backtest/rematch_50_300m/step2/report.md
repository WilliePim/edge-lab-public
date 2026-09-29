# Passi 2 e 3 — controllo appaiato, placebo, verdetto

Generato da `python backtest/rematch_50_300m/step2_analysis.py`. Pre-registrazione `130b0fe`, addendum 1 `e48cfb9`, addendum 2 `3322f7e`, addendum 3 `fd28e71`. Nessuna chiamata di rete; modelli linguistici: token e costo **0**.

| input | sha256 |
|---|---|
| `step2_prep/popolazione.jsonl` | `eb610a1482fbd0190ba203239dfd70df87e3bc351d36f946db534dadeda61de1` |
| `step2_prep/deal.jsonl` | `e74395669e3fddfa3256e91e840ad35e491476a0dfa20c586a3ae6d45fb3ea64` |
| `state/backfill/prices_resolved/` | `39e6abc8ab59209892bc2a492f458ad68e7b068b60322c26b4e8907fd3e857b2` (70 file) |

## Verdetto primario

> **INCONCLUSIVO — R1**: placebo non ~ 0, nessun matching lo corregge

| | M_size | M_mom |
|---|---|---|
| P1 ≈ 0 | sì | compresso per costruzione |
| P2 ≈ 0 | no | no |
| Q (placebo credibile) | no | no |
| S (media > 0 e IC CR1 esclude 0) | no | no |

Matching di riferimento **sel = non esiste**. R0′ non si applica senza sel; il test di segno per ciascun confronto è nella tabella degli scenari (§6).

Placebo ≈ 0 ⟺ IC 95% CR1 include lo zero **e** |media| < 1,5 punti (addendum 1 §3).

## 1. Cella × confronto, 126 sessioni

Popolazione primaria dell'addendum 1 sull'unione dell'addendum 3; sul verdetto entrano osservati e risolti. Excess in euro, calendario comune, ingresso dell'addendum 2.

### P (50-300M)

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vs IWM | 2,324 | +3.05% | -2.12% | 3.15 | 3.22 | 1,105 | +1.09% – +4.93% | +1.19% – +4.92% | +1.15% – +4.94% |
| vs peer dimensione (M_size) | 2,319 | +1.83% | +2.83% | 1.26 | 1.27 | 1,105 | -0.83% – +4.72% | -1.01% – +4.67% | -1.10% – +4.65% |
| vs peer dimensione + momentum (M_mom) | 2,166 | +1.92% | +2.55% | 1.34 | 1.35 | 1,019 | -0.94% – +4.93% | -0.88% – +4.73% | -0.87% – +4.68% |

### <50M

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vs IWM | 926 | +4.80% | -4.70% | 2.37 | 2.31 | 569 | +1.00% – +8.59% | +0.73% – +8.88% | +0.78% – +8.94% |
| vs peer dimensione (M_size) | 911 | -3.75% | +2.47% | -1.12 | -1.12 | 564 | -10.28% – +2.61% | -10.32% – +2.83% | -10.15% – +3.11% |
| vs peer dimensione + momentum (M_mom) | 861 | +2.52% | +1.82% | 0.91 | 0.93 | 528 | -2.76% – +7.76% | -2.81% – +7.84% | -2.72% – +7.82% |

### >300M

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vs IWM | 6,906 | -0.32% | -1.96% | -0.73 | -0.72 | 2,466 | -1.17% – +0.55% | -1.17% – +0.54% | -1.17% – +0.59% |
| vs peer dimensione (M_size) | 6,894 | +3.37% | +2.57% | 5.38 | 5.25 | 2,466 | +2.18% – +4.58% | +2.11% – +4.63% | +2.13% – +4.64% |
| vs peer dimensione + momentum (M_mom) | 6,512 | +2.66% | +2.40% | 4.24 | 4.24 | 2,318 | +1.42% – +3.80% | +1.43% – +3.88% | +1.38% – +3.80% |

### cluster

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vs IWM | 20 | +13.13% | +0.67% | 1.55 | 1.53 | 17 | -1.97% – +29.64% | -5.11% – +31.38% | -0.79% – +31.52% |
| vs peer dimensione (M_size) | 20 | +13.40% | +13.29% | 1.08 | 1.12 | 17 | -10.11% – +37.31% | -11.94% – +38.75% | -7.39% – +37.65% |
| vs peer dimensione + momentum (M_mom) | 16 | +3.01% | -2.73% | 0.20 | 0.21 | 13 | -22.90% – +30.61% | -28.84% – +34.86% | -24.75% – +32.25% |

### 4/4

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| vs IWM | — | — | — | — | — | — | — | — | — |
| vs peer dimensione (M_size) | — | — | — | — | — | — | — | — | — |
| vs peer dimensione + momentum (M_mom) | — | — | — | — | — | — | — | — | — |

La cella 4/4 non è testabile (addendum 1 §8): si legge solo n = **0** eventi con `score_v3` = 4 su 2,282 eventi della cella P con punteggio calcolato.

## 2. Placebo (passo 3)

Stesso peer scelto alla data dell'evento; P1 = (−252, −126], P2 = (−504, −378] sessioni dall'ingresso.

### P (50-300M)

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M_size P1 | 2,129 | -0.51% | +1.24% | -0.37 | -0.37 | 1,014 | -3.43% – +2.41% | -3.22% – +2.20% | -2.96% – +2.20% |
| M_size P2 | 1,778 | +4.53% | +3.72% | 2.86 | 2.92 | 876 | +1.51% – +7.51% | +1.48% – +7.58% | +1.46% – +7.69% |
| M_mom P1 | 2,159 | +4.12% | +3.43% | 4.09 | 4.11 | 1,017 | +2.05% – +6.12% | +2.15% – +6.09% | +2.18% – +6.07% |
| M_mom P2 | 1,817 | +3.31% | +1.80% | 2.32 | 2.33 | 888 | +0.67% – +6.08% | +0.53% – +6.10% | +0.44% – +6.29% |

### <50M

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M_size P1 | 832 | -2.84% | -0.09% | -1.06 | -1.08 | 520 | -8.00% – +2.40% | -7.99% – +2.31% | -8.22% – +1.93% |
| M_size P2 | 693 | +8.96% | +5.30% | 3.15 | 3.17 | 459 | +3.48% – +14.65% | +3.41% – +14.52% | +3.52% – +14.52% |
| M_mom P1 | 858 | +1.52% | +3.03% | 0.80 | 0.81 | 525 | -2.18% – +5.49% | -2.15% – +5.20% | -1.92% – +5.23% |
| M_mom P2 | 711 | +3.22% | +3.50% | 1.02 | 1.00 | 471 | -2.86% – +9.09% | -3.11% – +9.55% | -3.03% – +9.41% |

### >300M

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M_size P1 | 6,355 | +0.24% | -0.46% | 0.37 | 0.36 | 2,299 | -0.99% – +1.56% | -1.04% – +1.51% | -0.99% – +1.51% |
| M_size P2 | 5,296 | +0.13% | +1.33% | 0.19 | 0.18 | 2,126 | -1.32% – +1.64% | -1.30% – +1.57% | -1.26% – +1.53% |
| M_mom P1 | 6,507 | +3.97% | +3.81% | 9.09 | 9.01 | 2,316 | +3.14% – +4.85% | +3.10% – +4.83% | +3.12% – +4.82% |
| M_mom P2 | 5,446 | -0.86% | -0.39% | -1.23 | -1.24 | 2,133 | -2.20% – +0.54% | -2.23% – +0.50% | -2.14% – +0.52% |

### cluster

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M_size P1 | 16 | -18.17% | -0.55% | -1.45 | -1.70 | 13 | -44.05% – +2.56% | -41.51% – +5.18% | -37.97% – +1.83% |
| M_size P2 | 15 | -0.94% | +0.97% | -0.05 | -0.05 | 12 | -34.88% – +30.39% | -40.89% – +39.00% | -30.87% – +34.55% |
| M_mom P1 | 16 | -1.35% | -3.51% | -0.19 | -0.19 | 13 | -14.41% – +11.64% | -16.48% – +13.78% | -16.28% – +11.57% |
| M_mom P2 | 14 | -8.88% | -4.80% | -0.89 | -0.78 | 11 | -27.03% – +8.59% | -34.34% – +16.58% | -30.31% – +10.64% |

### 4/4

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M_size P1 | — | — | — | — | — | — | — | — | — |
| M_size P2 | — | — | — | — | — | — | — | — | — |
| M_mom P1 | — | — | — | — | — | — | — | — | — |
| M_mom P2 | — | — | — | — | — | — | — | — | — |

### Media a 126 sessioni ristretta alle coppie col placebo — cella P

| | coppie con P1 | media | coppie con P2 | media |
|---|---:|---:|---:|---:|
| M_size | 2,129 | +1.37% | 1,778 | +1.53% |
| M_mom | 2,159 | +2.05% | 1,817 | +1.91% |

### Differenza evento per evento, M_size − M_mom — cella P

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| (r_e − r_M_size) − (r_e − r_M_mom) | 2,162 | +0.16% | +0.00% | 0.11 | 0.11 | 1,019 | -2.79% – +3.05% | -2.86% – +3.18% | -2.78% – +3.16% |

Descrittiva (addendum 1 §4, conciliazione 3): non cambia la tabella.

## 3. Scomposizione per anno — cella P

Sullo stesso calendario, per evento: (r_e − r_IWM) = (r_e − r_peer) + (r_peer − r_IWM). Verificata esatta (scarto massimo 8.9e-16). Quota = media (r_peer − r_IWM) ÷ media (r_e − r_IWM).

### M_size

| anno | n | r_e − r_IWM | r_e − r_peer | r_peer − r_IWM | quota del peer |
|---|---:|---:|---:|---:|---:|
| 2015 | 183 | +3.93% | +5.96% | -2.03% | -52% |
| 2016 | 139 | +4.16% | +6.74% | -2.58% | -62% |
| 2017 | 147 | +5.45% | +4.98% | +0.47% | 9% |
| 2018 | 156 | +4.77% | -3.58% | +8.36% | 175% |
| 2019 | 163 | +1.58% | -1.43% | +3.01% | 190% |
| 2020 | 262 | +3.91% | -4.12% | +8.03% | 205% |
| 2021 | 186 | +2.82% | -1.24% | +4.05% | 144% |
| 2022 | 283 | +0.31% | +1.74% | -1.43% | -470% |
| 2023 | 291 | +0.88% | +0.82% | +0.06% | 7% |
| 2024 | 239 | +6.47% | +7.77% | -1.30% | -20% |
| 2025 | 242 | +2.44% | +7.78% | -5.35% | -219% |
| 2026 | 28 | -6.36% | -31.57% | +25.22% | — |
| **tutti** | **2,319** | **+3.00%** | **+1.83%** | **+1.17%** | **39%** |

### M_mom

| anno | n | r_e − r_IWM | r_e − r_peer | r_peer − r_IWM | quota del peer |
|---|---:|---:|---:|---:|---:|
| 2015 | 169 | +3.14% | -2.61% | +5.75% | 183% |
| 2016 | 137 | +4.07% | +4.49% | -0.42% | -10% |
| 2017 | 135 | +5.47% | +1.56% | +3.91% | 71% |
| 2018 | 145 | +4.14% | -0.80% | +4.94% | 119% |
| 2019 | 151 | +3.28% | +1.31% | +1.97% | 60% |
| 2020 | 246 | +2.46% | -6.19% | +8.65% | 351% |
| 2021 | 168 | +2.89% | -4.80% | +7.68% | 266% |
| 2022 | 259 | +0.10% | +2.21% | -2.12% | -2210% |
| 2023 | 284 | +1.04% | +4.56% | -3.52% | -339% |
| 2024 | 225 | +7.60% | +9.60% | -2.00% | -26% |
| 2025 | 219 | +4.93% | +8.44% | -3.51% | -71% |
| 2026 | 28 | -6.36% | +5.50% | -11.85% | — |
| **tutti** | **2,166** | **+3.21%** | **+1.92%** | **+1.28%** | **40%** |

## 4. Per anno — cella P

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2015** vs IWM | 183 | +3.93% | +2.34% | 1.96 | 1.96 | 183 | +0.23% – +7.97% | -0.02% – +7.88% | -0.03% – +8.28% |
| **2015** vs M_size | 183 | +5.96% | +2.76% | 2.11 | 2.11 | 183 | +0.32% – +11.56% | +0.38% – +11.55% | +0.34% – +11.68% |
| **2015** vs M_mom | 169 | -2.61% | -2.56% | -0.89 | -0.89 | 169 | -8.01% – +2.90% | -8.42% – +3.20% | -8.32% – +3.21% |
| **2016** vs IWM | 139 | +4.16% | +1.18% | 1.59 | 1.59 | 139 | -0.69% – +9.76% | -1.01% – +9.34% | -0.93% – +9.53% |
| **2016** vs M_size | 139 | +6.74% | +5.90% | 2.03 | 2.03 | 139 | +0.22% – +13.38% | +0.18% – +13.31% | +0.03% – +13.28% |
| **2016** vs M_mom | 137 | +4.49% | +5.67% | 0.98 | 0.98 | 137 | -4.52% – +13.17% | -4.53% – +13.51% | -4.35% – +12.76% |
| **2017** vs IWM | 147 | +5.45% | +2.05% | 1.58 | 1.58 | 147 | -0.90% – +12.59% | -1.37% – +12.28% | -0.67% – +13.13% |
| **2017** vs M_size | 147 | +4.98% | +3.75% | 0.99 | 0.99 | 147 | -5.36% – +14.79% | -5.00% – +14.97% | -5.24% – +14.84% |
| **2017** vs M_mom | 135 | +1.56% | +3.86% | 0.29 | 0.29 | 135 | -9.34% – +11.83% | -9.04% – +12.16% | -8.43% – +11.26% |
| **2018** vs IWM | 156 | +4.77% | +0.40% | 2.12 | 2.12 | 156 | +0.04% – +9.58% | +0.32% – +9.22% | +0.08% – +9.14% |
| **2018** vs M_size | 156 | -3.58% | +2.75% | -0.71 | -0.71 | 156 | -14.11% – +6.53% | -13.59% – +6.42% | -14.94% – +5.24% |
| **2018** vs M_mom | 145 | -0.80% | +6.53% | -0.16 | -0.16 | 145 | -11.21% – +7.66% | -10.71% – +9.10% | -10.29% – +7.91% |
| **2019** vs IWM | 165 | +2.11% | -2.83% | 0.72 | 0.72 | 165 | -3.60% – +8.33% | -3.72% – +7.94% | -3.58% – +8.37% |
| **2019** vs M_size | 163 | -1.43% | +1.05% | -0.28 | -0.28 | 163 | -11.57% – +8.52% | -11.56% – +8.71% | -11.72% – +8.02% |
| **2019** vs M_mom | 151 | +1.31% | +3.52% | 0.28 | 0.28 | 151 | -7.86% – +9.95% | -7.79% – +10.41% | -7.39% – +10.34% |
| **2020** vs IWM | 264 | +3.71% | -10.91% | 1.00 | 1.00 | 264 | -3.22% – +10.73% | -3.58% – +10.99% | -3.41% – +11.37% |
| **2020** vs M_size | 262 | -4.12% | +3.47% | -0.77 | -0.77 | 262 | -14.10% – +6.37% | -14.68% – +6.45% | -14.55% – +6.15% |
| **2020** vs M_mom | 246 | -6.19% | -6.46% | -1.14 | -1.14 | 246 | -16.73% – +4.04% | -16.86% – +4.49% | -17.26% – +4.15% |
| **2021** vs IWM | 186 | +2.82% | +2.27% | 0.93 | 0.93 | 186 | -2.71% – +9.23% | -3.13% – +8.77% | -2.79% – +8.70% |
| **2021** vs M_size | 186 | -1.24% | +2.61% | -0.26 | -0.26 | 186 | -9.79% – +8.02% | -10.50% – +8.03% | -10.42% – +8.06% |
| **2021** vs M_mom | 168 | -4.80% | +1.62% | -1.09 | -1.09 | 168 | -14.01% – +3.88% | -13.46% – +3.87% | -12.83% – +3.74% |
| **2022** vs IWM | 283 | +0.31% | -4.79% | 0.12 | 0.12 | 283 | -4.49% – +5.13% | -4.66% – +5.27% | -4.46% – +5.40% |
| **2022** vs M_size | 283 | +1.74% | +1.31% | 0.53 | 0.53 | 283 | -4.40% – +8.07% | -4.68% – +8.16% | -4.54% – +7.77% |
| **2022** vs M_mom | 259 | +2.21% | +2.78% | 0.61 | 0.61 | 259 | -4.76% – +9.30% | -4.96% – +9.38% | -5.10% – +9.28% |
| **2023** vs IWM | 291 | +0.88% | -5.27% | 0.33 | 0.33 | 291 | -3.94% – +5.92% | -4.32% – +6.09% | -4.12% – +6.31% |
| **2023** vs M_size | 291 | +0.82% | +1.92% | 0.19 | 0.19 | 291 | -7.77% – +8.86% | -7.63% – +9.28% | -7.80% – +9.43% |
| **2023** vs M_mom | 284 | +4.56% | +1.51% | 1.07 | 1.07 | 284 | -3.62% – +12.54% | -3.86% – +12.98% | -3.60% – +12.99% |
| **2024** vs IWM | 240 | +6.87% | +1.46% | 1.95 | 1.95 | 240 | +0.38% – +13.79% | -0.07% – +13.80% | -0.53% – +14.44% |
| **2024** vs M_size | 239 | +7.77% | +6.38% | 1.55 | 1.55 | 239 | -2.56% – +18.02% | -2.11% – +17.64% | -1.67% – +17.08% |
| **2024** vs M_mom | 225 | +9.60% | +2.35% | 2.10 | 2.10 | 225 | +0.04% – +18.25% | +0.60% – +18.61% | +1.24% – +18.14% |
| **2025** vs IWM | 242 | +2.44% | -9.22% | 0.57 | 0.57 | 242 | -5.40% – +11.18% | -5.98% – +10.85% | -6.05% – +10.91% |
| **2025** vs M_size | 242 | +7.78% | +8.09% | 1.26 | 1.26 | 242 | -5.08% – +20.18% | -4.38% – +19.95% | -4.55% – +19.39% |
| **2025** vs M_mom | 219 | +8.44% | +4.52% | 1.46 | 1.46 | 219 | -2.60% – +19.02% | -2.92% – +19.79% | -2.48% – +18.58% |
| **2026** vs IWM | 28 | -6.36% | -5.74% | -0.79 | -0.79 | 28 | -20.47% – +8.76% | -22.96% – +10.25% | -21.82% – +8.97% |
| **2026** vs M_size | 28 | -31.57% | -24.24% | -2.13 | -2.13 | 28 | -58.49% – -3.37% | -61.99% – -1.16% | -60.21% – -6.41% |
| **2026** vs M_mom | 28 | +5.50% | +18.71% | 0.41 | 0.41 | 28 | -22.91% – +30.09% | -21.86% – +32.85% | -20.61% – +31.13% |

Sotto 10 emittenti la t con cluster non si calcola.

## 5. Sensibilità descrittive — cella P

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| M_size con quiet ±365 (lookahead, a favore di REGGE) | 2,318 | +1.81% | +1.49% | 1.23 | 1.25 | 1,105 | -1.08% – +4.71% | -1.04% – +4.67% | -1.00% – +4.74% |
| M_mom con quiet ±365 (lookahead, a favore di REGGE) | 2,170 | +0.81% | +0.93% | 0.56 | 0.57 | 1,020 | -2.01% – +3.80% | -2.00% – +3.63% | -1.97% – +3.58% |
| 2022–2025 vs IWM | 1,056 | +2.45% | -4.91% | 1.52 | 1.54 | 722 | -0.74% – +5.61% | -0.67% – +5.56% | -0.47% – +5.53% |
| 2022–2025 vs M_size | 1,055 | +4.24% | +2.83% | 1.81 | 1.87 | 722 | -0.38% – +8.55% | -0.22% – +8.69% | -0.05% – +8.71% |
| 2022–2025 vs M_mom | 987 | +5.95% | +2.78% | 2.63 | 2.69 | 670 | +1.66% – +10.27% | +1.61% – +10.30% | +1.26% – +10.03% |

## 6. Sopravvivenza — cella P

| stato | eventi |
|---|---:|
| `GUASTO_FONTE` | 21 |
| `OSSERVATO` | 2,297 |
| `RISOLTO` | 33 |
| `TERMINATO_IN_FINESTRA` | 38 |
| `TOO_RECENT` | 32 |
| `USCITO_DOPO` | 1,264 |
| `USCITO_PRIMA` | 4 |
| `VIVO_SENZA_STORIA` | 20 |

**Copertura** = (osservati + risolti) ÷ (osservati + risolti + terminati in finestra + vivi non osservati) = 2,330 ÷ 3,673 = **63.4%**.

Classificatore d'uscita: concordanza 90.0% su 40 emittenti → valido.

### Terminati in finestra ai valori del §6

| scenario | eventi |
|---|---:|
| S0 | 3 |
| S_acq | 9 |
| S_zero | 26 |

| flag | eventi |
|---|---:|
| `DEAL_MISTO` | 1 |
| `DEAL_NON_TROVATO` | 22 |
| `INGRESSO_NON_ALLA_DATA_DI_DEPOSITO` | 9 |
| `NON_RISOLTO` | 1 |
| `OTC_SENZA_PREZZO` | 2 |

Senza gamba del peer (esclusi dagli scenari contro peer): 0.

### Tabella degli scenari

| confronto | osservati + risolti | + terminati ai valori del §6 | + NON_RISOLTO in finestra a S0 |
|---|---:|---:|---:|
| vs IWM | +3.05% (n 2,324) | +3.04% (n 2,362) | +3.00% (n 2,362) |
| vs M_size | +1.83% (n 2,319) | +1.83% (n 2,357) | +1.79% (n 2,357) |
| vs M_mom | +1.92% (n 2,166) | +1.93% (n 2,204) | +1.88% (n 2,204) |

Negli scenari contro M_mom i terminati usano il peer M_size: senza serie non c'è r12.

### Limite dei vivi non osservati (addendum 3 §8)

USCITO_DOPO nella cella: n_u = 1,264. media_k = m − k · n_u / (n_v + n_u).

| confronto | m | k = 5 | k = 10 | k = 20 | k* |
|---|---:|---:|---:|---:|---:|
| vs IWM | +3.05% | +1.29% | -0.47% | -3.99% | 8.7 punti |
| vs M_size | +1.83% | +0.07% | -1.70% | -5.22% | 5.2 punti |
| vs M_mom | +1.92% | +0.08% | -1.76% | -5.45% | 5.2 punti |

## 7. Criterio secondario (svedese, addendum 1 §6)

*Il test svedese sta in un repo separato: <https://github.com/WilliePim/fi-insider-scanner>.*

> **INCONCLUSIVO — copertura 54,4% < 60%**, scritto prima dei rendimenti. I pezzi, per confronto:

| pezzo | valore |
|---|---|
| P vs IWM: media, t CR1 | +3.05% , 3.22 |
| C vs peer (M_size): media, t CR1 | +1.83% , 1.27 |
| P vs IWM con i terminati a S_zero | +3.04% |
| MDE di P (2,80 · SE CR1) | +2.66% |
| IC bootstrap semplice di P | +1.09% – +4.93% |

## 8. Diagnostica

| | |
|---|---:|
| emittenti nel pool (ADR-005: 4.765 attesi) | 4,819 |
| cap evento non ricalcolabile: distanza con la cap della fascia | 226 |
| cap ricalcolata fuori dalla fascia originale | 34 |
| M_size cella P: coppie, peer distinti, riuso massimo | 2,319 / 965 / 15 |
| M_mom cella P: coppie, peer distinti, riuso massimo | 2,166 / 948 / 11 |

| banda | stato della gamba evento | eventi |
|---|---|---:|
| 50-300M | `ARTEFACT` | 5 |
| 50-300M | `ENDED_IN_WINDOW` | 1 |
| 50-300M | `NO_ENTRY_BAR` | 1 |
| 50-300M | `OK` | 2,323 |
| <50M | `ARTEFACT` | 20 |
| <50M | `OK` | 926 |
| >300M | `ARTEFACT` | 2 |
| >300M | `ENDED_IN_WINDOW` | 1 |
| >300M | `NO_ENTRY_BAR` | 12 |
| >300M | `OK` | 6,905 |

| banda | matching | quiet | esito della gamba del peer | coppie |
|---|---|---|---|---:|
| 50-300M | M_mom | pm365 | `OK` | 2,166 |
| 50-300M | M_mom | pm365 | `PEER_ARTEFATTO` | 3 |
| 50-300M | M_mom | pm365 | `PEER_FINITO` | 4 |
| 50-300M | M_mom | primario | `OK` | 2,161 |
| 50-300M | M_mom | primario | `PEER_ARTEFATTO` | 7 |
| 50-300M | M_mom | primario | `PEER_FINITO` | 5 |
| 50-300M | M_size | pm365 | `OK` | 2,315 |
| 50-300M | M_size | pm365 | `PEER_ARTEFATTO` | 6 |
| 50-300M | M_size | pm365 | `PEER_FINITO` | 3 |
| 50-300M | M_size | primario | `OK` | 2,317 |
| 50-300M | M_size | primario | `PEER_ARTEFATTO` | 5 |
| 50-300M | M_size | primario | `PEER_FINITO` | 2 |
| <50M | M_mom | pm365 | `OK` | 856 |
| <50M | M_mom | pm365 | `PEER_ARTEFATTO` | 8 |
| <50M | M_mom | pm365 | `PEER_FINITO` | 5 |
| <50M | M_mom | primario | `OK` | 856 |
| <50M | M_mom | primario | `PEER_ARTEFATTO` | 8 |
| <50M | M_mom | primario | `PEER_FINITO` | 5 |
| <50M | M_size | pm365 | `OK` | 908 |
| <50M | M_size | pm365 | `PEER_ARTEFATTO` | 16 |
| <50M | M_size | pm365 | `PEER_FINITO` | 2 |
| <50M | M_size | primario | `OK` | 909 |
| <50M | M_size | primario | `PEER_ARTEFATTO` | 15 |
| <50M | M_size | primario | `PEER_FINITO` | 2 |
| >300M | M_mom | pm365 | `OK` | 6,490 |
| >300M | M_mom | pm365 | `PEER_ARTEFATTO` | 6 |
| >300M | M_mom | pm365 | `PEER_FINITO` | 20 |
| >300M | M_mom | primario | `OK` | 6,499 |
| >300M | M_mom | primario | `PEER_ARTEFATTO` | 3 |
| >300M | M_mom | primario | `PEER_FINITO` | 13 |
| >300M | M_mom | primario | `PEER_SENZA_INGRESSO` | 1 |
| >300M | M_size | pm365 | `OK` | 6,874 |
| >300M | M_size | pm365 | `PEER_ARTEFATTO` | 8 |
| >300M | M_size | pm365 | `PEER_FINITO` | 22 |
| >300M | M_size | pm365 | `PEER_SENZA_INGRESSO` | 2 |
| >300M | M_size | primario | `OK` | 6,878 |
| >300M | M_size | primario | `PEER_ARTEFATTO` | 11 |
| >300M | M_size | primario | `PEER_FINITO` | 16 |
| >300M | M_size | primario | `PEER_SENZA_INGRESSO` | 1 |

| banda | matching | quiet | peer trovato | eventi |
|---|---|---|---|---:|
| 50-300M | M_mom | pm365 | no | 152 |
| 50-300M | M_mom | pm365 | sì | 2,178 |
| 50-300M | M_mom | primario | no | 152 |
| 50-300M | M_mom | primario | sì | 2,178 |
| 50-300M | M_size | pm365 | sì | 2,330 |
| 50-300M | M_size | primario | sì | 2,330 |
| <50M | M_mom | pm365 | no | 57 |
| <50M | M_mom | pm365 | sì | 889 |
| <50M | M_mom | primario | no | 57 |
| <50M | M_mom | primario | sì | 889 |
| <50M | M_size | pm365 | sì | 946 |
| <50M | M_size | primario | sì | 946 |
| >300M | M_mom | pm365 | no | 402 |
| >300M | M_mom | pm365 | sì | 6,518 |
| >300M | M_mom | primario | no | 402 |
| >300M | M_mom | primario | sì | 6,518 |
| >300M | M_size | pm365 | sì | 6,920 |
| >300M | M_size | primario | sì | 6,920 |

## 9. Scelte d'implementazione non fissate dalle pre-registrazioni

Dichiarate nel docstring di `step2_analysis.py`, prima del primo rendimento:

- ticker del peer: fra i ticker del CIK nel corpus con serie in `prices/`, il più recente;
- D non di borsa: close all'ultima sessione ≤ D, azioni con `filed` ≤ D esatto;
- standardizzazione di M_mom con sd di popolazione (ddof = 0);
- cap dell'evento non ricalcolabile: distanza con la cap della fascia (contata sopra);
- peer finito prima dell'uscita: ultimo close piatto; peer fermo più di 5 sessioni: coppia esclusa;
- terminati in finestra: peer M_size con la cap insider in entrambi i matching; cambio a s0;
- giuntura: primo ticker di oggi, nell'ordine delle submissions, che riprende entro 5 sessioni.

## 10. Cosa manca in questo passo

- **Closed period** (passo 4): richiede gli shard delle submissions non in cache; script separato.
- **Passo 5**: solo se il verdetto primario è REGGE.
