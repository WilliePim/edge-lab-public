# ADR 004 — lo scanner usa market-data come libreria; i backtest pre-registrati restano su Yahoo

**Data:** 2026-09-17 · **Stato:** accettata (decisione dell'utente) · **Specchio:** `DECISIONS.md` di edge-lab (prezzi EODHD, market-data come libreria)

## Contesto

Lo scanner (oggi edge-lab) era un repo separato da quello che ospitava market-data, con la regola «questo repo non
conosce il repo ospite». I suoi backtest leggono prezzi Yahoo da CSV con percorsi fissi; `state/backfill/prices/` è
congelato da impronta sha256 nelle pre-registrazioni.

## Decisione

1. **market-data si installa come libreria** nell'ambiente dello scanner (`pip install -e <repo ospite>/market-data`).
   Lo scanner dipende solo dal package `market_data` e solo da **`market_data.api`**: mai dai file dell'archivio, mai
   da altri moduli di market-data, mai dal repo ospite. La regola di dipendenza dello scanner resta vera: conosce una
   libreria installata, come conosce `yfinance`.
2. **I backtest già pre-registrati restano sui prezzi Yahoo congelati.** Cambiare fonte cambierebbe risultati già
   fissati e romperebbe le impronte.
3. **Solo i backtest nuovi usano EODHD, a partire dal Russell** (ramo `feat/russell-exits`).
4. La scelta della fonte per un backtest nuovo sta nella sua pre-registrazione, non in una variabile globale.

## Conseguenze

- L'installazione nell'ambiente dello scanner avviene quando `market_data.api` restituisce dati (fase 3).
- Un test nello scanner dovrà verificare che nessun modulo importi `market_data` fuori da `market_data.api`.

## Aggiornamento del 2026-09-27

market-data vive dentro edge-lab (ADR 007): l'installazione è `pip install -e ./market-data[archivio]` dal repo
stesso. La regola del punto 1 resta: fuori da `market-data/`, edge-lab dipende solo da `market_data.api`
(`tests/test_market_data_confine.py`). Non vale più «mai dal repo ospite», perché non c'è più un repo di mezzo: edge-lab
non dipende da nessun repo esterno.
