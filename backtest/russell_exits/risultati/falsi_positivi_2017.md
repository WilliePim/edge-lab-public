# Falsi positivi della definizione dell'addendum 1 — 2017

Generato da `python backtest/russell_exits/falsi_positivi.py 2017`. Lista ufficiale FTSE Russell: 108 cancellazioni dal Russell 3000 (ricostituzione del 2017-06-23). Istantanea «dopo»: 2017-06-30. Eventi societari contati fino al 2017-06-23 (ricostituzione). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 91 | 91 |
| … segnate come uscite verso il basso (**ritrovate**) | 89 (97.8%) | 89 (97.8%) |
| uscite segnate | 147 | 145 |
| nella lista ufficiale | 99 | 99 |
| **falsi positivi** | **48 (32.7%)** | **46 (31.7%)** |
| … stesso emittente con un CUSIP nuovo | 2 | 0 |
| … acquisita, in fusione o delistata nel trimestre | 38 | 38 |
| … senza spiegazione | 8 | 8 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 10 (6.8%) | 8 (5.5%) |

Metodo della quota residua (abbinamento per emittente): assente 143, quota del capitale 2.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
