# ADR-005 — La chiave di cache include prompt e modello

Data: 2026-09-02 · Stato: accettata

## Contesto

L'handoff chiede «hash del documento → risultato estrazione», e in parallelo la
regola «nessun prompt si cambia senza rieseguire le evals».

Le due cose non stanno insieme. Con la chiave sul solo documento, cambiare il
prompt e rilanciare le evals restituirebbe i risultati del prompt vecchio, dalla
cache, senza una sola chiamata: la regola sarebbe inapplicabile per costruzione
e sembrerebbe rispettata. Un'eval che non chiama nulla passa sempre.

## Decisione

`sha256(testo_inviato + prompt_version + model)`.

Due modi: `record` chiama l'API e scrive; `replay` legge solo la cache e
fallisce se manca. La CI gira in `replay` — deterministica, senza chiave, a
costo zero.

## Conseguenze

Un cambio di prompt invalida la cache e va ripagato. E' il prezzo che rende
onesta la misura, ed e' noto: `docs/costs.md` lo quantifica.
