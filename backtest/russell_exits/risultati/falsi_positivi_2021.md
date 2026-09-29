# Falsi positivi della definizione dell'addendum 1 — 2021

Generato da `python backtest/russell_exits/falsi_positivi.py 2021`. Lista ufficiale FTSE Russell: 292 cancellazioni dal Russell 3000 (ricostituzione del 2021-06-25). Istantanea «dopo»: 2021-06-30. Eventi societari contati fino al 2021-06-25 (ricostituzione). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 247 | 247 |
| … segnate come uscite verso il basso (**ritrovate**) | 245 (99.2%) | 245 (99.2%) |
| uscite segnate | 304 | 298 |
| nella lista ufficiale | 266 | 266 |
| **falsi positivi** | **38 (12.5%)** | **32 (10.7%)** |
| … stesso emittente con un CUSIP nuovo | 6 | 0 |
| … acquisita, in fusione o delistata nel trimestre | 22 | 22 |
| … senza spiegazione | 10 | 10 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 16 (5.3%) | 10 (3.4%) |

Metodo della quota residua (abbinamento per emittente): assente 294, azioni rettificate 3, quota del capitale 1.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
