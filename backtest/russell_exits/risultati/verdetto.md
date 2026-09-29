# Russell 2000, uscite verso il basso — referto del verdetto

Generato da `python backtest/russell_exits/analisi.py --verdetto`. Pre-registrazione `2026-09-16_preregistrazione.md` (ultimo commit a10e009 2026-09-21), addenda del 21 e 22 settembre, decisioni ADR-039, 040, 041-045. Codice al commit `b91d83a`.

**Il verdetto si legge solo sulle due celle pre-registrate.** Tutto il resto è descrittivo e non decide niente.

## Verdetti

| domanda | cella | casi | anni | mediana | media delle medie annuali | t (gradi) | 2015-19 | 2020-25 | placebo: media, t | **esito** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1. Investimento | B2 × 252 | 225 | 11 | +4.8% | +1.6% | 0.24 (10) | +0.3% | +2.7% | +5.6%, t 1.03 | **NON REGGE** |
| 2. Scheda di dicembre | A × 32 | 234 | 11 | -0.6% | +1.5% | 0.45 (10) | -3.6% | +5.7% | -0.5%, t -0.15 | **NON REGGE** |

**1. Investimento — NON REGGE.** Criteri del §1, nell'ordine:

- vero — 1. almeno 100 casi e almeno 9 anni
- vero — 2. mediana > 0
- **falso** — 3. media delle medie annuali > 0 con t ≥ 2
- vero — 4. media > 0 in 2015-2019 e in 2020-2025
- **falso** — 5. placebo con |t| < 2 e media più bassa

**2. Scheda di dicembre — NON REGGE.** Criteri del §1, nell'ordine:

- vero — 1. almeno 100 casi e almeno 9 anni
- **falso** — 2. mediana > 0
- **falso** — 3. media delle medie annuali > 0 con t ≥ 2
- **falso** — 4. media > 0 in 2015-2019 e in 2020-2025
- vero — 5. placebo con |t| < 2 e media più bassa

## Medie per anno, celle del verdetto

| anno | investimento: casi | media | placebo falsi eventi: casi | media | dicembre: casi | media | placebo dicembre: casi | media |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 25 | -14.5% | 24 | +2.3% | 25 | +0.0% | 25 | -2.8% |
| 2016 | 9 | -13.6% | 10 | -16.2% | 10 | -10.4% | 10 | -2.1% |
| 2017 | 5 | +12.2% | 4 | +28.9% | 5 | -11.1% | 5 | +16.3% |
| 2018 | 11 | +18.0% | 11 | +3.2% | 11 | +3.3% | 11 | +0.7% |
| 2019 | 33 | -0.6% | 35 | +15.8% | 35 | +0.2% | 34 | -2.5% |
| 2020 | 24 | -6.5% | 26 | -25.2% | 26 | +21.2% | 26 | -25.8% |
| 2021 | 64 | +14.2% | 64 | +21.2% | 64 | -3.7% | 64 | -4.3% |
| 2022 | 26 | +29.8% | 26 | -5.6% | 26 | +2.4% | 26 | +14.6% |
| 2023 | 9 | -45.1% | 9 | +8.0% | 9 | -1.7% | 9 | +2.7% |
| 2024 | 10 | +29.9% | 11 | -3.1% | 11 | -5.9% | 10 | -0.4% |
| 2025 | 9 | -6.0% | 6 | +32.1% | 12 | +22.0% | 12 | -1.7% |

## Chi è fuori dalle celle del verdetto, e come sono trattati i delistati

| cella | completo | delistato: ultimo prezzo | delistato: offerta in contanti | fuori: finestra oltre i dati | fuori: senza prezzo all'ingresso | fuori: buco all'uscita | fuori: meno di 3 peer | ingresso non decidibile |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VERDETTO investimento: B2 × 252 | 207 | 17 | 1 | 3 | 6 | 0 | 0 | 0 |
| PLACEBO investimento: falsi eventi, B2 × 252 | 215 | 10 | 1 | 6 | 1 | 1 | 0 | 0 |
| VERDETTO scheda di dicembre: A × 32 | 234 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| PLACEBO scheda di dicembre: finestra spostata di 63 sedute | 227 | 5 | 0 | 0 | 2 | 0 | 0 | 0 |

## Casi persi per prezzi mancanti (descrittivo, nessun rendimento)

388 uscite verso il basso non entrano per prezzi mancanti (prezzi e volumi insufficienti, o nessun prezzo EODHD per verificare l'identità). Per anno: 2015 32, 2016 34, 2017 31, 2018 25, 2019 41, 2020 26, 2021 56, 2022 65, 2023 32, 2024 26, 2025 20. Per mercato: NASDAQ 204, senza codice EODHD 59, PINK 58, NYSE 37, OTCMKTS 9, OTCQB 6, OTCQX 5, NYSE MKT 5, AMEX 5. Per fascia di grandezza (terzili del valore della posizione di IWM a marzo fra le uscite dell'anno): bassa 189, media 134, alta 65.

## Celle descrittive (non decidono niente)

| cella | casi | anni | media | mediana | quota positivi | media delle medie annuali | t |
|---|---:|---:|---:|---:|---:|---:|---:|
| A × 63 | 234 | 11 | +6.2% | +2.8% | 57.3% | +4.3% | 0.95 |
| A × 126 | 234 | 11 | +4.4% | +3.5% | 53.4% | +2.4% | 0.66 |
| A × 252 | 234 | 11 | +10.4% | +5.0% | 53.4% | +5.1% | 0.73 |
| B1 × 63 | 233 | 11 | +1.7% | +0.4% | 50.6% | +2.8% | 1.05 |
| B1 × 126 | 232 | 11 | +7.9% | +6.6% | 57.3% | +7.7% | 2.27 |
| B1 × 252 | 229 | 11 | +5.0% | +4.7% | 53.7% | +4.0% | 0.55 |
| B2 × 63 | 228 | 11 | +3.8% | +2.1% | 53.9% | +5.6% | 2.09 |
| B2 × 126 | 227 | 11 | +8.5% | +5.0% | 55.9% | +6.9% | 1.75 |
| B2 × 252 | 225 | 11 | +5.0% | +4.8% | 52.0% | +1.6% | 0.24 |
| B3 × 63 | 224 | 11 | +4.3% | +1.9% | 54.0% | +4.7% | 2.09 |
| B3 × 126 | 223 | 11 | +5.4% | +5.7% | 56.1% | +1.8% | 0.47 |
| B3 × 252 | 219 | 11 | +6.0% | +5.8% | 53.9% | +5.6% | 0.63 |
| C × 63 | 234 | 11 | +2.0% | +1.9% | 55.1% | +3.5% | 1.06 |
| C × 126 | 233 | 11 | +6.3% | +5.7% | 56.2% | +3.9% | 0.92 |
| C × 252 | 234 | 11 | +6.1% | +4.4% | 56.8% | +3.4% | 0.45 |
| dicembre: anticipo | 234 | 11 | +2.1% | +1.3% | 55.6% | +1.4% | 0.70 |
| dicembre: vendita | 234 | 11 | -1.6% | -2.1% | 37.2% | -1.5% | -1.04 |
| dicembre: coda | 234 | 11 | +0.8% | +0.3% | 51.7% | -0.3% | -0.11 |
| dicembre: recupero | 234 | 11 | +1.1% | -0.2% | 49.1% | +1.5% | 0.80 |
| approssimazione di dicembre | 76 | 11 | +7.9% | +2.8% | 59.2% | +8.7% | 2.06 |

Chiamate EDGAR usate: 2103 (tetto 3000); il prezzo delle offerte si legge solo da documenti già in cache.

