# Table III sul panel — la classe distingue, dentro l'universo?

> **Public copy note.** Descriptive report of 2026-09-01, not pre-registered: the starting point of the US
> insider re-test, which ended **INCONCLUSIVE** once size-matched peers and placebos were added. Read it together
> with `backtest/rematch_50_300m/STUDY.md`. Where a dilution gate appears, it is a predicate defined for these
> reports and the re-test, **not a validated filter**.

Generato il 2026-09-01. Rieseguibile con `python tools/table3_regression.py`.

Regressione di `exc_6m` sulle dummy di classe con controlli di size, book-to-market e rendimento passato, errori standard clusterizzati per emittente (sandwich CR1). **Non e' un confronto con un indice**: la domanda e' se, dentro l'universo dello scanner, la classe dell'insider separi.

## L'unita', e perche' non e' la riga del panel

Il panel e' un ri-scoring **settimanale** su finestra 60 giorni: lo stesso acquisto rientra in otto righe consecutive. Otto copie della stessa informazione non sono otto osservazioni, e il clustering CR1 assorbe la correlazione fra righe dello stesso emittente ma non il fatto che siano la stessa notizia ripetuta. Il risultato principale tiene percio' **la prima riga di ogni emittente-mese**; la versione settimanale e' in appendice, e serve a vedere di quanto le t si gonfiano.

| campione | righe |
|---|---:|
| emittente-mese (principale) | 52,863 |
| settimanale (appendice) | 175,206 |

## Niente lookahead nella classificazione

`purchase_history` e' troncata a `as_of` prima di entrare in `classify_insider`, e `classify_insider` scarta comunque da se' le date successive (`block_of`: `days <= 0` -> `None`). Verificato: la stessa storia con e senza acquisti futuri produce la stessa etichetta.

---

## Risultato principale — emittente-mese

### Specifica base

| termine | coeff. | s.e. (CR1) | t | |
|---|---:|---:|---:|---|
| intercetta | +0.2581 | 0.0492 | 5.25 | *** |
| opportunistic | +0.0090 | 0.0167 | 0.54 |  |
| novel | +0.0397 | 0.0189 | 2.10 | ** |
| sparse | +0.0158 | 0.0151 | 1.05 |  |
| log size | -0.0127 | 0.0022 | -5.87 | *** |
| B/M | +0.0057 | 0.0054 | 1.06 |  |
| rend. 12m passato | +0.0205 | 0.0093 | 2.19 | ** |

n = **42,475**, emittenti (cluster) = **2,743**. Baseline omessa: `routine`.

`*` |t| > 1,65 · `**` |t| > 1,96 · `***` |t| > 2,58.

---

## Interazioni classe x fascia di capitalizzazione

Se lo spread opportunistic-routine esiste sopra i 50M e sparisce sotto, il problema e' la soglia di universo e non il segnale.

### Con interazioni

| termine | coeff. | s.e. (CR1) | t | |
|---|---:|---:|---:|---|
| intercetta | +0.2762 | 0.1054 | 2.62 | *** |
| opportunistic | -0.0607 | 0.1006 | -0.60 |  |
| novel | -0.0564 | 0.1088 | -0.52 |  |
| sparse | -0.0631 | 0.0931 | -0.68 |  |
| bucket 50-300M | -0.0204 | 0.0932 | -0.22 |  |
| bucket >300M | -0.1127 | 0.0939 | -1.20 |  |
| opportunistic x 50-300M | +0.0272 | 0.1028 | 0.26 |  |
| opportunistic x >300M | +0.0988 | 0.1018 | 0.97 |  |
| novel x 50-300M | +0.1138 | 0.1165 | 0.98 |  |
| novel x >300M | +0.1147 | 0.1101 | 1.04 |  |
| sparse x 50-300M | +0.0412 | 0.0948 | 0.43 |  |
| sparse x >300M | +0.1080 | 0.0941 | 1.15 |  |
| log size | -0.0099 | 0.0030 | -3.24 | *** |
| B/M | +0.0060 | 0.0053 | 1.14 |  |
| rend. 12m passato | +0.0208 | 0.0093 | 2.24 | ** |

