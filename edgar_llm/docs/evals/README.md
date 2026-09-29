# Evals — metodologia

Il numero che decide se il modulo va in produzione e' uno: **accuracy su `tipo`
>= 90%** sul golden set. Tutto il resto e' diagnostica che serve a capire dove
si perde.

## Il golden set

Etichettato a mano, un documento alla volta, con
`python -m edgar_llm.label`. Chi etichetta vede **le finestre**, non il
documento intero: esattamente cio' che vedra' il modello. Il contrario
misurerebbe la capacita' di una persona di leggere un prospetto, non quella del
modello di leggerne un estratto.

Il repo **non versiona il testo dei filing**. Ogni golden porta `accession`,
`source_url`, lo `sha256` del testo estratto e le etichette.
`goldens.rehydrate` riscarica da EDGAR e verifica lo sha: se il testo e'
cambiato — documento sostituito, o conversione HTML→testo modificata sotto i
piedi — **il golden esce dal campione e la corsa lo dichiara**. Un golden set
che si adatta in silenzio a cio' che il codice fa adesso non misura piu' niente.

Composizione: filing pubblici EDGAR scelti neutri. L'unico nome dichiarato e'
il caso studio ITT/SPX FLOW, che e' un esempio tecnico di falso positivo.

## Come si confrontano cinque campi di natura diversa

| campo | confronto | perche' |
|---|---|---|
| `tipo` | uguaglianza | enumerazione chiusa di sette valori |
| `data_efficacia` | uguaglianza, nessuna tolleranza | una data e' giusta o non lo e' |
| `importo_usd` | scarto < $1, piu' errore assoluto mediano | e' un numero, e sbagliarlo di poco non e' come sbagliarlo di molto |
| `controparte` | contenimento normalizzato | «Jefferies» e «Jefferies LLC» sono la stessa risposta. **E' generoso, ed e' dichiarato** |
| `condizioni` | **non si punteggia** | e' prosa: due sintesi corrette possono non avere una parola in comune. Se ne riporta solo la copertura |

## I cinque esiti, e perche' non sono due

| esito | atteso | estratto | conta come |
|---|---|---|---|
| `ok` | c'e' | uguale | giusto |
| `ko` | c'e' | diverso | sbagliato |
| `entrambi_null` | non c'e' | non c'e' | **giusto** |
| `mancante` | c'e' | non c'e' | sbagliato |
| `inventato` | non c'e' | c'e' | sbagliato |

`entrambi_null` conta come giusto: dire «il documento non lo dice» quando il
documento non lo dice e' la risposta corretta, non un'astensione. Tenere
separati `mancante` e `inventato` serve perche' sono guasti opposti — reticenza
contro allucinazione — e si correggono con modifiche opposte al prompt.

Un campo estratto sotto la soglia di revisione (`low`) conta come `mancante`:
non e' usabile a valle, quindi per la misura non c'e'.

## Di chi e' l'errore: del modello o del taglio

Un'accuracy bassa su una forma di deposito ha due spiegazioni opposte, e
confonderle costa il lavoro successivo. Per ogni campo sbagliato o mancante si
cerca la **forma superficiale del valore vero** — quello scritto da una persona
— prima nelle finestre inviate, poi nel documento intero:

| esito | significato | cosa si cambia |
|---|---|---|
| `dentro` | l'informazione era nel prompt e il modello non l'ha usata | il prompt |
| `fuori` | non gliel'abbiamo mandata | il taglio del documento |
| `assente` | non c'e' ne' qui ne' la' | l'etichetta, o la conversione HTML→testo |
| `n.d.` | il campo non ha una forma da cercare | niente: e' un limite dichiarato |

Le varianti contano. «$0.7 billion» e «$700,000,000» sono lo stesso numero e un
documento ne usa una sola; «LSF11 Redwood Parent, L.P. (Seller)» compare senza
la glossa fra parentesi. Cercare la stringa letterale direbbe «fuori finestra»
su un documento che l'informazione ce l'aveva — e manderebbe a riscrivere il
taglio invece del prompt.

`tipo` e `condizioni` restano `n.d.`: il primo e' una classificazione, il
secondo una sintesi, e nel testo non hanno una forma scritta da cercare. E' un
esito onesto, non una lacuna da riempire con un'euristica.

La tabella «fuori finestra, uno per uno» riporta la resa del taglio per ogni
caso. Se una forma di deposito la domina, il problema e' il taglio su quella
forma — ed e' esattamente il sospetto che `docs/costs.md` lascia aperto sui
424B3, che entrano nel prompt all'1% del loro testo.

## Cosa non e' un errore del modello

Le estrazioni in cui `source_excerpt` non si trovava nel testo inviato vengono
**declassate dalla validazione** prima di arrivare qui. Il report le conta a
parte: sono errori del modello che il codice ha intercettato, e distinguerle
dagli errori passati e' l'unico modo di sapere se la validazione serve.

## La regola sui prompt

**Nessun prompt cambia senza rieseguire le evals.** E' applicabile perche' la
chiave di cache include `prompt_version` (ADR-005): un prompt nuovo non puo'
riusare le risposte del vecchio nemmeno per sbaglio. Ogni versione lascia un
`results-<versione>.md` in questa directory, e
[../prompts/changelog.md](../prompts/changelog.md) lega ogni modifica al suo
risultato.

## In CI

`python -m edgar_llm.eval --replay` gira **senza chiave e senza rete**,
servendosi dalla cache: deterministico e a costo zero. Un miss di cache in
replay e' un errore dichiarato, non un campo vuoto — se la CI passasse su una
cache incompleta, passerebbe misurando meno di quel che crede.
