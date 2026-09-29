# Fixture positive della guardia del perimetro

Ogni file qui dentro **deve** far scattare esattamente un controllo di
`edgar_llm/tools/perimeter_check.py`. Il nome del file e' lo slug del
controllo che deve scattare.

Sono violazioni sintetiche: valori palesemente finti, nessun segreto reale,
nessun dato di nessuno. Una chiave qui dentro e' `sk-ant-EXAMPLE000` e non
somiglia a niente che esista.

## Perche' esistono

Un controllo che non ha mai fallito apposta non e' un controllo dimostrato.
Una guardia rotta e un perimetro pulito producono lo stesso output --
silenzio -- e la differenza si vede solo mettendole davanti a qualcosa che
DEVE fermarle. Vedi `../../../docs/postmortems/PM-001-the-silent-guard.md`.

## Perche' non fanno fallire la pubblicazione

Questa directory e' esclusa dalla scansione (`FIXTURES` in
`perimeter_check.py`), altrimenti il mirror non partirebbe mai. L'esclusione e'
per percorso esatto, e a sua volta sorvegliata: la suite verifica che qui
dentro ci siano **esattamente** le fixture dichiarate e nient'altro, cosi'
l'unica zona non scandita del perimetro non puo' diventare un nascondiglio.
