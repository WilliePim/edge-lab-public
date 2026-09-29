# Falsi positivi della definizione dell'addendum 1 — 2024

Generato da `python backtest/russell_exits/falsi_positivi.py 2024`. Lista ufficiale FTSE Russell: 144 cancellazioni dal Russell 3000 (ricostituzione del 2024-06-28). Istantanea «dopo»: 2024-09-30 (spostata: il 30 giugno cade di domenica, zero sedute dopo la ricostituzione del 28: solo 17 entrate contro 190-285). Eventi societari contati fino al 2024-09-30 (istantanea dopo). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 122 | 122 |
| … segnate come uscite verso il basso (**ritrovate**) | 122 (100.0%) | 122 (100.0%) |
| uscite segnate | 191 | 184 |
| nella lista ufficiale | 129 | 127 |
| **falsi positivi** | **62 (32.5%)** | **57 (31.0%)** |
| … stesso emittente con un CUSIP nuovo | 6 | 1 |
| … acquisita, in fusione o delistata nel trimestre | 43 | 43 |
| … senza spiegazione | 13 | 13 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 19 (9.9%) | 14 (7.6%) |

Metodo della quota residua (abbinamento per emittente): assente 180, quota del capitale 4.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
