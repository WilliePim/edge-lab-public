# Validazione della tabella degli split di Yahoo

Generato da `python backtest/splits.py valida`. Addendum 5 §4. Zero chiamate di rete.

| esito | split |
|---|---:|
| CONFERMATO | 590 |
| DISCORDE | 65 |
| NON_VERIFICABILE | 1,204 |
| PIATTO | 31 |

**CONFERMATI / verificabili = 590 / 686 = 86.0%**, soglia 90%: **tabella NON VALIDA, nessuna correzione**.

## Discordi

65 split discordi. *(Copia pubblica: la tabella per ticker — data, rapporto di Yahoo, atteso e osservato
dai prezzi insider ÷ `adj_close` — è stata tolta, perché derivata dai prezzi Yahoo titolo per titolo.)*
