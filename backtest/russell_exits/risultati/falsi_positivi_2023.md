# Falsi positivi della definizione dell'addendum 1 — 2023

Generato da `python backtest/russell_exits/falsi_positivi.py 2023`. Lista ufficiale FTSE Russell: 173 cancellazioni dal Russell 3000 (ricostituzione del 2023-06-23). Istantanea «dopo»: 2023-06-30. Eventi societari contati fino al 2023-06-23 (ricostituzione). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 124 | 124 |
| … segnate come uscite verso il basso (**ritrovate**) | 124 (100.0%) | 124 (100.0%) |
| uscite segnate | 186 | 185 |
| nella lista ufficiale | 142 | 142 |
| **falsi positivi** | **44 (23.7%)** | **43 (23.2%)** |
| … stesso emittente con un CUSIP nuovo | 3 | 2 |
| … acquisita, in fusione o delistata nel trimestre | 24 | 24 |
| … senza spiegazione | 17 | 17 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 20 (10.8%) | 19 (10.3%) |

Metodo della quota residua (abbinamento per emittente): assente 174, quota del capitale 5, azioni rettificate 5, azioni non rettificate (né serie né azioni XBRL) 1.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
