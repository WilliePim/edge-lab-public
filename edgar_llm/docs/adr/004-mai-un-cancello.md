# ADR-004 — L'estrazione arricchisce, non decide mai

Data: 2026-09-02 · Stato: accettata

## Contesto

`CLAUDE.md` ammette nello scanner solo fatti «con una regola dichiarata e
riproducibile». Un'estrazione LLM non e' riproducibile: due chiamate identiche
possono dare due risposte.

Il caso che ha motivato il modulo — ITT flaggata `+15% in 12m` per
un'acquisizione — e' esattamente il caso in cui verrebbe voglia di lasciar
correggere il verdetto al modello.

## Decisione

L'output non tocca il verdetto del cancello, non entra nel punteggio e non
cambia l'ordinamento del report. Compare in una colonna, con la citazione che
lo giustifica. Se l'API non risponde, la pipeline produce lo stesso identico
report di prima.

Concretamente: **ITT resta BLOCKED.** Cambia che chi legge vede
`M&A_issuance (high)` accanto al verdetto invece di dover aprire EDGAR.

## Alternative scartate

Far declassare il veto all'estrazione quando il tipo e' `M&A_issuance`. E' la
cosa utile, ed e' la cosa che va misurata prima: quante volte l'estrazione ha
ragione, su un corpus, contro quante volte aveva ragione il veto. Finche' quel
numero non esiste, sostituirlo con un'intuizione e' il modo in cui e' morto il
rubric v2.

## Conseguenze

Il valore del modulo, oggi, e' che un umano legge meno EDGAR. Non che il filtro
migliori. Va detto cosi', anche nel README.
