# Pre-registrazione — addendum 2

Scritto il **2026-09-15, prima di calcolare qualunque rendimento sul calendario comune.**
Corregge una formulazione del §7 di [`2026-09-15_preregistration.md`](2026-09-15_preregistration.md)
(commit `130b0fe`). Trovata scrivendo il ponte del passo 1. Decisione: ADR-020 in
[`DECISIONS.md`](../DECISIONS.md).

## Il difetto

Il §7 dice: «Prezzo di ciascuna gamba a una sessione = ultimo close del titolo con data ≤
sessione, entro 5 sessioni». **All'ingresso questo ammette un prezzo anteriore alla
pubblicazione.** Se il titolo non scambia nella prima sessione dopo il deposito, l'ultimo close ≤
quella sessione è il close del giorno del deposito o di prima: si comprerebbe a un prezzo che
precede l'informazione. È un lookahead, e va a favore dell'evento.

L'originale non lo fa: l'ingresso è la prima barra del titolo **strettamente successiva** al
deposito (`tools/backtest_event_time.py`, righe 267–275).

## La regola corretta

Per la **gamba dell'evento**:

- s0 = prima sessione IWM successiva al deposito.
- **Ingresso** = prima barra del titolo con data ≥ s0, se cade entro 5 sessioni da s0. La sessione
  IWM di quella barra è **e0**. Nessuna barra entro 5 sessioni → `NO_ENTRY_BAR`, contato. **Mai un
  prezzo anteriore a s0.**
- **Uscita** = sessione e0 + h. Prezzo = ultimo close ≤ quella sessione, entro 5 sessioni.
- Serie finita prima dell'uscita e più di 10 sessioni prima della fine della cache → delistato,
  ultimo close tenuto piatto (`ENDED_IN_WINDOW`, ADR-010).
- Serie viva ma ultimo close più vecchio di 5 sessioni all'uscita → `STALE_EXIT`, escluso e
  contato.
- e0 + h oltre l'ultima sessione della cache → `TOO_RECENT`.

Per le **gambe del peer e di IWM**: ultimo close ≤ sessione entro 5 sessioni, alle sessioni **e0** ed
**e0 + h** dell'evento. Qui un prezzo precedente non porta informazione sull'evento, e tenere le
stesse due sessioni per le tre gambe è ciò che rende esatta la scomposizione.

Cambio `EURUSD=X` alla data di ciascuna sessione. \|r\| > 500% su qualunque gamba → escluso e contato.

## Cosa non cambia

Tutto il resto delle due pre-registrazioni. Il passo 1 replica l'originale con il suo codice e non
usa questa regola; la usa solo il ponte del passo 1 e poi i passi 2–4.
