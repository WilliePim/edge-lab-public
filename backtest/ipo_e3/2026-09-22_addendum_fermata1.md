# Addendum alla pre-registrazione E3 — decisioni della fermata 1

Scritto il **22 settembre 2026**, dopo la conferma dell'utente della fermata 1 e **prima di calcolare qualunque
rendimento extra**. Completa `2026-09-22_preregistrazione.md` (commit `b1c5591`) e non la riscrive. Da qui regole,
soglie e verdetti sono fermi.

## 1. Le decisioni dell'utente sul §9

| punto | decisione |
|---|---|
| 1. Società in accomandita e LLC con «common units» | **escluse**: non sono azioni ordinarie (K-1, distribuzioni). Escono, contate, come «società in accomandita o LLC con common units» |
| 2. Filtro 1 | **opzione (b)**, perché resta un vero controllo di salute: dove i 12 mesi non sono calcolabili, il flusso di cassa operativo progressivo di 6-12 mesi (170-380 giorni) dell'ultimo deposito prima dell'ingresso deve essere **positivo**, con dato non più vecchio di 270 giorni. Senza dato resta «non verificabile» e non passa. Un flusso di 12 mesi negativo non passa, qualunque sia il progressivo. L'opzione (c) è esclusa: toglierebbe il filtro di salute e cambierebbe la domanda |
| 3. IPO senza 126 sedute di storia | escono dalle celle che richiedono il terzile a 6 mesi, contate a parte. Nessuna finestra più corta |
| 4. Form 4 2012-2014 | scaricati i 12 trimestri (manifest in `state/backfill/sec_bulk/manifest.json`) |
| 5. Universo dei peer | solo titoli quotati in borsa. **Fuori dai peer SPAC, REIT, banche e casse di risparmio**, sugli stessi codici SIC tolti dalle IPO (`universo.SIC_ESCLUSI`), letti dalla testata di `submissions`. Il SIC è quello di oggi: limite dichiarato |
| 6. ADR-051 | regola confermata, soglia 0,5-3. **Eccezioni nominate:** Dicerna, Code Rebel e BigCommerce. Sono balzi veri del primo giorno, verificati a mano: chiusura grezza uguale alla rettificata, nessun frazionamento in archivio, volume da IPO |
| 7. IPO tolte per `salto_sospetto` | **opzione (i)**: restano fuori, limite dichiarato. Niente chiusure grezze |
| 8. Giorno B degenere | si dichiara, la regola non cambia |
| 9. Forti senza capitalizzazione | escluse e contate, senza sostituzione |

## 2. Una correzione di codice trovata alla verifica dell'ADR-051 (ADR-052)

Per William Lyon Homes e Nevro l'archivio registra il raggruppamento fatto prima dell'IPO alla data della prima barra.
`casi.py` lo applicava al prezzo di collocamento, che lo contiene già, e le due IPO uscivano come «incoerenti».

**Correzione:** il prezzo di collocamento si riporta nelle unità della serie dividendo solo per i frazionamenti con
data **dopo la prima barra**. Non è una regola nuova: è quello che il §4 prescriveva, scritto giusto.

## 3. Letture fissate ora, prima dei rendimenti

- **Verdetto INCONCLUSIVO.** Il §1 dice: «INCONCLUSIVO se la 2 è vera e la media delle medie annuali è > 0, ma il t
  per anno sta fra 1 e 2, **oppure** il campione non raggiunge il punto 1». Si legge così: una cella sotto gli 80
  casi o sotto gli 8 anni è INCONCLUSIVA qualunque sia il segno dei rendimenti. Con pochi casi non si conclude né
  in un senso né nell'altro. È anche l'istruzione dell'utente per il verdetto 1 in caso di popolazione rara. Il
  referto riporta comunque i numeri della cella.
- **«Media > 0 in entrambi i sottoperiodi»** (criterio 4): la media delle medie annuali di ciascun sottoperiodo, come
  nel Russell.
- **Rendimento extra:** caso meno la media dei peer con prezzo all'ingresso, sulle stesse date, sulla chiusura
  rettificata. Servono almeno 3 peer con prezzo, come nel Russell (`russell_exits/rendimenti.rendimento_extra`,
  riusato così com'è). I delistati usano l'ultimo prezzo, o il prezzo in contanti dell'offerta (§6 «il prezzo del
  deal»). I depositi vengono dallo zip in blocco delle submissions; il documento dell'offerta si scarica se non è in
  cache, contato nel tetto delle 3.000 chiamate. Se il tetto finisce, vale l'ultimo prezzo, e i casi si contano. Le
  serie seguono i cambi di ticker e le continuazioni fuori borsa (`serie_seguita`).
- **Placebo:** per ogni ingresso della cella, la finestra di 252 sedute che parte 126 sedute dopo l'ingresso, con gli
  stessi peer.
- **Base di coorte:** ogni IPO classificata (rotta, forte o intermedia), senza filtri, entra alla **data di
  controllo** (S + 10) con 5 peer scelti con le stesse regole a quella data. Orizzonti 63, 126 e 252. Descrittiva.
- **Finestre descrittive** delle rotte: rendimento del titolo, non extra, perché i peer si scelgono all'ingresso.
  - dal prezzo di collocamento (nelle unità della serie) alla chiusura di S − 10;
  - da S − 10 a S + 10;
  - da S + 10 all'ingresso B.

  Sulle chiusure rettificate per i frazionamenti, per tutte le rotte con un ingresso B e, a parte, per quelle della
  cella del verdetto.
- **Spaccato insider**, sulle rotte della cella del verdetto (B × 252):
  - *con dati Form 4*: l'emittente ha almeno un deposito Form 3/4/5 nei dati trimestrali della SEC fra il collocamento
    e l'ingresso B;
  - *con vendite*: almeno una transazione non derivata con codice `S` (vendita sul mercato aperto), con data fra S e
    l'ingresso B escluso, di una persona che dichiara il ruolo di dirigente (Officer) o amministratore (Director).

  Attesa registrata nel §8: il gruppo con vendite fa peggio. Descrittivo, fuori dai verdetti.
- **Coorte 2020-2021:** le celle del verdetto ristrette agli anni di coorte 2020 e 2021. Descrittiva.
