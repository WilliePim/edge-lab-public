# Pre-registrazione — E3: IPO rotte e IPO forti (USA, 2012-2024)

Scritta il **22 settembre 2026**, prima di calcolare o guardare qualunque rendimento extra. Segue la direttiva
dell'utente del 22 settembre, «Backtest E3: IPO rotte e IPO forti (USA, 2012-2024)».

**Fermata 1** è questo file, più:
- `risultati/conteggi.md`: imbuto, coperture, disponibilità per cella, giorno d'ingresso B;
- `verifica_30.md`: la verifica a mano dei prospetti.

Dopo la conferma dell'utente, regole, soglie e verdetti non cambiano. Una modifica è un addendum datato, mai una
riscrittura. Le decisioni tecniche stanno in `DECISIONS.md`, ADR-046 … ADR-050.

> **Stato: confermata il 22-09-2026.** Le decisioni dell'utente sui punti del §9 stanno in
> `2026-09-22_addendum_fermata1.md`, scritto prima di calcolare i rendimenti.

---

## 1. Domande e verdetti (testo della direttiva)

1. **IPO rotte.** Un'IPO di una società sana, schiacciata sotto il prezzo di collocamento da vendite tecniche, recupera
   contro società simili se compro quando la vendita finisce e tengo un anno?
2. **IPO forti.** Un'IPO che alla scadenza del lock-up non ha mai chiuso sotto il prezzo di collocamento batte società
   simili nell'anno seguente?

Le due domande sono opposte apposta. Se reggono entrambe c'è qualcosa che non va nel disegno, e il referto lo deve
discutere prima di qualsiasi conclusione.

I criteri sono uguali per entrambe e si leggono solo sulla cella indicata.

- **REGGE** se sono vere tutte:
  1. almeno 80 casi e almeno 8 anni di coorte con casi;
  2. mediana del rendimento extra > 0;
  3. media delle medie annuali > 0, con t per anno ≥ 2;
  4. media > 0 in entrambi i sottoperiodi, 2012-2018 e 2019-2024;
  5. placebo con |t| < 2 e media più bassa della cella del verdetto.
- **INCONCLUSIVO** se la 2 è vera e la media delle medie annuali è > 0, ma il t per anno sta fra 1 e 2, oppure il
  campione non raggiunge il punto 1.
- **NON REGGE** in tutti gli altri casi.

| verdetto | cella |
|---|---|
| 1. IPO rotte | ingresso B × 252 sedute |
| 2. IPO forti | ingresso unico × 252 sedute |

Tutte le altre celle sono descrittive.

## 2. Universo (fase 0; ADR-047)

- **Candidati.** 424B4 e 424B1 dal 2012 al 2024, presi dagli indici trimestrali EDGAR. Il 424B3 entra solo in
  mancanza degli altri due.
- **Esclusioni che non richiedono il testo,** prese dalle submissions in blocco (ADR-046): classe già quotata, SPAC
  (SIC 6770), REIT (SIC 6798), banche e casse di risparmio, fondi chiusi (N-2), emittenti esteri o ADR, entità non
  operative.
- **Esclusioni dal testo del prospetto** (ADR-049): SPAC (trust account), unit, REIT dichiarato, nessun prezzo di
  collocamento, prezzo sotto $5.
- **Identità e prezzi.** Codice EODHD dello stesso CIK con una prima barra entro 10 sedute dal prospetto. Prezzi solo
  tramite `market_data.api` (ADR-040), ticker seguiti con `serie_seguita`.

## 3. Date (ADR-049)

- **Data di collocamento:** la copertina del prospetto; se manca, la seduta prima della prima barra.
- **Scadenza del lock-up:** data di collocamento + durata dichiarata, in giorni di calendario, portata sulla prima
  seduta da quella data in poi. È la seduta S.
- **Data di controllo:** S + 10 sedute.

## 4. Rotte e forti (fase 1)

Si misura sulle chiusure rettificate per i frazionamenti, con il prezzo di collocamento riportato nelle stesse unità.

