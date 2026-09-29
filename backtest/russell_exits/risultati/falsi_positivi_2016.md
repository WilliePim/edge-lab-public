# Falsi positivi della definizione dell'addendum 1 — 2016

Generato da `python backtest/russell_exits/falsi_positivi.py 2016`. Lista ufficiale FTSE Russell: 129 cancellazioni dal Russell 3000 (ricostituzione del 2016-06-24). Istantanea «dopo»: 2016-06-30. Eventi societari contati fino al 2016-06-24 (ricostituzione). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 104 | 104 |
| … segnate come uscite verso il basso (**ritrovate**) | 104 (100.0%) | 104 (100.0%) |
| uscite segnate | 168 | 156 |
| nella lista ufficiale | 122 | 122 |
| **falsi positivi** | **46 (27.4%)** | **34 (21.8%)** |
| … stesso emittente con un CUSIP nuovo | 12 | 0 |
| … acquisita, in fusione o delistata nel trimestre | 26 | 26 |
| … senza spiegazione | 8 | 8 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 20 (11.9%) | 8 (5.1%) |

Metodo della quota residua (abbinamento per emittente): assente 153, quota del capitale 2, azioni rettificate 1.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
