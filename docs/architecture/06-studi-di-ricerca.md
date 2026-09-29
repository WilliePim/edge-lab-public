# 6 · Come si svolge uno studio di ricerca

> Ogni studio parte da una pre-registrazione e ha due fermate. Alla prima si guardano solo i conteggi e si aspetta la
> conferma dell'utente. Alla seconda arriva il verdetto, con il referto.

<!-- diagramma: 06-studi-di-ricerca.mmd -->
**[▶  Apri il diagramma nell'editor Mermaid](https://mermaid.live/edit#pako:eNqFV9tu4zYQ_RVCQW-AjbUk32IsUtiSVRRIi4W3XbSp-0BLtENEFlWKym6z2H_pB_S96Gv3x3qGlGw562zyYELk8HBmzpkh895LVSa8GfP6_f66MNLkYsYitReskqy6V_lOsLpQrDJ1JhXLJNMyFTrl6yJVxVbuZuuCMXMr9ti34ZU4fL7hWvJNLiprwdhWFea1fIDZ2vNH5bu15-ZzWYhI5UrTwsV4OBlOF-1amteVEXpxt7OLySgJk-TxotKZcJvnk-kimbv1ba7eprdcm-b4tNb3zkVZuZmSZ5ksgOwP14UN_7CH_RQ7m6re7DQvb9mrwW9rb8D--4e90nLPKRGmNkatvd-dJf3Nv4ZRLLUwRt7DRuT5V7URhREw-2Y2m8lCPiCL_f4VW8D0lRZ9LXayMppjvhCzlxv94ipTe15kosewpnKMldrlEuO9QKjAZqWqKrmRuQQuYLdN3hkTRbYuHrvu4yifXI-5kT0G3pD0vQROJtNbyTWmT-KIacfrZcQyldZ7-K9YKfTxy3pJMHXBDByyuiCkPbehnrhkAYP3a2-eY7NiU_bdwgLkciM0RFZjd5Wqb9feB2zMRCorykVndwh35hoH3EtGbsmCbXKVps4R5IEXqWQCCUdiXFyWHcFy6FilUpiPf531a-hYeHjAHg62uDvFBrTn-k6YfsYNt-eAA1cGrJQf_wUZKWxn7Fd-q9T5oEE0qz7-bfmOww5Dx-XCqeEXn6QTSaq6rdB7dyL8VzQDmloFVUaVnzIcYHNADEcKWqqtlkh-LOX70iazS29E9P5cSMipQqQC3KEqzoUQEfA1GK41t4atBORBAk6jbCurCgotRFVBFNfXP5yFCyGDNyB9K1POODJMnaVm4cB64NRf6lYBjDvFXA6-eFocEVEY5RwFQaht6C6mJougUBCjqHYNB8-yFY2Ak8jcaCufP2qeS6jGIlRoT7ZsACRBGX44LFDenKb4Wbwx1VCjPZC4R7XCmGC2Gq2Q67OVEvlWD1HghrCbvK6coqEbRm4YPxKXM27FFTwS12e1RMUWkpYSMjWc-SfiSUg8EQIQu51tJugMkAe4p4TbPpFSYmziXm6uGkVouCZdK9nVXCNr6uWLzZVLATLKOydQs7huGmerM-v30ypIbIvIMpxS7y0nxjGWkxicuVNDRsxJmm-UW8AKZbKREOM5RhLHSBJ0PexSkTyubLe89g4HE-8lZUAQ6W6T_2nmSclDW8U8TyG5k7yvKO-rYxbFO1waFKLRqtvmGqmdi2QVNNRplefoXGXOU7FRPXtv2xaulDai12gefb0POqXKwHMlCnfjPNFJVy5Lq-Az9xBV2KirrOAkwhsfvEdaGroVys7VSLfTE7zfWGmvoMW2Qaq7zmpIq9_TS4UeC_JeNUangrsZktmPrpntTjvt0Tkb303AvgQs_Qw7iyPrBDRq1AyXItjmO4kBF5U0aCSQVtOK6uIrXpZEYyqsQOmeQmdiBfqqPktb90znxOiTJC_cHePDKCbzuPHOzYR2xnUKv2kQ44MMXf04-prPlWs_NweRptRgY7FlzQtmK_N8drFI4kWy7IEjdSdmF8FoHC4XvdQ-5i78ZTifzpvF_luZmdtZgGffKR6F2qAtB8tJkhzQxuF4nPgtWugHy6n_HNpBIQ1kEi_HBx9mF_HlZDIYt5CTaTgaJM9BklRaB-FCMjigXQ7n4WJ6DDe4DBfPoZGoWt-W0Tzq-BYF4-DoW-LHfvwcmrpriVgkk_jomT-eh8P5wbPhKAzOYXk95u2pFGVG_wGg-uzDfe3RY9q-5b0PZMNro17_WaSYx-MCnd6rS7pSY8lR2fvjtFb17hafW57TY8AreXGjVGvw4X9H6uBr)**

## Cosa racconta

La forma comune degli studi in `backtest/`: script lanciati a mano uno dopo l'altro, e ciascuno lascia un file per il
successivo. Il diagramma segue lo studio E3 (IPO rotte e forti), il più recente e il più completo.

## Passo per passo

1. **Pre-registrazione.** Domande, regole e soglie si scrivono prima di guardare qualunque dato.
2. **Dati.**
   - Chiamate alla SEC con un tetto dichiarato.
   - Archivi SEC in blocco, scaricati solo con almeno 8 GB liberi.
   - Prezzi dall'archivio di market-data (`market_data.api`, dati fuori dal repo); gli studi più vecchi usano Yahoo.
3. **Campione.** Nell'ordine:
   - si leggono i documenti con regole fisse;
   - si verificano a mano 30 casi, e sotto il 90% di precisione ci si ferma;
   - poi classificazione, filtri con i soli dati noti a quella data, società simili.
4. **Fermata 1.** Solo conteggi. Le decisioni dell'utente finiscono in un addendum datato, e da lì le regole non
   cambiano più.
5. **Calcolo e fermata 2.** Rendimenti, controlli, verdetto secondo i criteri pre-registrati, referto.

## Dove sta nel codice

| passo | file |
|---|---|
| percorsi, tetto, calendario | `backtest/ipo_e3/comune.py` |
| archivi in blocco | `backtest/ipo_e3/bulk.py` |
| campione | `universo.py` → `leggi_prospetti.py` e `prospetto.py` → `verifica.py` → `casi.py` → `filtri.py` → `peer.py` |
| fermata 1 | `conteggi.py`, pre-registrazione e addendum in `backtest/ipo_e3/` |
| calcolo e fermata 2 | `analisi.py` → `sensibilita.py` → `referto.py` |
| moduli riusati | `backtest/russell_exits/` (`sec.py`, `serie_eodhd.py`, `rendimenti.py`, `filtri_xbrl.py`, `ingressi.py`) |

## Note

- **Un confine controllato da un test.** Verso l'archivio prezzi il confine è controllato:
  `tests/test_market_data_confine.py` ammette solo `market_data.api`.
- **Moduli condivisi via `sys.path`.** Gli studi si passano il codice aggiungendo cartelle al percorso di Python, non
  come pacchetti.
- **Tetto di default e tetto usato.** Il tetto di chiamate di `russell_exits/sec.py` vale 300 di default, ma tutti gli
  studi recenti passano 3000.