- **Rotta:** chiusura alla data di controllo ≤ −30% dal prezzo di collocamento.
- **Forte:** nessuna chiusura sotto il prezzo di collocamento dalla prima barra alla data di controllo.
- **Intermedie:** solo contate.

Servono almeno l'80% delle barre fra la prima barra e la data di controllo.

## 5. Filtri (fase 2; ADR-050)

Valgono solo per le rotte, alla data di ciascun ingresso, e usano solo depositi precedenti a quella data.
1. **Flusso di cassa operativo degli ultimi 12 mesi > 0** (vedi §9, punto 2).
2. **Cassa netta, oppure debito netto / EBITDA < 3.**
3. **Nessuna emissione dall'IPO:** nessun S-1, S-3 o 424B secondario, nessun 8-K con voce 3.02, azioni cresciute al
   massimo del 5%.
4. **Nessuna fusione o acquisizione annunciata.**

Un filtro «non verificabile» non passa. Le forti passano solo il filtro 4.

## 6. Peer (fase 3; ADR-050)

**Universo:**
- azioni ordinarie americane quotate su una borsa, da almeno 3 anni contati per CIK;
- che passano i filtri 1 e 2 alla data d'ingresso;
- con i bilanci presi dagli zip in blocco, point-in-time sulla data `filed`.

**Scelta:** lo stesso terzile di rendimento dei 6 mesi prima dell'ingresso, poi i 5 più vicini per capitalizzazione.

**Rendimenti** (alla fermata 2):
- sulla chiusura rettificata;
- con `serie_seguita` per i ticker che cambiano, comprese le continuazioni fuori borsa dopo un fallimento (suffisso Q);
- in caso di prezzo congelato mentre il gemello scambia, o di serie fuori borsa che non passa i controlli di qualità
  dell'archivio, vale l'ultimo prezzo vero, e i casi si contano;
- per un'acquisizione in contanti, il prezzo del deal.

**Motivazione pre-registrata:** fermarsi al delisting congela la perdita e gonfia i rendimenti della strategia.

## 7. Ingressi (fase 4; ADR-050)

| ingresso | regola |
|---|---|
| A | la prima seduta dopo la data di scadenza del lock-up |
| **B** (verdetto) | dalla data di controllo in avanti, la prima chiusura con (1) nelle ultime 20 sedute nessuna chiusura sotto il minimo registrato dalla scadenza in poi, e (2) volume medio delle ultime 10 sedute ≤ mediana delle 60 sedute che finiscono alla scadenza. Al più presto S + 30; forzato a S + 126 |
| C | S + 63 |
| forti | la data di controllo |

**Controllo di degenerazione:** la distribuzione del giorno B sta in `risultati/conteggi.md` §4.

## 8. Orizzonti, finestre e statistica (fasi 5-6, alla fermata 2)

**Orizzonti.** Rendimento extra (caso meno la media dei 5 peer) a 63, 126 e 252 sedute da ogni ingresso. Un caso
senza la finestra completa esce da quella cella e si conta.

**Finestre descrittive:**
- dal collocamento a S − 10;
- da S − 10 a S + 10;
- da S + 10 all'ingresso B.

**Statistica per cella:**
- casi, media, mediana, quota di positivi;
- media per anno di coorte e t sulle medie annuali, con la tabella per anno sempre riportata;
- sottoperiodi 2012-2018 e 2019-2024, e la coorte 2020-2021 da sola, descrittiva.

**Controlli:**
- **Placebo:** la stessa finestra di 252 sedute spostata in avanti di 126 dall'ingresso, per tutti e due i verdetti.
- **Base di coorte:** tutte le IPO dell'universo, senza condizione rotta/forte e senza filtri, contro i peer alla
  stessa data relativa. Descrittiva.
- **Insider:** le rotte con dati Form 4 si dividono fra chi ha vendite open-market di dirigenti fra la scadenza e
  l'ingresso e chi no. **Attesa registrata ora: il gruppo con vendite fa peggio.** Descrittiva, fuori dai verdetti.

## 9. Decisioni dell'utente richieste alla fermata 1

I numeri stanno in `risultati/conteggi.md`.

