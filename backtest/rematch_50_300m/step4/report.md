# Passo 4 — closed period

Generato da `python backtest/rematch_50_300m/step4_closed_period.py`. Pre-registrazione §8, ADR-011. Coppie del passo 2 (cella P, 126 sessioni, gamba dell'evento valida). Modelli linguistici: token e costo **0**.

Il passo 2 ha dato **R1**, nessun matching di riferimento: si riportano i tre confronti.

| | |
|---|---:|
| eventi | 2,324 |
| senza T | 0 |
| shard necessari ([T − 200 giorni, T]) | 57 |
| di cui scaricati in questo passo | 52 |
| non scaricati (tetto o errore) | 0 |
| chiamate EDGAR di questo passo, cumulate | 52 / 373 |
| impronta degli shard necessari (sha256 di nome + sha256, in ordine) | `73384332a974d9d61180a1920c26d959a64236ee0cf37f2670d3d406b9a7e225` |

## 10-Q, 10-K, 10-KT — W = 5 sessioni

Dentro 709 · fuori 1,598 · UNKNOWN 17 (0.7%).

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dentro vs IWM | 709 | +3.46% | -4.87% | 1.68 | 1.68 | 513 | -0.18% – +7.77% | -0.59% – +7.51% | -0.42% – +7.47% |
| dentro vs M_size | 707 | +2.92% | +0.82% | 1.04 | 1.06 | 512 | -2.14% – +8.65% | -2.49% – +8.33% | -2.34% – +7.98% |
| dentro vs M_mom | 658 | +2.57% | -0.22% | 0.95 | 0.93 | 472 | -2.76% – +7.55% | -2.87% – +8.00% | -2.76% – +7.89% |
| fuori vs IWM | 1,598 | +2.81% | -0.57% | 2.64 | 2.77 | 877 | +0.74% – +4.94% | +0.82% – +4.80% | +0.79% – +4.86% |
| fuori vs M_size | 1,595 | +1.34% | +3.55% | 0.79 | 0.81 | 877 | -2.14% – +4.68% | -1.91% – +4.59% | -2.02% – +4.82% |
| fuori vs M_mom | 1,495 | +1.58% | +3.28% | 0.93 | 0.96 | 815 | -1.76% – +4.70% | -1.66% – +4.82% | -1.72% – +4.72% |

## 10-Q, 10-K, 10-KT — W = 10 sessioni (principale)

Dentro 1,016 · fuori 1,291 · UNKNOWN 17 (0.7%).

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dentro vs IWM | 1,016 | +3.61% | -4.43% | 2.18 | 2.22 | 673 | +0.33% – +6.57% | +0.41% – +6.80% | +0.36% – +6.91% |
| dentro vs M_size | 1,013 | +2.10% | +3.00% | 0.84 | 0.85 | 673 | -3.43% – +6.64% | -2.76% – +6.97% | -2.40% – +6.99% |
| dentro vs M_mom | 947 | +2.16% | +1.14% | 0.96 | 0.95 | 623 | -1.99% – +6.67% | -2.31% – +6.62% | -2.04% – +6.88% |
| fuori vs IWM | 1,291 | +2.54% | -0.30% | 2.21 | 2.28 | 768 | +0.24% – +5.00% | +0.35% – +4.72% | +0.44% – +4.85% |
| fuori vs M_size | 1,289 | +1.61% | +2.76% | 0.94 | 0.96 | 768 | -1.71% – +4.87% | -1.68% – +4.90% | -1.67% – +4.69% |
| fuori vs M_mom | 1,206 | +1.67% | +3.63% | 0.90 | 0.91 | 712 | -1.76% – +5.37% | -1.95% – +5.28% | -2.00% – +5.10% |

## 10-Q, 10-K, 10-KT — W = 20 sessioni

Dentro 1,409 · fuori 898 · UNKNOWN 17 (0.7%).

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dentro vs IWM | 1,409 | +3.24% | -3.98% | 2.44 | 2.43 | 832 | +0.53% – +5.91% | +0.62% – +5.86% | +0.75% – +5.85% |
| dentro vs M_size | 1,405 | +2.13% | +3.00% | 1.08 | 1.07 | 832 | -1.55% – +6.09% | -1.79% – +6.06% | -1.61% – +6.02% |
| dentro vs M_mom | 1,311 | +2.04% | +1.84% | 1.07 | 1.05 | 769 | -1.55% – +6.01% | -1.77% – +5.84% | -1.60% – +5.94% |
| fuori vs IWM | 898 | +2.64% | +0.31% | 1.93 | 1.96 | 581 | +0.02% – +5.23% | -0.00% – +5.29% | +0.13% – +5.34% |
| fuori vs M_size | 897 | +1.34% | +2.76% | 0.64 | 0.66 | 580 | -2.72% – +5.53% | -2.64% – +5.32% | -2.56% – +5.20% |
| fuori vs M_mom | 842 | +1.64% | +3.32% | 0.75 | 0.77 | 537 | -2.71% – +5.86% | -2.57% – +5.85% | -2.65% – +6.03% |

## 8-K item 2.02 (descrittivo) — W = 10 sessioni

Dentro 1,027 · fuori 1,050 · UNKNOWN 247 (10.6%).

| | n | media | mediana | t semplice | t CR1 | emittenti | IC bootstrap semplice | IC da t CR1 | IC bootstrap per emittente |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dentro vs IWM | 1,027 | +5.79% | -0.47% | 3.65 | 3.68 | 658 | +2.72% – +8.92% | +2.70% – +8.88% | +2.85% – +8.79% |
| dentro vs M_size | 1,025 | +5.29% | +5.93% | 2.27 | 2.29 | 658 | +0.25% – +9.55% | +0.76% – +9.82% | +0.76% – +9.21% |
| dentro vs M_mom | 969 | +4.35% | +3.52% | 1.97 | 1.98 | 621 | -0.23% – +8.68% | +0.04% – +8.66% | -0.05% – +8.67% |
| fuori vs IWM | 1,050 | +1.62% | -2.36% | 1.36 | 1.39 | 650 | -0.68% – +4.00% | -0.67% – +3.91% | -0.49% – +3.99% |
| fuori vs M_size | 1,047 | +0.76% | +2.01% | 0.39 | 0.39 | 650 | -2.59% – +4.59% | -3.02% – +4.54% | -2.90% – +4.46% |
| fuori vs M_mom | 986 | -0.22% | +2.18% | -0.11 | -0.11 | 609 | -4.03% – +4.02% | -4.17% – +3.73% | -4.38% – +3.75% |

## Flag

| flag | eventi |
|---|---:|

Potenza (pre-registrazione §10): con 1.000–1.500 eventi per lato l'MDE contro peer è 4,8–6,4%; sotto il 5% il confronto dentro/fuori non ha potenza.
