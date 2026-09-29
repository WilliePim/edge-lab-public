# Falsi positivi ricalcolati, dopo la classificazione a mano

Generato da `python backtest/russell_exits/ricalcola_falsi_positivi.py`. Definizione di ADR-039: falso positivo = titolo segnato come uscita, presente nel campione dopo le esclusioni della fase 1, assente dalla lista ufficiale. Nessun rendimento calcolato.

Moduli che escludono in fase 1: quelli della pre-registrazione (§3, esclusione 2), senza l'8-K voce 2.01 -- la deposita anche chi compra o sopravvive a una fusione inversa, e non prova una sparizione.

| anno | finestra eventi | decide | uscite segnate | ufficiali ritrovate | tolte dalla fase 1 | falsi positivi | quota | con i non risolti |
|---|---|---|---:|---:|---:|---:|---:|---:|
| 2016 | ricostituzione | sì | 156 | 100.0% | 26 | 7 | **4.5%** | 5.1% |
| 2017 | ricostituzione | sì | 145 | 97.8% | 38 | 7 | **4.8%** | 5.5% |
| 2021 | ricostituzione | sì | 298 | 99.2% | 22 | 10 | **3.4%** | 3.4% |
| 2022 | ricostituzione | sì | 304 | 100.0% | 18 | 14 | **4.6%** | 4.6% |
| 2023 | ricostituzione | sì | 185 | 100.0% | 24 | 15 | **8.1%** | 10.3% |
| 2024 | ricostituzione | no | 184 | 100.0% | 31 | 23 | **12.5%** | 14.1% |
| 2024 | istantanea dopo | sì | 184 | 100.0% | 43 | 12 | **6.5%** | 7.6% |
| 2025 | ricostituzione | sì | 165 | 98.6% | 23 | 1 | **0.6%** | 0.6% |

Anni sopra la soglia del 10%, sulla misura che decide: **nessuno**.