1. **Società in accomandita e LLC con «common units».** Non sono azioni ordinarie: si escludono? Oggi sono segnate e
   contate, non escluse.
2. **Filtro 1 sul flusso di cassa.** Per una società appena quotata, 12 mesi di flusso di cassa in XBRL spesso non
   esistono prima dell'ingresso: né un anno fiscale né quattro trimestri consecutivi. Oggi «non verificabile»
   esclude. Le opzioni, con i conteggi in `conteggi.md` §2:
   - (a) resta così;
   - (b) dove i 12 mesi mancano, il segno dell'ultimo flusso progressivo di 6-12 mesi;
   - (c) senza filtro 1 per le rotte.
3. **Rendimento a 6 mesi per il terzile dei peer.** Le IPO con lock-up corto entrano con meno di 126 sedute di
   storia. Oggi restano senza peer, contate.
4. **Form 4 per lo spaccato insider.** I dati trimestrali su disco partono dal 2015. Scaricare i trimestri dal 2012 al
   2014 costa 12 chiamate EDGAR; altrimenti lo spaccato copre solo le coorti dalla fine del 2014.
5. **Universo dei peer solo su borsa** (ADR-050): da confermare. Va deciso anche un secondo punto: oggi l'universo dei
   peer comprende banche e REIT, che fra le IPO sono esclusi. Nell'esempio della rotta, 2 dei 5 peer sono banche
   (MBVT, FBIZ). Le opzioni: si tolgono dai peer le stesse categorie tolte dalle IPO (SIC 6770, 6798, 602x/603x), o
   restano.
6. **Coerenza della serie con il prezzo di collocamento** (ADR-051). Regola nuova, non nella direttiva: un'IPO la cui
   prima chiusura sta fuori da 0,5-3 volte il prezzo di collocamento esce. La serie è di un altro titolo con lo stesso
   ticker, oppure è già rettificata dal fornitore. Da confermare, con la soglia. I casi esclusi sono elencati per nome
   in `conteggi.md`.
7. **IPO tolte dall'archivio per un `salto_sospetto`.** L'archivio segnala 582 IPO con un salto simile a un
   frazionamento non verificato e ne toglie dai prezzi puliti tutta la storia dalla prima barra al salto, anche
   quando il salto cade anni dopo. Così 204 IPO escono per «meno dell'80% di barre». Non sono a caso: il salto è quasi
   sempre un raggruppamento, cioè un titolo sceso molto. Classificate sulle chiusure grezze, dove il salto cade dopo
   la data di controllo, sarebbero 58 rotte, 31 forti e 91 intermedie (`salti.py`, `conteggi.md` §1). Le opzioni:
   - (i) restano fuori, e il limite si dichiara: il campione delle rotte perde proprio le peggiori;
   - (ii) si classificano sulle chiusure grezze fino alla data di controllo; dopo, per i rendimenti, vale la serie
     rettificata di `serie_eodhd` con il salto trattato come frazionamento, e i casi si contano a parte.
8. **Degenerazione del giorno B.** Il 52% delle rotte con un ingresso B sta a un estremo: 16% al primo giorno
   possibile (S + 30), 36% forzato (S + 126). È oltre la metà, quindi si dichiara: la regola B, così com'è, spesso non
   scatta. Nessuna modifica proposta: la regola resta quella della direttiva.
9. **Forti senza capitalizzazione.** Per 26 forti la capitalizzazione non si calcola: mancano sia le azioni in XBRL
   dopo il collocamento sia quelle del prospetto. Senza capitalizzazione non si scelgono i peer. Oggi escono, contate,
   e non c'è nessuna sostituzione.

**Dimensione delle celle del verdetto, con le regole attuali** (`conteggi.md` §3):
- **verdetto 1:** 7 casi in 4 anni. Sotto il criterio 1, quindi al più INCONCLUSIVO, qualunque cosa dicano i rendimenti;
- **verdetto 2:** 340 casi in 13 anni.

Solo l'opzione (c) del punto 2 porta il verdetto 1 sopra gli 80 casi.
