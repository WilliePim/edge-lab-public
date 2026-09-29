# ADR-007 — pytest dentro edgar_llm/, harness fuori

Data: 2026-09-02 · Stato: accettata

## Contesto

Il repository che ospita questo package non usa pytest: le sue tredici suite
sono script piatti su un harness minimale, che eseguono all'import e riportano
insieme tutte le asserzioni fallite. Questo package e' pero' destinato a essere
letto da estranei, e i test che chiamano davvero l'API vanno esclusi dal run di
default — cosa che i marker di pytest fanno e un harness fatto in casa no.

## Decisione

`edgar_llm/tests/` gira con pytest, marker `llm` per cio' che chiama l'API. Il
resto del repo resta sull'harness. `test.sh` lancia entrambi.

## Alternative scartate

- Harness ovunque: un solo attrezzo, ma il marker diventa una variabile
  d'ambiente e il repo pubblico mostra un harness fatto in casa dove ci si
  aspetta pytest.
- pytest ovunque: riscrivere tredici suite che funzionano, per uniformita'.

## Conseguenze

Due convenzioni nello stesso repo. Il confine e' la directory, ed e' lo stesso
confine del perimetro pubblico: nessuna ambiguita' su quale valga dove.