n = **42,475**, emittenti (cluster) = **2,743**. Baseline omessa: `routine`, bucket base `<50M`.

---

## Medie grezze, per controllo

| classe | n | media `exc_6m` |
|---|---:|---:|
| sparse | 39,115 | +1.30% |
| opportunistic | 8,795 | +1.20% |
| routine | 3,323 | +0.32% |
| novel | 1,630 | +3.01% |

| fascia | n | media `exc_6m` |
|---|---:|---:|
| 50-300M | 10,104 | +5.54% |
| <50M | 3,369 | +6.13% |
| >300M | 30,116 | -0.36% |
| cap ignota | 9,274 | +0.19% |

| classe x fascia | n | media `exc_6m` |
|---|---:|---:|
| novel x 50-300M | 230 | +13.01% |
| novel x <50M | 83 | +7.26% |
| novel x >300M | 1,009 | +1.28% |
| opportunistic x 50-300M | 1,904 | +4.80% |
| opportunistic x <50M | 601 | +5.79% |
| opportunistic x >300M | 4,713 | -0.49% |
| routine x 50-300M | 772 | +7.66% |
| routine x <50M | 184 | +11.98% |
| routine x >300M | 1,534 | -4.27% |
| sparse x 50-300M | 7,198 | +5.27% |
| sparse x <50M | 2,501 | +5.74% |
| sparse x >300M | 22,860 | -0.15% |

_Celle sotto le 30 osservazioni omesse._

---

## Appendice — la stessa regressione sul settimanale

Le t qui sono gonfiate per costruzione. E' il motivo per cui non e' il risultato principale.

### Specifica base, righe settimanali

| termine | coeff. | s.e. (CR1) | t | |
|---|---:|---:|---:|---|
| intercetta | +0.2147 | 0.0478 | 4.50 | *** |
| opportunistic | +0.0148 | 0.0170 | 0.87 |  |
| novel | +0.0542 | 0.0189 | 2.87 | *** |
| sparse | +0.0226 | 0.0154 | 1.46 |  |
| log size | -0.0113 | 0.0021 | -5.39 | *** |
| B/M | +0.0079 | 0.0051 | 1.56 |  |
| rend. 12m passato | +0.0207 | 0.0088 | 2.36 | ** |

n = **140,645**, emittenti (cluster) = **2,746**. Baseline omessa: `routine`.

---

## Limiti

1. **Il campione e' quello con `exc_6m`**, cioe' le righe del panel per cui esisteva una serie prezzi a 6 mesi. Gli emittenti senza serie sono andati peggio: misurato in `backtest-event-time-2026-09-01.md`, scarto **-3,36 punti**.
2. **`exc_6m` NON controlla per il fattore size.** E' excess contro il solo fattore di mercato: un premio small-cap ci finisce dentro per intero. Il coefficiente su `log size` (**-0,0127**, t -5,87) e le medie per fascia (`<50M` +6,1%, `>300M` -0,4%) sono percio' compatibili con un fattore size non controllato, non necessariamente con alfa. Il controllo si vede meglio nelle medie grezze: la fascia `<50M` e' positiva anche per i compratori **routine** (+11,98%), che sono la classe che per costruzione non dovrebbe portare informazione. Finche' `exc_6m` non e' ricalcolato contro un modello con SMB, la lettura size di questa tabella resta sospesa.
3. **`exc_6m` e' excess contro il fattore di mercato Fama-French**, come il panel lo ha calcolato ai tempi. Non e' il Russell 2000 in euro del backtest event-time: i due numeri non si sommano.
4. **Size e B/M coprono meno del campione.** La regressione gira sulle righe con cap, equity e rendimento passato tutti presenti; il conteggio effettivo e' nella riga `n` di ogni tabella.
5. **Il market cap e' agganciato per data piu' vicina <= `as_of`**, non esatta: `marketcap_rows` e' indicizzato per data di transazione e il panel per data di ri-scoring.
6. **`unseasoned` non compare**: distinguerlo da `novel` richiede la prima data di deposito del CIK, che il corpus non porta.
7. **Il clustering e' per emittente.** Non assorbe la correlazione temporale fra mesi consecutivi dello stesso emittente, solo quella fra le sue righe.
