# Russell 2000, uscite verso il basso — conteggi della fermata 1

Generato da `python backtest/russell_exits/analisi.py --conteggi`. **Nessun rendimento extra calcolato o guardato.** Chiamate EDGAR usate: 2103 (tetto 3000).

Rifatti dopo le tre decisioni che il §9 della pre-registrazione aspettava:
- **definizione** di ADR-039 (assente o ≤ 50% delle azioni di marzo, non in IWB, abbinamento per emittente), con il classificatore validato contro le liste ufficiali: nessun anno controllato sopra il 10% di falsi positivi (`falsi_positivi_ricalcolati.md`);
- **istantanea «dopo» del 30 settembre** per il 2019 e il 2024, con gli eventi societari della fase 1 contati fino a quella data;
- **prezzi, volumi e identità dall'archivio EODHD** (ADR-040), che conserva i delistati che Yahoo perde.

## Casi per anno

| anno | definizione verificata sulla lista ufficiale | uscite verso il basso | verso l'alto | dopo esclusioni e filtri | con ≥ 3 peer | rimasti | universo dei peer | falsi eventi |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2015 | no: lista non cercata | 183 | 30 | 25 | 25 | 1787 | 411 | 25 |
| 2016 | sì | 156 | 35 | 10 | 10 | 1771 | 379 | 10 |
| 2017 | sì | 145 | 30 | 5 | 5 | 1778 | 375 | 5 |
| 2018 | no: nessuna lista | 138 | 49 | 11 | 11 | 1792 | 447 | 11 |
| 2019 | no: nessuna lista | 270 | 36 | 35 | 35 | 1686 | 499 | 35 |
| 2020 | no: solo l'aggiornamento del 19 giugno | 164 | 113 | 26 | 26 | 1693 | 532 | 26 |
| 2021 | sì | 297 | 111 | 64 | 64 | 1638 | 490 | 64 |
| 2022 | sì | 304 | 90 | 26 | 26 | 1612 | 468 | 26 |
| 2023 | sì | 185 | 21 | 9 | 9 | 1704 | 492 | 9 |
| 2024 | sì (istantanea di settembre) | 181 | 26 | 11 | 11 | 1726 | 535 | 11 |
| 2025 | sì | 165 | 18 | 12 | 12 | 1752 | 546 | 12 |

## Copertura: identità e prezzi, per anno

Nell'ordine delle esclusioni del §3. **Identità** = il prezzo implicito nella posizione del fondo coincide con la chiusura grezza EODHD entro il 3%. **Eventi** = restano dopo gli eventi societari del trimestre (Form 25/15, fusioni, 8-K 1.03). **Prezzi** = almeno l'80% di chiusure e volumi puliti dal Rank Day − 126 sedute alla ricostituzione.

| anno | uscite verso il basso | con identità | | dopo gli eventi | con prezzi sufficienti | copertura prezzi |
|---|---:|---:|---:|---:|---:|---:|
| 2015 | 183 | 162 | 88.5% | 132 | 107 | 81.1% |
| 2016 | 156 | 148 | 94.9% | 119 | 87 | 73.1% |
| 2017 | 145 | 137 | 94.5% | 96 | 71 | 74.0% |
| 2018 | 138 | 131 | 94.9% | 104 | 83 | 79.8% |
| 2019 | 270 | 250 | 92.6% | 188 | 153 | 81.4% |
| 2020 | 164 | 156 | 95.1% | 128 | 106 | 82.8% |
| 2021 | 297 | 280 | 94.3% | 255 | 207 | 81.2% |
| 2022 | 304 | 289 | 95.1% | 267 | 207 | 77.5% |
| 2023 | 185 | 170 | 91.9% | 140 | 114 | 81.4% |
| 2024 | 181 | 170 | 93.9% | 115 | 94 | 81.7% |
| 2025 | 165 | 158 | 95.8% | 133 | 119 | 89.5% |

## Esclusioni delle uscite verso il basso (tutti gli anni)

| motivo | casi |
|---|---:|
| filtri | 1112 |
| acquisita, in fusione o delistata nel trimestre | 374 |
| prezzi e volumi insufficienti | 329 |
| identità: NESSUN_PREZZO_EODHD | 59 |
| identità: PREZZO_DIVERSO | 57 |
| identità: NESSUN_CANDIDATO | 21 |
| SPAC (SIC 6770) | 2 |

## Filtri sulle uscite che arrivano ai filtri (tutti gli anni)

| filtro | passa | non passa | non verificabile |
|---|---:|---:|---:|
| flusso di cassa operativo 12 mesi > 0 | 567 | 632 | 147 |
| cassa netta o debito netto / EBITDA < 3 | 869 | 215 | 262 |
| azioni +5% o meno in 12 mesi | 834 | 340 | 172 |
| nessuna fusione annunciata alle liste preliminari | 1330 | 16 | 0 |

## Quando scatta l'ingresso (uscite dopo esclusioni, filtri e peer)

| scaglione | primo giorno possibile | forzato al limite | in mezzo | non decidibile | mediana sedute dopo la ricostituzione | quota agli estremi |
|---|---:|---:|---:|---:|---:|---:|
| B1 | 49 | 34 | 151 | 0 | 20.0 | 35.5% |
| B2 | 62 | 15 | 157 | 0 | 33.0 | 32.9% |
| B3 | 55 | 26 | 153 | 0 | 62.0 | 34.6% |

Sedute dopo la ricostituzione a cui scatta l'ingresso, per scaglione (N = sedute minime, limite = ingresso forzato):

| scaglione | N | limite | minimo | primo quartile | mediana | terzo quartile | massimo |
|---|---:|---:|---:|---:|---:|---:|---:|
| B1 | 10 | 60 | 10 | 11.8 | 20.0 | 35.5 | 60 |
| B2 | 20 | 126 | 20 | 20.0 | 33.0 | 62.2 | 126 |
| B3 | 40 | 189 | 40 | 42.0 | 62.0 | 98.2 | 189 |

In nessuno scaglione più della metà degli ingressi cade agli estremi.

## Casi disponibili per orizzonte

| cella | casi | anni |
|---|---:|---|
| A x 63 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| A x 126 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| A x 252 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B1 x 63 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B1 x 126 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B1 x 252 | 231 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B2 x 63 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B2 x 126 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B2 x 252 | 231 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B3 x 63 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B3 x 126 | 233 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| B3 x 252 | 229 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| C x 63 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| C x 126 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| C x 252 | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| dicembre: anticipo | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| dicembre: vendita | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| dicembre: coda | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |
| dicembre: recupero | 234 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 |

## Falsi eventi per il placebo

Per ogni anno, i rimasti dell'universo con la capitalizzazione più bassa non usati come peer, tanti quante le uscite con almeno 3 peer (ADR-045): un falso evento per caso, per costruzione; ingresso B2.

| anno | falsi eventi | con ingresso B2 decidibile |
|---|---:|---:|
| 2015 | 25 | 25 |
| 2016 | 10 | 10 |
| 2017 | 5 | 5 |
| 2018 | 11 | 11 |
| 2019 | 35 | 35 |
| 2020 | 26 | 26 |
| 2021 | 64 | 64 |
| 2022 | 26 | 26 |
| 2023 | 9 | 9 |
| 2024 | 11 | 11 |
| 2025 | 12 | 12 |
| **totale** | **234** | **234** |

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
