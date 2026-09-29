# ADR-001 — Il modulo vive accanto ai suoi consumatori, non nel monorepo

Data: 2026-09-02 · Stato: accettata

## Contesto

L'handoff collocava il modulo in un monorepo separato. I due consumatori
dell'estrazione stanno pero' in un altro repository: il modulo del veto
diluizione e quello che assembla il report giornaliero.

La documentazione di quel repository fissa la direzione della dipendenza: «il
monorepo conosce questo repo, questo repo non conosce il monorepo».

## Decisione

`edgar_llm/` sta nel repository che contiene i suoi consumatori. Il mirror
pubblico e' uno subtree split di **quel** repository.

## Alternative scartate

Modulo nel monorepo. Per far comparire una colonna nel report giornaliero
occorrerebbe che lo scanner importasse dal monorepo: la freccia si invertirebbe,
e con essa una regola che regge da mesi. Il costo di quel cambio e' molto
maggiore del beneficio di stare vicini al resto del sistema.

## Conseguenze

I vincoli del repository ospite valgono anche dentro il perimetro pubblico:
dataclass frozen, dipendenze contate, niente giudizi nell'output.
Vedi ADR-002 e ADR-004.

## Nota sul nome

Questo documento non nomina ne' il monorepo ne' il repository ospite. Non e'
reticenza: un lettore pubblico non ha quei file, il nome non gli serve, e il
perimetro e' un confine che vale anche per la prosa. Il controllo
`nome-repo-privato` in `tools/perimeter_check.py` lo fa rispettare.
