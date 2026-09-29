# Falsi positivi della definizione dell'addendum 1 — 2025

Generato da `python backtest/russell_exits/falsi_positivi.py 2025`. Lista ufficiale FTSE Russell: 152 cancellazioni dal Russell 3000 (ricostituzione del 2025-06-27). Istantanea «dopo»: 2025-06-30. Eventi societari contati fino al 2025-06-27 (ricostituzione). Nessun rendimento calcolato.

Falso positivo = segnata come uscita verso il basso, non nella lista ufficiale.

| | abbinamento per CUSIP esatto | abbinamento per emittente |
|---|---:|---:|
| cancellazioni ufficiali trovate in IWM a marzo (ticker o nome) | 141 | 141 |
| … segnate come uscite verso il basso (**ritrovate**) | 140 (99.3%) | 139 (98.6%) |
| uscite segnate | 174 | 165 |
| nella lista ufficiale | 142 | 141 |
| **falsi positivi** | **32 (18.4%)** | **24 (14.5%)** |
| … stesso emittente con un CUSIP nuovo | 8 | 0 |
| … acquisita, in fusione o delistata nel trimestre | 23 | 23 |
| … senza spiegazione | 1 | 1 |
| falsi positivi senza le acquisite o delistate nel trimestre (escluse comunque in fase 1) | 9 (5.2%) | 1 (0.6%) |

Metodo della quota residua (abbinamento per emittente): azioni rettificate 93, assente 58, quota del capitale 13, azioni non rettificate (né serie né azioni XBRL) 1.

**Soglia dell'utente (10% dei casi dell'anno): superata.**

_Copia pubblica: gli elenchi per titolo di questa sezione e delle seguenti sono stati tolti; restano le tabelle aggregate._
