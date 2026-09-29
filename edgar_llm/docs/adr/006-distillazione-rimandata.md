# ADR-006 — La distillazione non si decide adesso

Data: 2026-09-02 · Stato: accettata

## Contesto

La Componente 3 (normalizzatore delle footnote Form 4) prevede due fasi:
etichettare con un modello grande, poi valutare se distillare su uno piccolo per
il volume.

## Decisione

La fase (b) non si progetta finche' non esistono i costi reali della (a).
Nessun lavoro su modelli locali, quantizzazione o fine-tuning entra nel piano.

## Alternative scartate

Predisporre adesso l'astrazione «cambio modello», per non rifattorizzare dopo.
Il volume atteso e' di ~29 documenti al giorno (`docs/costs.md`), un costo che
di per se' non giustifica una distillazione: il numero che la giustificherebbe
non e' stato misurato, e senza quel numero l'astrazione difende da un problema
che potrebbe non esistere.

## Conseguenze

`client.py` isola comunque il nome del modello, perche' serve gia' alla chiave
di cache (ADR-005). Nient'altro viene predisposto.
