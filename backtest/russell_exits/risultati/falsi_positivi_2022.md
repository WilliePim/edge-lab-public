# Falsi positivi della definizione dell'addendum 1 — 2022

Generato da `python backtest/russell_exits/falsi_positivi.py 2022`. Lista ufficiale FTSE Russell: 298 cancellazioni dal Russell 3000 (ricostituzione del 2022-06-24). Istantanea «dopo»: 2022-06-30. Eventi societari contati fino al 2022-06-24 (ricostituzione). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 259 | 259 |
| … segnate come uscite verso il basso (**ritrovate**) | 259 (100.0%) | 259 (100.0%) |
| uscite segnate | 307 | 304 |
| nella lista ufficiale | 272 | 272 |
| **falsi positivi** | **35 (11.4%)** | **32 (10.5%)** |
| … stesso emittente con un CUSIP nuovo | 3 | 0 |
| … acquisita, in fusione o delistata nel trimestre | 18 | 18 |
| … senza spiegazione | 14 | 14 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 17 (5.5%) | 14 (4.6%) |

Metodo della quota residua (abbinamento per emittente): assente 295, azioni rettificate 5, quota del capitale 4.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
