# Addendum del 22 settembre 2026 — la fermata 1 rifatta dopo le tre decisioni

Addendum alla pre-registrazione del 16 settembre (`2026-09-16_preregistrazione.md`). Scritto **prima di calcolare o
guardare qualunque rendimento extra**. Non cambia domande, verdetti, soglie, filtri, peer, ingressi né placebo: cambia
le fonti e il 2019/2024, come il §9 prevedeva («da rifare dopo le decisioni dell'utente sulla definizione, sul 2024 e
sulla fonte dei prezzi»). Decisioni tecniche in `DECISIONS.md`, ADR-041.

## Che cosa cambia rispetto al testo del 16 settembre

| § | testo del 16 settembre | ora | decisione |
|---|---|---|---|
| 3 | uscita = assente dall'istantanea del 30 giugno | assente o al massimo il 50% delle azioni di marzo rettificate, non in IWB, abbinamento per emittente | ADR-039, addendum 1 |
| 3 | istantanea «dopo» del 30 giugno per ogni anno | **30 settembre per il 2019 e il 2024** (il 30 giugno cade di domenica, zero sedute dopo la ricostituzione) | utente, 17-09 |
| 3 | eventi societari fra il 31 marzo e la ricostituzione | fra le due istantanee confrontate: per il 2019 e il 2024 fino al 30 settembre, a condizione che ogni sparizione estiva esclusa abbia il suo deposito EDGAR | utente, 22-09 |
| 3 | identità verificata sui prezzi Yahoo | sui prezzi dell'**archivio EODHD**, che conserva i delistati | utente, 22-09 |
| 2, 6 | chiusure e volumi Yahoo (`Close`, `Adj Close`, `Volume`) | chiusure e volumi **EODHD**: la `Close` rettificata per i soli frazionamenti si ricostruisce dalla grezza, il volume EODHD è già rettificato come quello Yahoo | ADR-040, ADR-041 |
| 2 | — | prezzi **puliti**: fuori i periodi esclusi dai controlli di qualità dell'archivio e le chiusure a zero | ADR-041 |

## Quali anni sono verificati sulle liste ufficiali

La definizione delle uscite è stata confrontata con la lista finale FTSE Russell delle cancellazioni per il 2016, 2017,
2021, 2022, 2023, 2024 e 2025: nessun anno sopra il 10% di falsi positivi (`risultati/falsi_positivi_ricalcolati.md`).
**Non verificati**: 2015 (lista non cercata), 2018 e 2019 (nessuna lista finale pubblica), 2020 (esiste solo
l'aggiornamento del 19 giugno). Entrano nel campione, dichiarati come tali.

## La fermata 1

Tabelle complete in `risultati/conteggi.md`. Nessun rendimento calcolato.

**Casi per anno** (uscite verso il basso dopo identità, eventi societari, prezzi, SPAC, i quattro filtri e almeno 3
peer):

| 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | **totale** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 10 | 5 | 11 | 35 | 26 | 61 | 26 | 9 | 11 | 12 | **230** |

Il criterio 1 di REGGE chiede almeno 100 casi e almeno 9 anni con casi: sulla cella del verdetto B2 × 252 i casi
disponibili sono **227 in 11 anni**.

**Copertura dell'identità** fra le uscite: dall'88,5% (2015) al 95,8% (2025). Con Yahoo era dal 23% al 74%.

**Copertura dei prezzi** fra le uscite che superano gli eventi societari: dal 73,6% (2016) all'89,5% (2025). Le 331
escluse per prezzi e volumi insufficienti comprendono quelle con buchi dovuti ai controlli di qualità dell'archivio.

**Il collo di bottiglia sono i filtri di qualità** (§4): su 1.364 uscite che ci arrivano, il flusso di cassa operativo
positivo lo passano 579, lo falliscono 635 e non è verificabile per 150. Le small cap che escono dal Russell 2000
bruciano cassa in quasi la metà dei casi. È la regola pre-registrata e non cambia.

**Giorni d'ingresso**, in sedute dopo la ricostituzione:

| scaglione | N – limite | minimo | primo quartile | mediana | terzo quartile | massimo | agli estremi |
|---|---|---:|---:|---:|---:|---:|---:|
| B1 | 10 – 60 | 10 | 11,8 | 20 | 37 | 60 | 35,7% |
| B2 | 20 – 126 | 20 | 20 | 31,5 | 63,2 | 126 | 33,0% |
| B3 | 40 – 189 | 40 | 42 | 62 | 98,2 | 189 | 34,3% |

Nessun ingresso non decidibile. In nessuno scaglione più della metà degli ingressi cade al primo giorno possibile o al
limite: la regola distingue.

**Falsi eventi per il placebo**: 230, uno per ogni caso dell'anno, tutti con ingresso B2 decidibile.

## Correzione del 22 settembre, dopo la conferma e prima di qualunque rendimento

Preparando il calcolo dei rendimenti si è trovato un difetto: da quando la cache EDGAR si scrive compressa, il codice
che legge i depositi dal disco (`survival.submissions`) cercava solo i file vecchi in chiaro, e per 356 società con
identità verificata rispondeva «nessun deposito». Fra le uscite verso il basso ne erano colpite 154. Per loro la fase 1
non vedeva gli eventi societari e il filtro 4 risultava non verificabile, cioè il titolo usciva. Corretto (commit
`f4a7042`); nessuna regola è cambiata, e **nessun rendimento era stato calcolato**.

Con la correzione la fermata 1 diventa:

| 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | **totale** |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **25** | 10 | 5 | 11 | 35 | 26 | **64** | 26 | 9 | 11 | 12 | **234** |

Erano 230 (+1 nel 2015, +3 nel 2021). La cella del verdetto B2 × 252 ha **231 casi in 11 anni**. L'universo dei peer
cresce di più, soprattutto nel 2015 (da 355 a 411) e nel 2016 (da 343 a 379), per la stessa ragione: rimasti che prima
uscivano per il filtro 4 «non verificabile». Falsi eventi: 234, uno per caso. Le misure dei falsi positivi rifatte
scendono o restano uguali in ogni anno (`risultati/falsi_positivi_ricalcolati.md`): nessun anno sopra il 10%, il 2024
con la finestra di settembre al 6,5%, e ogni sua sparizione estiva esclusa ha il suo deposito EDGAR (11 con Form 25,
15-12 o 8-K 1.03; Desktop Metal con la sola proxy di fusione, modulo elencato dal §3).
